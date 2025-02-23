import georinex as gr
import json
import pandas as pd

try:
    # Define the input and output file paths
    input_file = '/Users/julin/Downloads/FYP/UrbanNav/Data/1_UrbanNav-HK-Medium-Urban-1/UrbanNav-HK-Medium-Urban-1.google.pixel4.obs'
    output_file = '/Users/julin/Downloads/FYP/UrbanNav/Data/1_UrbanNav-HK-Medium-Urban-1/UrbanNav-HK-Medium-Urban-1.google.pixel4.jsonl'

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
            f.write(json.dumps(record) + '\n')

    print(f"Conversion complete. JSONL file saved to {output_file}")

except FileNotFoundError:
    print(f"Error: Could not find the input file at {input_file}")
except Exception as e:
    print(f"An error occurred: {str(e)}")