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

# Load environment variables
load_dotenv()

class GNSSProcessor:
    def __init__(self):
        self.supported_formats = {
            '.obs': self.process_rinex,
            '.nmea': self.process_nmea,
        }
        
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
        # Read RINEX data
        obs_data = gr.load(input_file)
        df = obs_data.to_dataframe().reset_index()
        
        # Filter for location-related data
        location_records = []
        for _, row in df.iterrows():
            record = {
                'timestamp': row.get('time'),
                'satellite_system': row.get('sv', '').split()[0] if isinstance(row.get('sv'), str) else None,
                'satellite_number': row.get('sv', '').split()[1] if isinstance(row.get('sv'), str) else None,
                'pseudorange': float(row.get('C1', 0)),
                'carrier_phase': float(row.get('L1', 0)),
                'doppler': float(row.get('D1', 0)) if 'D1' in row else None,
                'signal_strength': float(row.get('S1', 0)) if 'S1' in row else None
            }
            location_records.append(record)
        
        return location_records

    def process_nmea(self, input_file):
        """Process NMEA file"""
        location_records = []
        
        with open(input_file, 'r') as f:
            for line in f:
                try:
                    # Split the line to separate NMEA message and timestamp
                    parts = line.strip().split(',')
                    if len(parts) > 1:
                        nmea_msg = ','.join(parts[:-1])
                        timestamp = int(parts[-1]) if parts[-1].isdigit() else None
                        
                        msg = pynmea2.parse(nmea_msg)
                        
                        # Extract location data from GGA, RMC, or GNS messages
                        if msg.sentence_type in ['GGA', 'RMC', 'GNS']:
                            record = self.extract_location_data(msg, timestamp)
                            if record:
                                location_records.append(record)
                                
                except (pynmea2.ParseError, ValueError):
                    continue
                
        return location_records

    def extract_location_data(self, msg, timestamp=None):
        """Extract location data from NMEA message"""
        if not hasattr(msg, 'latitude') or not hasattr(msg, 'longitude'):
            return None

        record = {
            'timestamp_ms': timestamp,
            'latitude': float(msg.latitude) if msg.latitude else None,
            'longitude': float(msg.longitude) if msg.longitude else None,
        }

        # Add additional fields based on message type
        if msg.sentence_type == 'GGA':
            record.update({
                'altitude': float(msg.altitude) if hasattr(msg, 'altitude') else None,
                'num_satellites': int(msg.num_sats) if hasattr(msg, 'num_sats') else None,
                'hdop': float(msg.horizontal_dil) if hasattr(msg, 'horizontal_dil') else None,
                'quality': msg.gps_qual if hasattr(msg, 'gps_qual') else None
            })
        elif msg.sentence_type == 'RMC':
            record.update({
                'speed': float(msg.spd_over_grnd) if hasattr(msg, 'spd_over_grnd') else None,
                'course': float(msg.true_course) if hasattr(msg, 'true_course') else None,
                'date': msg.datestamp.isoformat() if hasattr(msg, 'datestamp') else None
            })

        return record

    def analyze_format(self, sample_content):
        """Use Azure OpenAI to analyze the file format"""
        response = openai.ChatCompletion.create(
            engine=os.getenv('AZURE_OPENAI_ENGINE'),
            messages=[
                {
                    "role": "system",
                    "content": """You are a GNSS data format expert. Analyze the data and identify its format.
                    Focus on identifying these aspects:
                    1. File format (RINEX, NMEA, UBX, etc.)
                    2. Location-related fields (coordinates, altitude, satellites, etc.)
                    3. Data structure and field positions
                    Respond in JSON format with these keys: format, fields, structure"""
                },
                {
                    "role": "user",
                    "content": f"Analyze this GNSS data sample:\n{sample_content}"
                }
            ]
        )
        
        try:
            analysis = json.loads(response.choices[0].message.content)
            return analysis
        except json.JSONDecodeError:
            return {'format': 'unknown', 'fields': [], 'structure': 'unknown'}

    def process_unknown_format(self, input_file, analysis):
        """Process file based on AI analysis"""
        location_records = []
        
        with open(input_file, 'r') as f:
            for line in f:
                try:
                    # Apply the structure identified by AI to parse the line
                    if analysis['format'].lower() == 'ubx':
                        record = self.parse_ubx_line(line, analysis['structure'])
                    else:
                        record = self.parse_generic_line(line, analysis['structure'])
                    
                    if record:
                        location_records.append(record)
                except Exception:
                    continue
                    
        return location_records

    def process_file(self, input_file):
        """Main method to process GNSS data file"""
        file_ext = Path(input_file).suffix.lower()
        
        # Use predefined processor for known formats
        if file_ext in self.supported_formats:
            location_records = self.supported_formats[file_ext](input_file)
        else:
            # Analyze unknown format using AI
            with open(input_file, 'r') as f:
                sample_content = f.read(1000)
            analysis = self.analyze_format(sample_content)
            location_records = self.process_unknown_format(input_file, analysis)
        
        # Save to JSONL
        output_file = str(Path(input_file).with_suffix('.location.jsonl'))
        with open(output_file, 'w') as f:
            for record in location_records:
                f.write(json.dumps(record, default=self.custom_serializer) + '\n')
        
        return output_file 