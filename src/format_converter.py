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
import math

# Load environment variables
load_dotenv()

# Configure Azure OpenAI
client = AzureOpenAI(
    api_key=os.getenv('AZURE_OPENAI_API_KEY'),
    api_version=os.getenv('AZURE_OPENAI_API_VERSION'),
    base_url=f"{os.getenv('AZURE_OPENAI_ENDPOINT')}/deployments/{os.getenv('AZURE_OPENAI_ENGINE')}"
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
        
        # Load RINEX data with multi-system support
        obs_data = gr.load(input_file, use='G,R,E,C,J')  # GPS, GLONASS, Galileo, BeiDou, QZSS
        
        print("Converting RINEX data to DataFrame...")
        df = obs_data.to_dataframe().reset_index()
        print(f"Found {len(df)} RINEX records")
        
        print("Writing records to JSONL file...")
        record_count = 0
        with open(output_file, 'w') as f:
            for record in df.to_dict(orient='records'):
                try:
                    # Extract timestamp
                    if 'time' in record:
                        try:
                            ts = pd.Timestamp(record['time'])
                            record['timestamp_ms'] = int(ts.timestamp() * 1000)
                        except Exception as e:
                            print(f"Warning: Failed to convert time field: {e}")
                            record['timestamp_ms'] = int(datetime.now().timestamp() * 1000)
                    else:
                        record['timestamp_ms'] = int(datetime.now().timestamp() * 1000)
                    
                    # Extract satellite system and number
                    if 'sv' in record:
                        sv = str(record['sv'])
                        if sv:
                            record['satellite_system'] = sv[0] if len(sv) > 0 else None
                            record['satellite_number'] = sv[1:] if len(sv) > 1 else None
                    
                    # Extract measurements
                    measurements = {}
                    for key in record:
                        # Handle different observation types
                        if any(key.startswith(prefix) for prefix in ['C', 'L', 'D', 'S']):
                            value = record[key]
                            if pd.notna(value) and not math.isinf(float(value)):
                                measurements[key] = float(value)
                    
                    # Add measurements to record
                    if measurements:
                        record['measurements'] = measurements
                    
                    # Write valid record
                    f.write(json.dumps(record, default=custom_serializer) + '\n')
                    record_count += 1
                    
                    # Print progress
                    if record_count % 1000 == 0:
                        print(f"Processed {record_count} records...")
                        
                except Exception as e:
                    print(f"Warning: Failed to process record: {e}")
                    continue
        
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
        
        # Try different encodings
        encodings = ['utf-8', 'latin1', 'ascii']
        nmea_data = None
        
        for encoding in encodings:
            try:
                with open(input_file, 'rb') as f:
                    nmea_data = f.read().decode(encoding)
                break
            except UnicodeDecodeError:
                continue
                
        if nmea_data is None:
            # If all encodings fail, try reading line by line ignoring errors
            with open(input_file, 'rb') as f:
                nmea_data = f.read().decode('utf-8', errors='ignore')
        
        # Split into lines and process
        lines = nmea_data.splitlines()
        with open(output_file, 'w') as jsonl_file:
            for line in lines:
                total_count += 1
                try:
                    # Clean the line
                    line = line.strip()
                    if not line:
                        continue
                        
                    # Handle lines with or without timestamp
                    parts = line.split(',')
                    if len(parts) > 1:
                        # Check if last part could be timestamp
                        if parts[-1].isdigit() and len(parts[-1]) >= 13:  # Looks like a millisecond timestamp
                            timestamp = int(parts[-1])
                            nmea_msg = ','.join(parts[:-1])
                        else:
                            timestamp = None
                            nmea_msg = line
                    else:
                        timestamp = None
                        nmea_msg = line
                    
                    # Parse NMEA message
                    if nmea_msg.startswith('$'):
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
                        
                except pynmea2.ParseError:
                    continue
                except Exception as e:
                    print(f"Error processing line: {str(e)}")
                    continue
                
                # Print progress every 1000 messages
                if valid_count % 1000 == 0:
                    print(f"Processed {valid_count} valid messages...")
        
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
        print("Reading sample data for analysis")
        
        # Try different encodings for reading sample data
        sample_data = None
        encodings = ['utf-8', 'latin1', 'ascii']
        
        for encoding in encodings:
            try:
                with open(input_file, 'rb') as f:
                    # Read first 15 lines or 2000 bytes, whichever comes first
                    lines = []
                    bytes_read = 0
                    for _ in range(15):
                        line = f.readline()
                        if not line:
                            break
                        bytes_read += len(line)
                        if bytes_read > 2000:
                            break
                        try:
                            decoded_line = line.decode(encoding)
                            lines.append(decoded_line)
                        except UnicodeDecodeError:
                            continue
                    sample_data = ''.join(lines)
                if sample_data:
                    break
            except Exception:
                continue
                
        if not sample_data:
            # If all encodings fail, try reading with ignore errors
            with open(input_file, 'rb') as f:
                sample_data = f.read(2000).decode('utf-8', errors='ignore')
        
        print("Requesting format analysis from LLM...")
        
        # Create format-specific system messages
        system_messages = {
            'RINEX': """You are an expert in processing RINEX observation files. Generate Python code that:
1. Processes RINEX data to extract: timestamp_ms, satellite_system, satellite_number, pseudorange, carrier_phase, doppler, signal_strength
2. Handles different RINEX versions and satellite systems (GPS, GLONASS, Galileo, BeiDou)
3. Includes robust error handling and validation
4. Returns only the Python code block with no additional text""",
            
            'NMEA': """You are an expert in NMEA data processing. Generate Python code that:
1. Processes NMEA sentences (GGA, RMC, GSA, GSV, etc.)
2. Extracts: timestamp_ms, latitude, longitude, altitude, speed, course, num_satellites, hdop, fix_quality
3. Handles different NMEA message types and formats
4. Includes checksum validation and error handling
5. Returns only the Python code block with no additional text""",
            
            None: """You are a GNSS data format expert. Analyze the sample data and generate Python code that:
1. Identifies the format and extracts all relevant GNSS measurements
2. Handles binary and text formats with appropriate encoding
3. Extracts at minimum: timestamp_ms and any available position/measurement data
4. Includes format-specific validation and error handling
5. Returns only the Python code block with no additional text"""
        }
        
        # Select appropriate system message
        system_message = system_messages.get(format_type, system_messages[None])
        
        # Prepare user message with sample data and file paths
        user_message = f"""Sample data from the file:
{sample_data}

Generate Python code to process this data format. The code should:
1. Read from '{input_file}'
2. Write to '{output_file}' in JSONL format
3. Extract all relevant GNSS data
4. Handle errors and edge cases
5. Include validation of extracted data

Return only the Python code block."""

        # Make API call with reduced tokens and temperature
        response = client.chat.completions.create(
            model=os.getenv('AZURE_OPENAI_MODEL'),
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message}
            ],
            temperature=0.3,
            max_tokens=10000
        )
        
        # Extract and execute the generated code
        generated_code = response.choices[0].message.content
        if '```python' in generated_code:
            code_block = generated_code.split('```python')[1].split('```')[0]
        else:
            code_block = generated_code
            
        print("\nExecuting generated code...")
        exec(code_block)
        
        # Validate the output file
        if os.path.exists(output_file):
            is_valid, valid_count, total_count = validate_jsonl(output_file)
            if is_valid:
                print(f"Successfully converted file with {valid_count}/{total_count} valid records")
                return True
                
        return False
        
    except Exception as e:
        print(f"Error in LLM conversion: {str(e)}")
        return False 