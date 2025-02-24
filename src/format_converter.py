import json
import georinex as gr
import pynmea2
import pandas as pd
from pathlib import Path
from datetime import datetime
from decimal import Decimal
import openai
import os
from dotenv import load_dotenv
from openai import AzureOpenAI

# Load environment variables
load_dotenv()

# Configure Azure OpenAI
client = AzureOpenAI(
    api_key=os.getenv('AZURE_OPENAI_API_KEY'),
    api_version=os.getenv('AZURE_OPENAI_API_VERSION'),
    base_url=os.getenv('AZURE_OPENAI_ENDPOINT')
)

def custom_serializer(obj):
    """Custom JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, (datetime, pd.Timestamp)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    return str(obj)

def validate_jsonl(file_path):
    """Validate if the JSONL file is correctly formatted and contains required fields"""
    try:
        required_fields = ['timestamp_ms']  # Add more required fields as needed
        valid_records = 0
        total_records = 0
        
        with open(file_path, 'r') as f:
            for line in f:
                total_records += 1
                try:
                    record = json.loads(line)
                    # Check if all required fields are present
                    if all(field in record for field in required_fields):
                        valid_records += 1
                except json.JSONDecodeError:
                    continue
        
        # File is valid if at least 50% of records are valid
        is_valid = valid_records > 0 and (valid_records / total_records) >= 0.5
        return is_valid, valid_records, total_records
        
    except Exception as e:
        print(f"Error validating JSONL: {str(e)}")
        return False, 0, 0

def convert_to_jsonl(input_file, output_file=None):
    """Convert GNSS data file to JSONL format"""
    if output_file is None:
        output_file = os.path.splitext(input_file)[0] + '.jsonl'
    
    try:
        # Detect file type
        file_ext = os.path.splitext(input_file)[1].lower()
        print(f"Detected file type: {file_ext}")
        
        # Try RINEX conversion once for .obs files
        if file_ext == '.obs':
            print("Attempting RINEX conversion...")
            success = convert_rinex_to_jsonl(input_file, output_file)
            if success and validate_jsonl(output_file)[0]:
                print("RINEX conversion successful")
                return output_file
            print("RINEX conversion failed, attempting LLM fallback...")
            success = convert_with_llm(input_file, output_file, format_type='RINEX')
            if success:
                return output_file
            print("RINEX LLM conversion failed")
        
        # Try NMEA conversion once for .nmea files
        elif file_ext == '.nmea':
            print("Attempting NMEA conversion...")
            success = convert_nmea_to_jsonl(input_file, output_file)
            if success and validate_jsonl(output_file)[0]:
                print("NMEA conversion successful")
                return output_file
            print("NMEA conversion failed, attempting LLM fallback...")
            success = convert_with_llm(input_file, output_file, format_type='NMEA')
            if success:
                return output_file
            print("NMEA LLM conversion failed")
        
        # For unknown formats, try LLM directly
        else:
            print("Unknown format, attempting LLM conversion...")
            success = convert_with_llm(input_file, output_file)
            if success:
                return output_file
        
        raise Exception("Failed to convert file to JSONL format")
        
    except Exception as e:
        print(f"Error converting file: {str(e)}")
        if os.path.exists(output_file):
            os.remove(output_file)
        return None

def convert_rinex_to_jsonl(input_file, output_file):
    """Convert RINEX observation file to JSONL format"""
    try:
        print(f"Reading RINEX file: {input_file}")
        obs_data = gr.load(input_file)
        
        print("Converting RINEX data to DataFrame...")
        df = obs_data.to_dataframe().reset_index()
        print(f"Found {len(df)} RINEX records")
        
        print("Writing records to JSONL file...")
        record_count = 0
        with open(output_file, 'w') as f:
            for record in df.to_dict(orient='records'):
                if 'time' in record:
                    try:
                        # Use pandas Timestamp to convert time field to a Python datetime
                        ts = pd.Timestamp(record['time'])
                        record['timestamp_ms'] = int(ts.timestamp() * 1000)
                    except Exception as e:
                        print(f"Warning: Failed to convert time field: {e}")
                        record['timestamp_ms'] = int(datetime.now().timestamp() * 1000)
                else:
                    record['timestamp_ms'] = int(datetime.now().timestamp() * 1000)
                f.write(json.dumps(record, default=custom_serializer) + '\n')
                record_count += 1
        
        print(f"Successfully wrote {record_count} RINEX records to JSONL")
        return True
        
    except Exception as e:
        print(f"Error converting RINEX file: {str(e)}")
        return False

def convert_nmea_to_jsonl(input_file, output_file):
    """Convert NMEA file to JSONL format"""
    try:
        print(f"Reading NMEA file: {input_file}")
        valid_count = 0
        total_count = 0
        gga_count = 0
        rmc_count = 0
        
        with open(input_file, 'r') as nmea_file, open(output_file, 'w') as jsonl_file:
            for line in nmea_file:
                total_count += 1
                try:
                    # Split line to separate NMEA message and timestamp
                    parts = line.strip().split(',')
                    if len(parts) > 1:
                        # Reconstruct NMEA message without timestamp
                        nmea_msg = ','.join(parts[:-1])
                        timestamp = int(parts[-1]) if parts[-1].isdigit() else None
                        
                        # Parse NMEA message
                        msg = pynmea2.parse(nmea_msg)
                        
                        # Track message types
                        if msg.sentence_type == 'GGA':
                            gga_count += 1
                        elif msg.sentence_type == 'RMC':
                            rmc_count += 1
                        
                        # Convert to dictionary and write to JSONL
                        data = nmea_to_dict(msg, timestamp)
                        jsonl_file.write(json.dumps(data, default=custom_serializer) + '\n')
                        valid_count += 1
                        
                        # Print progress every 1000 messages
                        if valid_count % 1000 == 0:
                            print(f"Processed {valid_count} valid messages...")
                        
                except pynmea2.ParseError:
                    continue
                except Exception as e:
                    print(f"Error processing line: {e}")
                    continue
        
        print(f"NMEA Processing Summary:")
        print(f"- Total lines processed: {total_count}")
        print(f"- Valid messages: {valid_count}")
        print(f"- GGA messages: {gga_count}")
        print(f"- RMC messages: {rmc_count}")
        return valid_count > 0
        
    except Exception as e:
        print(f"Error converting NMEA file: {str(e)}")
        return False

def nmea_to_dict(msg, timestamp=None):
    """Convert NMEA message to dictionary"""
    data = {}
    for field in msg.fields:
        value = getattr(msg, field[1])
        data[field[1]] = value
    # Add sentence type and timestamp
    data['sentence_type'] = msg.sentence_type
    if timestamp is not None:
        data['timestamp_ms'] = timestamp
    return data

def convert_with_llm(input_file, output_file, format_type=None):
    """Convert unknown format to JSONL using LLM"""
    try:
        print("Starting LLM-based conversion...")
        print("Read sample data for analysis")
        
        # Read first few bytes of the file
        with open(input_file, 'r') as f:
            sample_data = f.read(1000)  # Read first 1000 bytes
            
        print("Requesting format analysis from LLM...")
        
        # Create format-specific system messages
        system_messages = {
            'RINEX': """You are an expert in processing RINEX observation files. Your task is to generate robust Python code that processes a RINEX observation file to extract key measurement data. The generated Python code must:
1. Be syntactically correct and compatible with Python 3.11.
2. Return only the Python script enclosed in a code block (```python ... ```) with no additional comments, explanations, or text.
3. Include error handling that captures any execution errors in a variable named 'execution_errors' and feeds them back to the LLM agent for refinement.
4. Extract at least the following fields: timestamp_ms, satellite_system, satellite_number, pseudorange, carrier_phase, doppler, and signal_strength.
5. Read from the input file path and write to the output file path provided in the code.
6. DO NOT include example usage or test data in the generated code.
Return only the Python code following these guidelines.""",
            'NMEA': """You are an expert in NMEA data processing. Your task is to generate robust Python code that processes NMEA data to extract location information. The generated Python code must:
1. Be syntactically correct and compatible with Python 3.11.
2. Return only the Python script enclosed in a code block (```python ... ```) with no additional comments, explanations, or text.
3. Include error handling that captures any execution errors in a variable named 'execution_errors' and feeds them back to the LLM agent for refinement.
4. Extract at least the following fields: timestamp_ms, latitude, longitude, altitude (if available), and num_satellites (if available).
5. Read from the input file path and write to the output file path provided in the code.
6. DO NOT include example usage or test data in the generated code.
Return only the Python code following these guidelines.""",
            None: """You are a seasoned GNSS data format expert. Your task is to analyze the provided sample data and generate robust Python code that converts the data into a standardized JSONL format. The generated Python code must:
1. Be syntactically correct and compatible with Python 3.11.
2. Return only the Python script enclosed in a code block (```python ... ```) with no additional comments, explanations, or text.
3. Include error handling that captures any execution errors in a variable named 'execution_errors' and feeds them back to the LLM agent for refinement.
4. Extract at least the field timestamp_ms and any available GNSS measurements or location data.
5. Read from the input file path and write to the output file path provided in the code.
6. DO NOT include example usage or test data in the generated code.
Return only the Python code following these guidelines."""
        }

        # Select appropriate system message
        system_message = system_messages.get(format_type, system_messages[None])
        
        # Maximum retry attempts
        max_attempts = 10
        attempt = 0
        last_error = None
        
        while attempt < max_attempts:
            try:
                # Request format analysis and conversion code from LLM
                response = client.chat.completions.create(
                    model=os.getenv('AZURE_OPENAI_ENGINE'),
                    messages=[
                        {"role": "system", "content": system_message},
                        {"role": "user", "content": f"""Here's a sample of the data from {input_file}:

{sample_data}

Generate Python code to convert this data to JSONL format and save it to {output_file}.
The code should use these exact file paths:
INPUT_FILE = "{input_file}"
OUTPUT_FILE = "{output_file}"
"""}
                    ],
                    temperature=0.7,
                    max_tokens=10000
                )
                
                # Extract the generated code
                generated_code = response.choices[0].message.content
                
                # Extract code from within code block markers if present
                if "```python" in generated_code and "```" in generated_code:
                    # Extract code between ```python and ``` markers
                    code_start = generated_code.find("```python") + len("```python")
                    code_end = generated_code.find("```", code_start)
                    if code_end != -1:
                        generated_code = generated_code[code_start:code_end].strip()
                
                # Execute the generated code
                exec(generated_code)
                
                # Validate the output
                is_valid, valid_count, total_count = validate_jsonl(output_file)
                if is_valid:
                    print(f"Successfully converted {valid_count}/{total_count} records")
                    return True
                
                print(f"Validation failed: {valid_count}/{total_count} valid records")
                last_error = f"Generated code produced {valid_count}/{total_count} valid records"
                
            except Exception as e:
                print(f"Attempt {attempt + 1} failed: {str(e)}")
                last_error = str(e)
            
            attempt += 1
        
        print(f"Failed to generate valid output after {max_attempts} attempts")
        if last_error:
            print(f"Last error: {last_error}")
        return False
        
    except Exception as e:
        print(f"Error in LLM conversion: {str(e)}")
        return False 