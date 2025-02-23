import json
import georinex as gr
import pynmea2
import pandas as pd
from pathlib import Path
import openai
from datetime import datetime
from decimal import Decimal
import os
from dotenv import load_dotenv
import re
import numpy as np
from openai import AzureOpenAI

# Load environment variables
load_dotenv()

class GNSSProcessor:
    def __init__(self):
        self.system_prompt = """You are an expert GNSS data processing AI agent. Your task is to:
1. Analyze GNSS data files to identify their format and key characteristics.
2. Generate robust Python code that processes the data and extracts standardized location records.
3. Ensure the code correctly parses timestamps and converts them to Unix time (milliseconds since epoch), and transforms geographic coordinates to decimal degrees.
4. Produce a JSONL file where each record includes at least:
   - timestamp_ms
   - latitude
   - longitude
   - altitude (if available)
   - num_satellites (if available)
   - HDOP and quality metrics (if available)
   - Additional fields (e.g., satellite system, signal strength, speed, course) as present.
5. Handle incomplete or inconsistent data gracefully, and report useful errors.
6. Ensure the generated code is syntactically valid, avoids pitfalls like leading zeros in numeric literals, and is compatible with Python 3.11.

You will receive execution feedback. Use this iterative feedback to improve and refine your solution until a fully valid and robust output is achieved."""
        self.output_callback = print  # Default to print function

    def log(self, message):
        """Helper method to handle output messages"""
        self.output_callback(message)

    def custom_serializer(self, obj):
        """Custom JSON serializer for objects not serializable by default json code"""
        if isinstance(obj, (datetime, pd.Timestamp)):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        return str(obj)

    def convert_nmea_coordinates(self, lat, lat_dir, lon, lon_dir):
        """Convert NMEA coordinate format to decimal degrees"""
        try:
            # Convert latitude from DDMM.MMMMM to decimal degrees
            lat_deg = float(lat[:2])
            lat_min = float(lat[2:])
            latitude = lat_deg + lat_min/60.0
            if lat_dir == 'S':
                latitude = -latitude

            # Convert longitude from DDDMM.MMMMM to decimal degrees
            lon_deg = float(lon[:3])
            lon_min = float(lon[3:])
            longitude = lon_deg + lon_min/60.0
            if lon_dir == 'W':
                longitude = -longitude

            return latitude, longitude
        except (ValueError, TypeError, IndexError):
            return None, None

    def process_rinex(self, input_file):
        """Process RINEX observation file"""
        try:
            # Read RINEX data
            obs_data = gr.load(input_file)
            df = obs_data.to_dataframe().reset_index()
            
            # Filter for location-related data
            location_records = []
            for _, row in df.iterrows():
                try:
                    # Extract satellite system and number safely
                    sv = row.get('sv', '')
                    if isinstance(sv, str) and ' ' in sv:
                        sat_sys, sat_num = sv.split()
                    else:
                        sat_sys = sv[:1] if isinstance(sv, str) and sv else None
                        sat_num = sv[1:] if isinstance(sv, str) and len(sv) > 1 else None

                    # Create record with safe value extraction
                    record = {
                        'timestamp': row.get('time'),
                        'satellite_system': sat_sys,
                        'satellite_number': sat_num,
                        'pseudorange': float(row.get('C1', 0)) if pd.notna(row.get('C1')) else None,
                        'carrier_phase': float(row.get('L1', 0)) if pd.notna(row.get('L1')) else None,
                        'doppler': float(row.get('D1', 0)) if pd.notna(row.get('D1')) else None,
                        'signal_strength': float(row.get('S1', 0)) if pd.notna(row.get('S1')) else None
                    }
                    
                    # Only add records with valid data
                    if any(v is not None and v != 0 for v in [record['pseudorange'], record['carrier_phase'], record['doppler'], record['signal_strength']]):
                        location_records.append(record)
                except (ValueError, TypeError, IndexError) as e:
                    print(f"Warning: Error processing RINEX record: {str(e)}")
                    continue
            
            if not location_records:
                raise ValueError("No valid location records found in RINEX file")
                
            return location_records
            
        except Exception as e:
            raise Exception(f"Error processing RINEX file: {str(e)}")

    def process_nmea(self, input_file):
        """Process NMEA file"""
        try:
            location_records = []
            
            with open(input_file, 'r') as f:
                for line in f:
                    try:
                        # Split the line to separate NMEA message and timestamp
                        parts = line.strip().split(',')
                        if len(parts) < 2:  # Skip invalid lines
                            continue
                            
                        nmea_msg = ','.join(parts[:-1])
                        timestamp = int(parts[-1]) if parts[-1].isdigit() else None
                        
                        msg = pynmea2.parse(nmea_msg)
                        
                        # Extract location data from GGA, RMC, or GNS messages
                        if msg.sentence_type in ['GGA', 'RMC', 'GNS']:
                            record = self.extract_location_data(msg, timestamp)
                            if record:
                                location_records.append(record)
                                    
                    except (pynmea2.ParseError, ValueError, AttributeError) as e:
                        print(f"Warning: Error parsing NMEA message: {str(e)}")
                        continue
                    except Exception as e:
                        print(f"Warning: Unexpected error processing NMEA line: {str(e)}")
                        continue
            
            if not location_records:
                raise ValueError("No valid location records found in NMEA file")
                
            return location_records
            
        except Exception as e:
            raise Exception(f"Error processing NMEA file: {str(e)}")

    def extract_location_data(self, msg, timestamp=None):
        """Extract location data from NMEA message"""
        try:
            # Check for required attributes
            if not all(hasattr(msg, attr) for attr in ['latitude', 'longitude']):
                return None

            # Only proceed if we have valid coordinates
            if msg.latitude is None or msg.longitude is None:
                return None

            # Create base record with required fields
            record = {
                'timestamp_ms': timestamp,
                'latitude': float(msg.latitude),
                'longitude': float(msg.longitude),
            }

            # Add GGA-specific fields
            if msg.sentence_type == 'GGA':
                try:
                    record.update({
                        'altitude': float(msg.altitude) if msg.altitude is not None else None,
                        'num_satellites': int(msg.num_sats) if hasattr(msg, 'num_sats') and msg.num_sats is not None else None,
                        'hdop': float(msg.horizontal_dil) if hasattr(msg, 'horizontal_dil') and msg.horizontal_dil is not None else None,
                        'quality': int(msg.gps_qual) if hasattr(msg, 'gps_qual') and msg.gps_qual is not None else None
                    })
                except (ValueError, TypeError, AttributeError) as e:
                    print(f"Warning: Error processing GGA fields: {str(e)}")
                    # Keep the basic record if conversion fails
                    pass

            # Add RMC-specific fields
            elif msg.sentence_type == 'RMC':
                try:
                    record.update({
                        'speed': float(msg.spd_over_grnd) if hasattr(msg, 'spd_over_grnd') and msg.spd_over_grnd is not None else None,
                        'course': float(msg.true_course) if hasattr(msg, 'true_course') and msg.true_course is not None else None,
                        'date': msg.datestamp.isoformat() if hasattr(msg, 'datestamp') and msg.datestamp is not None else None
                    })
                except (ValueError, TypeError, AttributeError) as e:
                    print(f"Warning: Error processing RMC fields: {str(e)}")
                    # Keep the basic record if conversion fails
                    pass

            return record

        except Exception as e:
            print(f"Warning: Error processing NMEA message: {str(e)}")
            return None

    def process_file(self, input_file):
        try:
            self.log("Starting file processing...")
            # Read a sample of the file
            with open(input_file, 'r') as f:
                sample_content = f.read(2000)  # Read first 2KB for analysis

            self.log("Analyzing file format...")
            # Initialize conversation history
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": f"Analyze this GNSS data sample and generate Python code to process it:\n\nFile: {input_file}\nSample data:\n{sample_content}"}
            ]

            max_attempts = 10  # Increased from 5 to 10
            for attempt in range(max_attempts):
                self.log(f"\nProcessing attempt {attempt + 1} of {max_attempts}")
                try:
                    # Get AI response
                    self.log("Generating processing code...")
                    client = AzureOpenAI(
                        api_key=os.getenv('AZURE_OPENAI_API_KEY'),
                        api_version=os.getenv('AZURE_OPENAI_API_VERSION'),
                        base_url=os.getenv('AZURE_OPENAI_ENDPOINT')
                    )
                    
                    response = client.chat.completions.create(
                        model=os.getenv('AZURE_OPENAI_ENGINE'),
                        messages=messages,
                        temperature=0.7,
                        max_tokens=120000
                    )
                    
                    ai_response = response.choices[0].message.content
                    
                    # Extract code from response
                    code_match = re.search(r'```python\n(.*?)\n```', ai_response, re.DOTALL)
                    if not code_match:
                        self.log("No code block found in response, requesting clarification...")
                        messages.append({"role": "assistant", "content": ai_response})
                        messages.append({"role": "user", "content": "Please provide the code within a Python code block using ```python and ``` markers."})
                        continue

                    processing_code = code_match.group(1)
                    self.log("\nGenerated code:")
                    self.log("```python")
                    self.log(processing_code)
                    self.log("```")
                    
                    # Create a safe execution environment with output capture
                    local_env = {
                        'input_file': input_file,
                        'pd': pd,
                        'np': np,
                        'datetime': datetime,
                        'json': json,
                        'pynmea2': pynmea2,
                        'gr': gr,
                        'Path': Path,
                        'print': lambda *args: execution_output.append(' '.join(str(arg) for arg in args))
                    }
                    
                    execution_output = []
                    debug_info = {
                        'attempt': attempt + 1,
                        'output': [],
                        'error': None,
                        'records_generated': False,
                        'records_valid': False
                    }
                    
                    try:
                        # Execute the processing code
                        self.log("\nExecuting generated code...")
                        try:
                            compiled_code = compile(processing_code, '<string>', 'exec')
                        except SyntaxError as se:
                            error_msg = f"Syntax error in generated code: {se}"
                            self.log(error_msg)
                            debug_info['error'] = error_msg
                            messages.append({"role": "assistant", "content": ai_response})
                            messages.append({
                                "role": "user", 
                                "content": f"Attempt {attempt + 1} generated code with syntax error: {se}. Please fix the code to avoid leading zeros in numeric literals and any syntax errors."
                            })
                            continue
                        exec(compiled_code, globals(), local_env)
                        debug_info['output'] = execution_output
                        
                        # Check if location_records were generated
                        if 'location_records' not in local_env:
                            self.log("No location_records variable was created")
                            debug_info['error'] = "No location_records variable was created"
                            messages.append({"role": "assistant", "content": ai_response})
                            messages.append({
                                "role": "user", 
                                "content": f"Attempt {attempt + 1} failed:\n" + 
                                         f"Output: {' | '.join(execution_output)}\n" +
                                         f"Error: {debug_info['error']}\n" +
                                         "The code executed but didn't generate location_records. Please modify the code to create a list of location_records with the required fields."
                            })
                            continue
                        
                        debug_info['records_generated'] = True
                        location_records = local_env['location_records']
                        
                        # Validate records
                        self.log("Validating generated records...")
                        if not self._validate_records(location_records):
                            self.log("Generated records don't match required format")
                            debug_info['error'] = "Generated records don't match required format"
                            messages.append({"role": "assistant", "content": ai_response})
                            messages.append({
                                "role": "user",
                                "content": f"Attempt {attempt + 1} failed:\n" +
                                         f"Output: {' | '.join(execution_output)}\n" +
                                         f"Error: {debug_info['error']}\n" +
                                         "Sample of invalid records:\n" +
                                         str(location_records[:2]) + "\n" +
                                         "Please fix the code to ensure all required fields (timestamp_ms, latitude, longitude) are present and properly formatted."
                            })
                            continue
                        
                        debug_info['records_valid'] = True
                        
                        # Save to JSONL
                        self.log("Records validated successfully, saving to file...")
                        output_file = str(Path(input_file).with_suffix('.location.jsonl'))
                        with open(output_file, 'w') as f:
                            for record in location_records:
                                f.write(json.dumps(record, default=self.custom_serializer) + '\n')
                        
                        self.log(f"Successfully processed {len(location_records)} records")
                        return output_file
                        
                    except Exception as e:
                        error_msg = str(e)
                        self.log(f"Error during execution: {error_msg}")
                        debug_info['error'] = error_msg
                        messages.append({"role": "assistant", "content": ai_response})
                        messages.append({
                            "role": "user",
                            "content": f"Attempt {attempt + 1} failed:\n" +
                                     f"Output: {' | '.join(execution_output)}\n" +
                                     f"Error: {error_msg}\n" +
                                     "Code execution failed. Please fix the error and try again."
                        })
                        
                        if attempt == max_attempts - 1:
                            raise Exception(f"Failed to process file after {max_attempts} attempts: {error_msg}")
                    
                except Exception as e:
                    self.log(f"Error during attempt {attempt + 1}: {str(e)}")
                    if attempt == max_attempts - 1:
                        raise Exception(f"Failed to process file after {max_attempts} attempts: {str(e)}")
            
            raise Exception("Failed to generate valid output after maximum attempts")
            
        except Exception as e:
            self.log(f"Fatal error: {str(e)}")
            raise Exception(f"Error processing file {input_file}: {str(e)}")

    def _validate_records(self, records):
        """Validate that records contain required fields in correct format"""
        if not records or not isinstance(records, list):
            return False
            
        required_fields = {'timestamp_ms', 'latitude', 'longitude'}
        numeric_fields = {'latitude', 'longitude', 'altitude', 'hdop', 'speed'}
        
        for record in records:
            if not isinstance(record, dict):
                return False
                
            # Check required fields exist
            if not all(field in record for field in required_fields):
                return False
                
            # Validate numeric fields
            for field in numeric_fields:
                if field in record and record[field] is not None:
                    try:
                        float(record[field])
                    except (ValueError, TypeError):
                        return False
        
        return True 