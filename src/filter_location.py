#!/usr/bin/env python3
import json
from utils import custom_serializer, convert_nmea_coordinates, setup_argument_parser

def filter_location_data(input_file, output_file):
    """Filter JSONL file to keep only records with location data"""
    try:
        location_records = []
        
        print(f"Processing JSONL file: {input_file}")
        with open(input_file, 'r') as f:
            for line in f:
                try:
                    data = json.loads(line)
                    
                    # Process GGA messages (they have lat, lon, and altitude)
                    if data.get('sentence_type') == 'GGA':
                        lat = data.get('lat', '')
                        lat_dir = data.get('lat_dir', '')
                        lon = data.get('lon', '')
                        lon_dir = data.get('lon_dir', '')
                        altitude = data.get('altitude', None)
                        
                        if lat and lon and altitude is not None:
                            # Convert coordinates to decimal degrees
                            latitude, longitude = convert_nmea_coordinates(lat, lat_dir, lon, lon_dir)
                            
                            if latitude is not None and longitude is not None:
                                location_record = {
                                    'timestamp_ms': data.get('timestamp_ms'),
                                    'latitude': latitude,
                                    'longitude': longitude,
                                    'altitude': float(altitude),
                                    'num_sats': int(data.get('num_sats', 0)),
                                    'gps_qual': data.get('gps_qual'),
                                    'horizontal_dil': float(data.get('horizontal_dil', 0))
                                }
                                location_records.append(location_record)
                
                except (json.JSONDecodeError, ValueError) as e:
                    print(f"Error processing line: {e}")
                    continue
        
        print(f"Found {len(location_records)} location records")
        
        # Write filtered records to new JSONL file
        print(f"Writing filtered data to: {output_file}")
        with open(output_file, 'w') as f:
            for record in location_records:
                f.write(json.dumps(record, default=custom_serializer) + '\n')
        
        print("Filtering complete")
        if location_records:
            print("Sample of first record:")
            print(json.dumps(location_records[0], default=custom_serializer, indent=2))
        
        return True

    except FileNotFoundError:
        print(f"Error: Could not find the input file at {input_file}")
        return False
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return False

def main():
    parser = setup_argument_parser("Filter JSONL file to keep only location data")
    args = parser.parse_args()
    
    filter_location_data(args.input, args.output)

if __name__ == "__main__":
    main() 