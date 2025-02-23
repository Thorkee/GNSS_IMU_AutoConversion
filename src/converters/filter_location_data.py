import json
from decimal import Decimal
from datetime import datetime, time, date

def custom_serializer(obj):
    if isinstance(obj, (datetime, time, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

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

def process_location_data():
    input_file = '/Users/julin/Downloads/FYP/UrbanNav/Data/Processed_JSON/UrbanNav-HK-Medium-Urban-1.google.pixel4.nmea.jsonl'
    output_file = '/Users/julin/Downloads/FYP/UrbanNav/Data/Processed_JSON/UrbanNav-HK-Medium-Urban-1.google.pixel4.location.jsonl'
    
    location_records = []
    
    print("Processing JSONL file...")
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
    print("Writing filtered data to new JSONL file...")
    with open(output_file, 'w') as f:
        for record in location_records:
            f.write(json.dumps(record, default=custom_serializer) + '\n')
    
    print(f"Filtered location data saved to: {output_file}")
    print(f"Sample of first record:")
    if location_records:
        print(json.dumps(location_records[0], default=custom_serializer, indent=2))

if __name__ == "__main__":
    process_location_data() 