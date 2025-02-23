import json
import os
from pathlib import Path
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

def validate_location_records(records):
    """Validate if location records have required fields for FGO"""
    required_fields = {
        'nmea': ['timestamp_ms', 'latitude', 'longitude'],
        'rinex': ['timestamp_ms', 'satellite_system', 'satellite_number', 'pseudorange']
    }
    
    if not records:
        return False
        
    # Detect record type based on fields
    record_type = 'rinex' if 'satellite_system' in records[0] else 'nmea'
    required = required_fields[record_type]
    
    # Check if all records have required fields
    return all(all(field in record for field in required) for record in records)

def extract_location_data(input_file, output_file=None):
    """Extract standardized location records from JSONL file"""
    try:
        print(f"Starting location data extraction from: {input_file}")
        input_path = Path(input_file)
        
        if output_file is None:
            output_file = str(input_path.with_suffix('.location.jsonl'))
            
        total_records = 0
        valid_records = 0
        gga_records = 0
        rmc_records = 0
        rinex_records = 0
        
        print("Reading and processing records...")
        with open(input_file, 'r') as f_in, open(output_file, 'w') as f_out:
            for line in f_in:
                total_records += 1
                try:
                    record = json.loads(line)
                    
                    # Process based on record type
                    location_record = None
                    
                    # Check for NMEA records
                    if 'sentence_type' in record:
                        if record['sentence_type'] == 'GGA':
                            location_record = extract_gga_location(record)
                            if location_record:
                                gga_records += 1
                        elif record['sentence_type'] == 'RMC':
                            location_record = extract_rmc_location(record)
                            if location_record:
                                rmc_records += 1
                    
                    # Check for RINEX records
                    elif 'time' in record and ('C1' in record or 'L1' in record):
                        location_record = extract_rinex_location(record)
                        if location_record:
                            rinex_records += 1
                    
                    # Write valid location record
                    if location_record and is_valid_location(location_record):
                        f_out.write(json.dumps(location_record) + '\n')
                        valid_records += 1
                        
                        # Print progress every 1000 records
                        if valid_records % 1000 == 0:
                            print(f"Processed {valid_records} valid location records...")
                    
                except json.JSONDecodeError as e:
                    print(f"Error decoding JSON at record {total_records}: {str(e)}")
                    continue
                except Exception as e:
                    print(f"Error processing record {total_records}: {str(e)}")
                    continue
        
        # Print summary
        print("\nLocation Extraction Summary:")
        print(f"- Total records processed: {total_records}")
        print(f"- Valid location records: {valid_records}")
        print(f"- GGA records: {gga_records}")
        print(f"- RMC records: {rmc_records}")
        print(f"- RINEX records: {rinex_records}")
        
        if valid_records > 0:
            print(f"\nSuccessfully extracted location data to: {output_file}")
            return output_file
        else:
            print("No valid location records found, attempting LLM extraction...")
            return extract_with_llm(input_file, output_file)
            
    except Exception as e:
        print(f"Error extracting location data: {str(e)}")
        return None

def extract_gga_location(record):
    """Extract location data from GGA message"""
    try:
        if not all(field in record for field in ['latitude', 'longitude']):
            return None
            
        location = {
            'timestamp_ms': record.get('timestamp_ms'),
            'latitude': float(record['latitude']),
            'longitude': float(record['longitude']),
            'altitude': float(record['altitude']) if 'altitude' in record else None,
            'num_satellites': int(record['num_satellites']) if 'num_satellites' in record else None,
            'hdop': float(record['hdop']) if 'hdop' in record else None,
            'quality': int(record['quality']) if 'quality' in record else None,
            'record_type': 'GGA'
        }
        return location
    except (ValueError, TypeError) as e:
        print(f"Error extracting GGA location: {str(e)}")
        return None

def extract_rmc_location(record):
    """Extract location data from RMC message"""
    try:
        if not all(field in record for field in ['latitude', 'longitude']):
            return None
            
        location = {
            'timestamp_ms': record.get('timestamp_ms'),
            'latitude': float(record['latitude']),
            'longitude': float(record['longitude']),
            'speed': float(record['speed']) if 'speed' in record else None,
            'course': float(record['course']) if 'course' in record else None,
            'record_type': 'RMC'
        }
        return location
    except (ValueError, TypeError) as e:
        print(f"Error extracting RMC location: {str(e)}")
        return None

def extract_rinex_location(record):
    """Extract location data from RINEX record"""
    try:
        location = {
            'timestamp_ms': int(record['time'].timestamp() * 1000) if 'time' in record else None,
            'satellite_system': record.get('sv', '').split()[0] if record.get('sv', '') else None,
            'satellite_number': record.get('sv', '').split()[1] if record.get('sv', '') and len(record.get('sv', '').split()) > 1 else None,
            'pseudorange': float(record['C1']) if 'C1' in record else None,
            'carrier_phase': float(record['L1']) if 'L1' in record else None,
            'doppler': float(record['D1']) if 'D1' in record else None,
            'signal_strength': float(record['S1']) if 'S1' in record else None,
            'record_type': 'RINEX'
        }
        return location
    except (ValueError, TypeError, AttributeError) as e:
        print(f"Error extracting RINEX location: {str(e)}")
        return None

def is_valid_location(record):
    """Validate location record format"""
    try:
        # Check required fields
        if not all(field in record for field in ['timestamp_ms', 'record_type']):
            return False
            
        # Validate based on record type
        if record['record_type'] == 'GGA':
            return all(field in record for field in ['latitude', 'longitude'])
        elif record['record_type'] == 'RMC':
            return all(field in record for field in ['latitude', 'longitude'])
        elif record['record_type'] == 'RINEX':
            return any(field in record and record[field] is not None for field in 
                ['pseudorange', 'carrier_phase', 'doppler', 'signal_strength'])
        
        return False
        
    except Exception:
        return False

def extract_nmea_location_data(input_file):
    """Extract location data from NMEA JSONL file"""
    try:
        location_records = []
        
        with open(input_file, 'r') as f:
            for line in f:
                try:
                    data = json.loads(line)
                    record = None
                    
                    # Process GGA messages (primary source of 3D location)
                    if data.get('sentence_type') == 'GGA':
                        try:
                            lat = data.get('lat', '')
                            lat_dir = data.get('lat_dir', '')
                            lon = data.get('lon', '')
                            lon_dir = data.get('lon_dir', '')
                            
                            if lat and lon:
                                # Convert coordinates
                                latitude, longitude = convert_nmea_coordinates(lat, lat_dir, lon, lon_dir)
                                
                                if latitude is not None and longitude is not None:
                                    record = {
                                        'timestamp_ms': data.get('timestamp_ms'),
                                        'latitude': latitude,
                                        'longitude': longitude,
                                        'altitude': float(data.get('altitude', 0)),
                                        'num_satellites': int(data.get('num_sats', 0)),
                                        'hdop': float(data.get('horizontal_dil', 0)),
                                        'quality': int(data.get('gps_qual', 0))
                                    }
                        except (ValueError, TypeError):
                            continue
                            
                    # Process RMC messages (adds speed and course)
                    elif data.get('sentence_type') == 'RMC':
                        try:
                            lat = data.get('lat', '')
                            lat_dir = data.get('lat_dir', '')
                            lon = data.get('lon', '')
                            lon_dir = data.get('lon_dir', '')
                            
                            if lat and lon:
                                # Convert coordinates
                                latitude, longitude = convert_nmea_coordinates(lat, lat_dir, lon, lon_dir)
                                
                                if latitude is not None and longitude is not None:
                                    record = {
                                        'timestamp_ms': data.get('timestamp_ms'),
                                        'latitude': latitude,
                                        'longitude': longitude,
                                        'speed': float(data.get('spd_over_grnd', 0)),
                                        'course': float(data.get('true_course', 0))
                                    }
                        except (ValueError, TypeError):
                            continue
                    
                    if record:
                        location_records.append(record)
                        
                except json.JSONDecodeError:
                    continue
                except Exception as e:
                    print(f"Error processing line: {e}")
                    continue
                    
        return len(location_records) > 0, location_records
        
    except Exception as e:
        print(f"Error extracting NMEA location data: {str(e)}")
        return False, []

def extract_rinex_location_data(input_file):
    """Extract location data from RINEX JSONL file"""
    try:
        location_records = []
        
        with open(input_file, 'r') as f:
            for line in f:
                try:
                    data = json.loads(line)
                    
                    # Extract satellite system and number
                    sv = data.get('sv', '')
                    if isinstance(sv, str) and ' ' in sv:
                        sat_sys, sat_num = sv.split()
                    else:
                        sat_sys = sv[:1] if isinstance(sv, str) and sv else None
                        sat_num = sv[1:] if isinstance(sv, str) and len(sv) > 1 else None
                    
                    if sat_sys and sat_num:
                        # Create standardized record
                        record = {
                            'timestamp_ms': int(data['time'].timestamp() * 1000),
                            'satellite_system': sat_sys,
                            'satellite_number': sat_num
                        }
                        
                        # Add observation data if available
                        if 'C1' in data:
                            record['pseudorange'] = float(data['C1'])
                        if 'L1' in data:
                            record['carrier_phase'] = float(data['L1'])
                        if 'D1' in data:
                            record['doppler'] = float(data['D1'])
                        if 'S1' in data:
                            record['signal_strength'] = float(data['S1'])
                            
                        location_records.append(record)
                        
                except json.JSONDecodeError:
                    continue
                except Exception as e:
                    print(f"Error processing line: {e}")
                    continue
                    
        return len(location_records) > 0, location_records
        
    except Exception as e:
        print(f"Error extracting RINEX location data: {str(e)}")
        return False, []

def convert_nmea_coordinates(lat, lat_dir, lon, lon_dir):
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

def extract_with_llm(input_file, output_file):
    """Extract location data using LLM when standard parsing fails"""
    print("Starting LLM-based location extraction...")
    
    try:
        # Read sample data for analysis
        with open(input_file, 'r') as f:
            sample_data = []
            for i, line in enumerate(f):
                if i < 5:  # Read first 5 lines as sample
                    sample_data.append(line.strip())
                else:
                    break
                    
        # Request location extraction from LLM
        messages = [
            {"role": "system", "content": "You are a helpful assistant that analyzes GNSS data formats and extracts location information."},
            {"role": "user", "content": f"Here is a sample of the data:\n{chr(10).join(sample_data)}\n\nPlease generate Python code to process this format and extract location data."}
        ]
        
        max_attempts = 10
        for attempt in range(max_attempts):
            try:
                response = client.chat.completions.create(
                    model=os.getenv('AZURE_OPENAI_ENGINE'),
                    messages=messages,
                    temperature=0.7,
                    max_tokens=2000
                )
                
                # Extract and execute the generated code
                generated_code = response.choices[0].message.content
                print("\nGenerated code:")
                print(f"```python\n{generated_code}\n```")
                
                print("\nExecuting generated code...")
                
                # Create a local namespace for execution
                local_namespace = {}
                exec(generated_code, globals(), local_namespace)
                
                # Check if location_records were created
                if 'location_records' not in local_namespace:
                    print("No location_records variable was created")
                    print(f"\nProcessing attempt {attempt + 1} of {max_attempts}")
                    print("Generating processing code...")
                    continue
                    
                # Validate the records
                records = local_namespace['location_records']
                if validate_location_records(records):
                    print("Records validated successfully, saving to file...")
                    with open(output_file, 'w') as f:
                        for record in records:
                            f.write(json.dumps(record) + '\n')
                    print(f"Successfully processed {len(records)} records")
                    return output_file
                else:
                    print("Generated records failed validation")
                    print(f"\nProcessing attempt {attempt + 1} of {max_attempts}")
                    print("Generating processing code...")
                    
            except Exception as e:
                print(f"Attempt {attempt + 1} failed: {str(e)}")
                if attempt < max_attempts - 1:
                    print(f"\nProcessing attempt {attempt + 2} of {max_attempts}")
                    print("Generating processing code...")
                continue
                
        print(f"Failed to generate valid output after {max_attempts} attempts")
        return None
        
    except Exception as e:
        print(f"Error in LLM extraction: {str(e)}")
        return None

def validate_location_record(record):
    """Validate if a location record has the required fields"""
    if not isinstance(record, dict):
        return False
        
    # Check for required fields based on format type
    if 'satellite_system' in record:
        # RINEX format
        required_fields = ['timestamp_ms', 'satellite_system', 'satellite_number']
        optional_fields = ['pseudorange', 'carrier_phase', 'doppler', 'signal_strength',
                         'computed_latitude', 'computed_longitude', 'computed_altitude']
    else:
        # NMEA format
        required_fields = ['timestamp_ms']
        optional_fields = ['latitude', 'longitude', 'altitude', 'num_satellites',
                         'hdop', 'quality', 'speed', 'course']
    
    # Check required fields
    if not all(field in record for field in required_fields):
        return False
        
    # Check that at least some optional fields are present
    if not any(field in record for field in optional_fields):
        return False
        
    # Validate timestamp
    try:
        timestamp = int(record['timestamp_ms'])
        if timestamp <= 0:
            return False
    except (ValueError, TypeError):
        return False
    
    return True 