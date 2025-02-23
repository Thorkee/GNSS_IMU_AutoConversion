# GNSS IMU Auto Conversion

An intelligent GNSS data conversion tool that uses Azure OpenAI to automatically process various GNSS data formats and extract location information for Factor Graph Optimization (FGO).

## Features

- **Automatic Format Detection**: Uses Azure OpenAI to analyze and identify unknown GNSS data formats
- **Multiple Format Support**:
  - RINEX observation files (.obs)
  - NMEA files (.nmea)
  - UBX format (auto-detected)
  - Other common GNSS formats (auto-detected)
- **Intelligent Data Extraction**:
  - Extracts only location-relevant data needed for FGO
  - Standardizes output format across different input types
- **Web Interface**:
  - Drag-and-drop file upload
  - Multiple file upload support
  - Real-time processing status
  - Easy download of converted files
- **Background Processing**:
  - Asynchronous processing using Celery
  - Progress tracking
  - Error handling and recovery

## Installation

1. Clone the repository:
```bash
git clone https://github.com/Thorkee/GNSS_IMU_AutoConversion.git
cd GNSS_IMU_AutoConversion
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables in `.env`:
```env
AZURE_OPENAI_ENDPOINT=your_endpoint_here
AZURE_OPENAI_API_KEY=your_api_key_here
AZURE_OPENAI_ENGINE=your_deployment_name_here
AZURE_OPENAI_API_VERSION=2023-05-15
```

## Running the Application

1. Start Redis server (required for Celery):
```bash
redis-server
```

2. Start Celery worker:
```bash
celery -A app.celery worker --loglevel=info
```

3. Start the Flask application:
```bash
python app.py
```

The web interface will be available at `http://localhost:5000`

## Output Format

The tool converts all input formats to a standardized JSONL format containing only location-relevant data:

```json
{
    "timestamp_ms": 1621218691991,
    "latitude": 22.301210,
    "longitude": 114.178993,
    "altitude": 10.9,
    "num_satellites": 7,
    "hdop": 1.0,
    "quality": 1
}
```

Additional fields may include:
- `satellite_system`: GNSS system identifier
- `pseudorange`: Pseudorange measurements
- `carrier_phase`: Carrier phase measurements
- `doppler`: Doppler measurements
- `signal_strength`: Signal strength indicators
- `speed`: Ground speed (when available)
- `course`: True course (when available)

## Supported Input Formats

### RINEX Observation Files (.obs)
- Standard RINEX 2.x and 3.x formats
- Extracts pseudorange, carrier phase, and satellite information

### NMEA Files (.nmea)
- GGA messages (primary position data)
- RMC messages (recommended minimum data)
- GNS messages (GNSS fix data)
- GSV messages (satellite data)

### Auto-detected Formats
The AI can analyze and process various other formats by:
1. Analyzing file structure and content
2. Identifying relevant fields and their positions
3. Extracting location-related data
4. Converting to standardized format

## Error Handling

- Invalid file format detection
- Missing or corrupted data handling
- Processing error recovery
- User-friendly error messages

## Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a new Pull Request

## License

MIT License

## Acknowledgments

- Azure OpenAI for format detection
- georinex for RINEX file processing
- pynmea2 for NMEA file processing
