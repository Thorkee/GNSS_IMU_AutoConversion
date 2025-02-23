#!/usr/bin/env python3
import georinex as gr
import json
import pandas as pd
from utils import custom_serializer, setup_argument_parser

def convert_rinex_to_jsonl(input_file, output_file):
    """Convert RINEX observation file to JSONL format"""
    try:
        print(f"Reading RINEX file: {input_file}")
        # Read the RINEX observation file into an xarray.Dataset
        obs_data = gr.load(input_file)

        print("Converting to DataFrame...")
        # Convert the xarray.Dataset to a pandas DataFrame
        df = obs_data.to_dataframe().reset_index()

        print("Writing to JSONL file...")
        # Write the DataFrame to a JSONL file
        with open(output_file, 'w') as f:
            for record in df.to_dict(orient='records'):
                f.write(json.dumps(record, default=custom_serializer) + '\n')

        print(f"Conversion complete. JSONL file saved to {output_file}")
        return True

    except FileNotFoundError:
        print(f"Error: Could not find the input file at {input_file}")
        return False
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return False

def main():
    parser = setup_argument_parser("Convert RINEX observation file to JSONL format")
    args = parser.parse_args()
    
    convert_rinex_to_jsonl(args.input, args.output)

if __name__ == "__main__":
    main() 