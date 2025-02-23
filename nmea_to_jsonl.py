import pynmea2
import json
from datetime import datetime, time, date
from decimal import Decimal
import os
from collections import Counter

def custom_serializer(obj):
    """Custom JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, (datetime, time, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

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

try:
    # Define the input and output file paths
    input_file = '/Users/julin/Downloads/FYP/UrbanNav/Data/1_UrbanNav-HK-Medium-Urban-1/UrbanNav-HK-Medium-Urban-1.google.pixel4.nmea'

    print(f"Reading NMEA file: {input_file}")
    
    # Process NMEA file to analyze message types
    sentence_types = Counter()
    sample_messages = {}
    
    with open(input_file, 'r') as nmea_file:
        for line in nmea_file:
            try:
                # Split the line to separate NMEA message and timestamp
                parts = line.strip().split(',')
                if len(parts) > 1:
                    # Reconstruct the NMEA message without the timestamp
                    nmea_msg = ','.join(parts[:-1])
                    # Parse NMEA message
                    msg = pynmea2.parse(nmea_msg)
                    sentence_types[msg.sentence_type] += 1
                    
                    # Store a sample message for each type if we haven't seen it before
                    if msg.sentence_type not in sample_messages:
                        sample_messages[msg.sentence_type] = msg
                        
            except Exception:
                continue

    print("\nNMEA Message Types Found:")
    for sentence_type, count in sentence_types.most_common():
        print(f"\n{sentence_type}: {count} messages")
        msg = sample_messages[sentence_type]
        print("Fields available:")
        for field in msg.fields:
            value = getattr(msg, field[1])
            print(f"  - {field[1]}: {value}")

except FileNotFoundError:
    print(f"Error: Could not find the input file at {input_file}")
except Exception as e:
    print(f"An error occurred: {str(e)}")

try:
    # Define the input and output file paths
    output_file = '/Users/julin/Downloads/FYP/UrbanNav/Data/1_UrbanNav-HK-Medium-Urban-1/UrbanNav-HK-Medium-Urban-1.google.pixel4.nmea.jsonl'

    print(f"Reading JSONL file: {output_file}")
    
    # Read first few records of each message type
    message_samples = {}
    
    with open(output_file, 'r') as jsonl_file:
        for i, line in enumerate(jsonl_file):
            if i > 1000:  # Only check first 1000 lines to get samples
                break
                
            data = json.loads(line)
            sentence_type = data.get('sentence_type')
            
            if sentence_type and sentence_type not in message_samples:
                message_samples[sentence_type] = data
                
    print("\nContents of JSONL file:")
    for sentence_type, data in message_samples.items():
        print(f"\n{sentence_type} message sample:")
        # Print all fields except for empty ones
        for key, value in data.items():
            if value is not None and value != '':
                print(f"  - {key}: {value}")

except FileNotFoundError:
    print(f"Error: Could not find the JSONL file at {output_file}")
except Exception as e:
    print(f"An error occurred: {str(e)}") 