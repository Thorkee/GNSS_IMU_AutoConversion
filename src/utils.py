import json
from datetime import datetime, time, date
from decimal import Decimal
import argparse

def custom_serializer(obj):
    """Custom JSON serializer for objects not serializable by default json code"""
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

def setup_argument_parser(description):
    """Set up common command line arguments"""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('--input', required=True, help='Input file path')
    parser.add_argument('--output', required=True, help='Output file path')
    return parser

# Added helper function for truncating text to a max token count (approximation using whitespace splitting)
def truncate_text_by_tokens(text: str, max_tokens: int = 10000) -> str:
    """Truncate the given text to at most max_tokens tokens. Tokens are approximated by splitting on whitespace."""
    tokens = text.split()
    if len(tokens) > max_tokens:
        return ' '.join(tokens[:max_tokens])
    return text 