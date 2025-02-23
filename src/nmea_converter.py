#!/usr/bin/env python3
import pynmea2
import json
from utils import custom_serializer, setup_argument_parser

def nmea_to_dict(msg, timestamp=None):
    """Convert NMEA message to dictionary, handling datetime objects."""
    data = {}
    for field in msg.fields:
        value = getattr(msg, field[1])
        data[field[1]] = value
    # Add sentence type and timestamp
    data['sentence_type'] = msg.sentence_type
    if timestamp is not None:
        data['timestamp_ms'] = timestamp
    return data

def convert_nmea_to_jsonl(input_file, output_file):
    """Convert NMEA file to JSONL format"""
    try:
        print(f"Reading NMEA file: {input_file}")
        valid_count = 0
        total_count = 0
        
        with open(input_file, 'r') as nmea_file, open(output_file, 'w') as jsonl_file:
            for line in nmea_file:
                total_count += 1
                try:
                    # Split the line to separate NMEA message and timestamp
                    parts = line.strip().split(',')
                    if len(parts) > 1:
                        # Reconstruct the NMEA message without the timestamp
                        nmea_msg = ','.join(parts[:-1])
                        timestamp = int(parts[-1]) if parts[-1].isdigit() else None
                        
                        # Parse NMEA message
                        msg = pynmea2.parse(nmea_msg)
                        
                        # Convert to dictionary and write to JSONL
                        data = nmea_to_dict(msg, timestamp)
                        jsonl_file.write(json.dumps(data, default=custom_serializer) + '\n')
                        valid_count += 1
                        
                except pynmea2.ParseError:
                    continue
                except Exception as e:
                    print(f"Error processing line: {e}")
                    continue

        print(f"Processed {total_count} lines")
        print(f"Successfully converted {valid_count} NMEA messages")
        print(f"Output saved to: {output_file}")
        return True

    except FileNotFoundError:
        print(f"Error: Could not find the input file at {input_file}")
        return False
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return False

def main():
    parser = setup_argument_parser("Convert NMEA file to JSONL format")
    args = parser.parse_args()
    
    convert_nmea_to_jsonl(args.input, args.output)

if __name__ == "__main__":
    main() 