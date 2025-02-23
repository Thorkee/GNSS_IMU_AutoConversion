# GNSS IMU Auto Conversion

This repository contains tools for converting GNSS and IMU data files to standardized JSONL format.

## Features

- Convert RINEX observation files to JSONL
- Convert NMEA files to JSONL
- Filter and extract location data (latitude, longitude, altitude)
- Standardized output format with timestamps

## Requirements

```bash
pip install -r requirements.txt
```

## Usage

### Converting RINEX files

```bash
python src/rinex_converter.py --input path/to/input.obs --output path/to/output.jsonl
```

### Converting NMEA files

```bash
python src/nmea_converter.py --input path/to/input.nmea --output path/to/output.jsonl
```

### Filtering Location Data

```bash
python src/filter_location.py --input path/to/input.jsonl --output path/to/output.jsonl
```

## Output Format

The filtered location data contains the following fields:
- timestamp_ms: Unix timestamp in milliseconds
- latitude: Decimal degrees (WGS84)
- longitude: Decimal degrees (WGS84)
- altitude: Meters above sea level
- num_sats: Number of satellites used
- gps_qual: GPS quality indicator
- horizontal_dil: Horizontal dilution of precision

## License

MIT License 