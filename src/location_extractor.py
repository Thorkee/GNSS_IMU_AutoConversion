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
    base_url=f"{os.getenv('AZURE_OPENAI_ENDPOINT')}/deployments/{os.getenv('AZURE_OPENAI_ENGINE')}"
)

def validate_location_records(records):
    """Validate if location records have useful positioning data for FGO"""
    if not records:
        return False
        
    # Basic validation - each record should be a dictionary
    if not all(isinstance(record, dict) for record in records):
        return False
    
    # Each record should have at least a timestamp
    if not all('timestamp_ms' in record for record in records):
        return False
    
    # Each record should have some form of positioning data
    positioning_fields = {
        'location': ['latitude', 'longitude', 'altitude'],
        'gnss': ['satellite_system', 'satellite_number', 'pseudorange', 'carrier_phase'],
        'quality': ['hdop', 'pdop', 'num_satellites', 'fix_type', 'quality', 'accuracy'],
        'motion': ['speed', 'course', 'heading', 'velocity']
    }
    
    # Record should contain at least one field from location OR gnss categories
    # and optionally fields from quality/motion categories
    for record in records:
        has_location = any(field in record for field in positioning_fields['location'])
        has_gnss = any(field in record for field in positioning_fields['gnss'])
        if not (has_location or has_gnss):
            return False
            
        # Validate numeric fields if present
        for category in positioning_fields.values():
            for field in category:
                if field in record and record[field] is not None:
                    try:
                        float(record[field])
                    except (ValueError, TypeError):
                        return False
    
    return True

def extract_location_data(input_file, output_file=None):
    """Extract standardized location records from JSONL file"""
    try:
        print(f"Starting location data extraction from: {input_file}")
        input_path = Path(input_file)
        
        if output_file is None:
            output_file = str(input_path.with_suffix('.location.jsonl'))
            
        # Try standard extraction first
        print("Attempting standard extraction...")
        success = False
        try:
            # Try NMEA extraction with binary mode
            success, records = extract_nmea_location_data(input_file)
            if not success:
                # Try RINEX extraction
                success, records = extract_rinex_location_data(input_file)
            
            if success and records:
                # Write valid location records
                with open(output_file, 'w') as f:
                    for record in records:
                        if validate_location_record(record):
                            f.write(json.dumps(record) + '\n')
                print("Standard extraction successful")
                return output_file
        except Exception as e:
            print(f"Standard extraction failed: {str(e)}")
        
        # If standard extraction fails, try LLM extraction
        print("Standard extraction failed, attempting LLM extraction...")
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
        records = []
        # Try reading as binary first
        try:
            with open(input_file, 'rb') as f:
                content = f.read()
                # Try different encodings
                for encoding in ['utf-8', 'latin1', 'ascii']:
                    try:
                        text = content.decode(encoding)
                        break
                    except UnicodeDecodeError:
                        continue
                else:
                    # If no encoding works, try reading line by line
                    text = ''
                    for line in content.split(b'\n'):
                        try:
                            text += line.decode('utf-8', errors='ignore') + '\n'
                        except:
                            continue
        except Exception as e:
            print(f"Error reading NMEA file: {e}")
            return False, []

        # Process the text content
        for line in text.splitlines():
            try:
                if not line.strip():
                    continue
                    
                # Try parsing as JSON first
                try:
                    record = json.loads(line)
                except:
                    # If not JSON, try parsing as NMEA
                    if line.startswith('$'):
                        record = parse_nmea_sentence(line)
                    else:
                        continue
                
                if record and validate_location_record(record):
                    records.append(record)
            except Exception as e:
                print(f"Error processing line: {str(e)}")
                continue
                
        return bool(records), records
    except Exception as e:
        print(f"Error extracting NMEA data: {str(e)}")
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

def parse_nmea_sentence(sentence):
    """Parse raw NMEA sentence into a record"""
    try:
        if not sentence.startswith('$'):
            return None
            
        parts = sentence.strip().split(',')
        if len(parts) < 2:
            return None
            
        msg_type = parts[0][1:]  # Remove $
        record = {'sentence_type': msg_type}
        
        # GGA message (Global Positioning System Fix Data)
        if msg_type in ['GPGGA', 'GNGGA']:
            if len(parts) >= 15:
                try:
                    record.update({
                        'timestamp_ms': int(float(parts[1]) * 1000) if parts[1] else None,
                        'latitude': float(parts[2][:2]) + float(parts[2][2:]) / 60 if parts[2] else None,
                        'lat_dir': parts[3],
                        'longitude': float(parts[4][:3]) + float(parts[4][3:]) / 60 if parts[4] else None,
                        'lon_dir': parts[5],
                        'quality': int(parts[6]) if parts[6] else None,
                        'num_satellites': int(parts[7]) if parts[7] else None,
                        'hdop': float(parts[8]) if parts[8] else None,
                        'altitude': float(parts[9]) if parts[9] else None,
                        'altitude_units': parts[10]
                    })
                except (ValueError, IndexError):
                    return None
                    
        # RMC message (Recommended Minimum Navigation Information)
        elif msg_type in ['GPRMC', 'GNRMC']:
            if len(parts) >= 12:
                try:
                    record.update({
                        'timestamp_ms': int(float(parts[1]) * 1000) if parts[1] else None,
                        'status': parts[2],
                        'latitude': float(parts[3][:2]) + float(parts[3][2:]) / 60 if parts[3] else None,
                        'lat_dir': parts[4],
                        'longitude': float(parts[5][:3]) + float(parts[5][3:]) / 60 if parts[5] else None,
                        'lon_dir': parts[6],
                        'speed': float(parts[7]) * 0.514444 if parts[7] else None,  # Convert knots to m/s
                        'course': float(parts[8]) if parts[8] else None
                    })
                except (ValueError, IndexError):
                    return None
                    
        # GSA message (GNSS DOP and Active Satellites)
        elif msg_type in ['GPGSA', 'GNGSA']:
            if len(parts) >= 18:
                try:
                    record.update({
                        'mode': parts[1],
                        'fix_type': int(parts[2]) if parts[2] else None,
                        'pdop': float(parts[15]) if parts[15] else None,
                        'hdop': float(parts[16]) if parts[16] else None,
                        'vdop': float(parts[17]) if parts[17] else None
                    })
                except (ValueError, IndexError):
                    return None
                    
        return record
    except Exception:
        return None

def extract_with_llm(input_file, output_file):
    """Use LLM to extract location data from file"""
    try:
        print("Starting LLM-based extraction...")
        
        # Read sample data for analysis
        print("Reading sample data...")
        sample_lines = []
        unique_message_types = set()
        
        try:
            with open(input_file, 'rb') as f:
                content = f.read()
                # Try different encodings
                for encoding in ['utf-8', 'latin1', 'ascii']:
                    try:
                        text = content.decode(encoding)
                        break
                    except UnicodeDecodeError:
                        continue
                else:
                    text = content.decode('utf-8', errors='ignore')
                
                # Get first 15 lines minimum
                lines = text.splitlines()[:15]
                sample_lines.extend(lines)
                
                # Look for more unique message types up to 25 lines total
                if len(lines) > 15:
                    for line in lines[15:]:
                        if len(sample_lines) >= 25:
                            break
                        try:
                            if line.startswith('$'):
                                msg_type = line.split(',')[0][1:]
                                if msg_type not in unique_message_types:
                                    unique_message_types.add(msg_type)
                                    sample_lines.append(line)
                            else:
                                record = json.loads(line)
                                msg_type = record.get('sentence_type')
                                if msg_type not in unique_message_types:
                                    unique_message_types.add(msg_type)
                                    sample_lines.append(line)
                        except:
                            continue
                            
        except Exception as e:
            print(f"Error reading sample data: {e}")
            return None
            
        print(f"Collected {len(sample_lines)} sample lines")
        sample_data = '\n'.join(sample_lines)
        
        # Request format analysis from LLM with reduced token limit
        system_message = """You are a GNSS data processing expert. Analyze the sample data and generate Python code to extract location records.
Focus on extracting: timestamp_ms, latitude, longitude, altitude, speed, course, and quality indicators (hdop, pdop, num_satellites).
The code should handle both JSON and raw NMEA formats. Return only the Python code block with no additional text."""

        max_attempts = 10
        for attempt in range(max_attempts):
            try:
                print(f"\nProcessing attempt {attempt + 1} of {max_attempts}")
                print("Generating processing code...")
                
                response = client.chat.completions.create(
                    model=os.getenv('AZURE_OPENAI_MODEL'),
                    messages=[
                        {"role": "system", "content": system_message},
                        {"role": "user", "content": f"Sample data:\n{sample_data}\n\nGenerate Python code to process this data format."}
                    ],
                    temperature=0.7,
                    max_tokens=10000,  # Updated from 2000
                    n=1
                )
                
                if not response.choices:
                    continue
                    
                generated_code = response.choices[0].message.content
                print("\nGenerated code:")
                print("```python")
                print(generated_code)
                print("```")
                
                # Extract code block if present
                if '```python' in generated_code:
                    code_to_exec = generated_code.split('```python')[1].split('```')[0]
                else:
                    code_to_exec = generated_code

                print("\nExecuting generated code...")

                # Execute only the code block content
                local_vars = {'INPUT_FILE': input_file, 'OUTPUT_FILE': output_file}
                exec(code_to_exec, globals(), local_vars)
                
                # Verify the results
                if os.path.exists(output_file):
                    with open(output_file, 'r') as f:
                        records = [json.loads(line) for line in f]
                    if validate_location_records(records):
                        print("LLM extraction successful")
                        return output_file
                        
            except Exception as e:
                print(f"Attempt {attempt + 1} failed: {str(e)}")
                
        print("Failed to generate valid output after 10 attempts")
        return None
        
    except Exception as e:
        print(f"Error in LLM extraction: {str(e)}")
        return None

def validate_location_record(record):
    """Validate a single location record"""
    try:
        # Basic validation
        if not isinstance(record, dict):
            return False
            
        # Must have timestamp
        if 'timestamp_ms' not in record:
            return False
            
        # Check for positioning data
        has_position = False
        
        # Direct position
        if all(field in record for field in ['latitude', 'longitude']):
            try:
                lat = float(record['latitude'])
                lon = float(record['longitude'])
                if -90 <= lat <= 90 and -180 <= lon <= 180:
                    has_position = True
                    
                # Validate altitude if present
                if 'altitude' in record and record['altitude'] is not None:
                    alt = float(record['altitude'])
                    if not (-1000 <= alt <= 9000):  # Reasonable altitude range in meters
                        return False
            except (ValueError, TypeError):
                return False
                
        # GNSS raw measurements
        if all(field in record for field in ['pseudorange', 'carrier_phase']):
            try:
                float(record['pseudorange'])
                float(record['carrier_phase'])
                has_position = True
            except (ValueError, TypeError):
                pass
                
        if not has_position:
            return False
            
        # Validate quality indicators if present
        if 'hdop' in record and record['hdop'] is not None:
            try:
                hdop = float(record['hdop'])
                if not (0 <= hdop <= 50):  # Reasonable HDOP range
                    return False
            except (ValueError, TypeError):
                return False
                
        if 'pdop' in record and record['pdop'] is not None:
            try:
                pdop = float(record['pdop'])
                if not (0 <= pdop <= 50):  # Reasonable PDOP range
                    return False
            except (ValueError, TypeError):
                return False
                
        if 'num_satellites' in record and record['num_satellites'] is not None:
            try:
                num_sats = int(record['num_satellites'])
                if not (0 <= num_sats <= 50):  # Reasonable number of satellites
                    return False
            except (ValueError, TypeError):
                return False
                
        # Validate motion data if present
        if 'speed' in record and record['speed'] is not None:
            try:
                speed = float(record['speed'])
                if not (0 <= speed <= 278):  # Max speed ~1000 km/h in m/s
                    return False
            except (ValueError, TypeError):
                return False
                
        if 'course' in record and record['course'] is not None:
            try:
                course = float(record['course'])
                if not (0 <= course <= 360):  # Course in degrees
                    return False
            except (ValueError, TypeError):
                return False
                
        return True
        
    except Exception:
        return False

def _validate_coordinates(latitude, longitude, altitude=None):
    """Validate coordinate ranges"""
    try:
        lat = float(latitude)
        lon = float(longitude)
        
        # Check latitude range (-90 to 90)
        if lat < -90 or lat > 90:
            return False
            
        # Check longitude range (-180 to 180)
        if lon < -180 or lon > 180:
            return False
            
        # Check altitude if provided (reasonable range check)
        if altitude is not None:
            alt = float(altitude)
            # Most GNSS applications work between -1000m (Dead Sea) and 9000m (Mount Everest)
            if alt < -1000 or alt > 9000:
                return False
                
        return True
    except (ValueError, TypeError):
        return False

def _validate_speed(speed):
    """Validate speed value (in m/s)"""
    try:
        spd = float(speed)
        # Maximum reasonable speed for most applications (about 1000 km/h)
        return 0 <= spd <= 278
    except (ValueError, TypeError):
        return False

def _validate_course(course):
    """Validate course/bearing value (in degrees)"""
    try:
        crs = float(course)
        return 0 <= crs <= 360
    except (ValueError, TypeError):
        return False

def _validate_accuracy(accuracy):
    """Validate accuracy value (in meters)"""
    try:
        acc = float(accuracy)
        # Maximum reasonable accuracy value (1km)
        return 0 <= acc <= 1000
    except (ValueError, TypeError):
        return False

def _validate_pdop(pdop):
    """Validate PDOP (Position Dilution of Precision) value"""
    try:
        pd = float(pdop)
        # PDOP values: <2 excellent, 2-5 good, 5-10 moderate, >10 poor
        return 0 < pd <= 50
    except (ValueError, TypeError):
        return False

def _validate_android_record(record):
    """Validate Android-specific location record"""
    required_fields = ['latitude', 'longitude', 'provider']
    if not all(field in record for field in required_fields):
        return False
        
    try:
        # Validate coordinates
        if not _validate_coordinates(record['latitude'], record['longitude'],
                                   record.get('altitude')):
            return False
            
        # Validate optional fields
        if 'accuracy' in record and not _validate_accuracy(record['accuracy']):
            return False
        if 'speed' in record and not _validate_speed(record['speed']):
            return False
        if 'bearing' in record and not _validate_course(record['bearing']):
            return False
            
        return True
    except (ValueError, TypeError):
        return False

def _validate_huawei_record(record):
    """Validate Huawei-specific location record"""
    required_fields = ['latitude', 'longitude', 'accuracy']
    if not all(field in record for field in required_fields):
        return False
        
    try:
        # Validate coordinates
        if not _validate_coordinates(record['latitude'], record['longitude'],
                                   record.get('altitude')):
            return False
            
        # Validate accuracy
        if not _validate_accuracy(record['accuracy']):
            return False
            
        # Validate optional fields
        if 'speed' in record and not _validate_speed(record['speed']):
            return False
            
        return True
    except (ValueError, TypeError):
        return False

def _validate_ublox_record(record):
    """Validate u-blox-specific location record"""
    required_fields = ['latitude', 'longitude', 'fix_type']
    if not all(field in record for field in required_fields):
        return False
        
    try:
        # Validate coordinates
        if not _validate_coordinates(record['latitude'], record['longitude'],
                                   record.get('altitude')):
            return False
            
        # Validate fix type (0=no fix, 1=dead reckoning, 2=2D, 3=3D, 4=GNSS+dead reckoning, 5=time only)
        fix_type = int(record['fix_type'])
        if not 0 <= fix_type <= 5:
            return False
            
        # Validate optional fields
        if 'num_sv' in record:
            num_sv = int(record['num_sv'])
            if not 0 <= num_sv <= 50:  # Maximum reasonable number of satellites
                return False
                
        if 'pdop' in record and not _validate_pdop(record['pdop']):
            return False
            
        return True
    except (ValueError, TypeError):
        return False

def _validate_ios_record(record):
    """Validate iOS-specific location record"""
    required_fields = ['latitude', 'longitude', 'altitude']
    if not all(field in record for field in required_fields):
        return False
        
    try:
        # Validate coordinates
        if not _validate_coordinates(record['latitude'], record['longitude'],
                                   record['altitude']):
            return False
            
        # Validate optional fields
        if 'course' in record and not _validate_course(record['course']):
            return False
        if 'speed' in record and not _validate_speed(record['speed']):
            return False
        if 'h_accuracy' in record and not _validate_accuracy(record['h_accuracy']):
            return False
        if 'v_accuracy' in record and not _validate_accuracy(record['v_accuracy']):
            return False
            
        return True
    except (ValueError, TypeError):
        return False

def _validate_rinex_record(record):
    """Validate RINEX-specific location record"""
    required_fields = ['satellite_system', 'satellite_number']
    if not all(field in record for field in required_fields):
        return False
        
    try:
        if 'pseudorange' in record:
            float(record['pseudorange'])
        if 'carrier_phase' in record:
            float(record['carrier_phase'])
        if 'doppler' in record:
            float(record['doppler'])
        if 'signal_strength' in record:
            float(record['signal_strength'])
        return True
    except (ValueError, TypeError):
        return False

def _validate_nmea_record(record):
    """Validate NMEA-specific location record"""
    required_fields = ['latitude', 'longitude']
    if not all(field in record for field in required_fields):
        return False
        
    try:
        float(record['latitude'])
        float(record['longitude'])
        if 'altitude' in record:
            float(record['altitude'])
        if 'num_satellites' in record:
            int(record['num_satellites'])
        if 'hdop' in record:
            float(record['hdop'])
        if 'quality' in record:
            int(record['quality'])
        return True
    except (ValueError, TypeError):
        return False 