# GNSS Data Processing System

A robust system for processing various GNSS (Global Navigation Satellite System) data formats, with automatic format detection and conversion capabilities.

## System Architecture

The system consists of several key components:

1. Web Interface (Flask)
2. Task Queue (Celery)
3. Message Broker (Redis)
4. Processing Pipeline
5. Format Converters
6. Location Data Extractors

## Processing Pipeline

### 1. File Upload and Initial Processing
- User uploads GNSS data file through web interface
- System generates unique task ID
- File is saved to temporary storage
- Processing task is queued in Celery

### 2. Format Detection and Conversion
The system supports multiple GNSS data formats:

#### a. RINEX (.obs files)
- Reads RINEX observation file using `georinex`
- Converts to DataFrame with standardized fields
- Adds timestamp_ms for temporal alignment
- Validates data structure and required fields
- Outputs to JSONL format
- **LLM Fallback**: If standard conversion fails, uses format-specific LLM for:
  - RINEX structure analysis
  - Observation data parsing
  - Timestamp conversion
  - Field extraction and validation
  - Up to 10 retry attempts with error feedback

#### b. NMEA (.nmea files)
- Processes NMEA sentences using `pynmea2`
- Handles common message types (GGA, RMC)
- Extracts timestamps and coordinates
- Validates message integrity
- Converts to standardized JSONL format
- **LLM Fallback**: If standard conversion fails, uses format-specific LLM for:
  - NMEA sentence parsing
  - GGA/RMC message extraction
  - Coordinate conversion
  - Field validation
  - Up to 10 retry attempts with error feedback

#### c. Unknown Formats
- Samples file content for analysis
- Uses LLM (Language Model) to:
  - Detect format structure
  - Generate conversion logic
  - Extract relevant fields
- Converts to standardized JSONL format
- Implements retry mechanism with:
  - Error analysis and feedback
  - Iterative improvement
  - Maximum 10 attempts

### 3. Location Data Extraction
Processes standardized JSONL files to extract:

#### a. NMEA-derived Location Data
- GGA (Global Positioning Fix Data)
  - Latitude/Longitude
  - Altitude
  - Number of satellites
  - HDOP (Horizontal Dilution of Precision)
  - Fix quality
- RMC (Recommended Minimum Navigation)
  - Position
  - Velocity
  - Time
- **LLM Extraction**: If standard extraction fails:
  - Format-specific data analysis
  - Field validation and correction
  - Up to 10 retry attempts

#### b. RINEX-derived Location Data
- Observation data
- Satellite positions
- Time information
- Signal strength
- Carrier phase measurements
- **LLM Extraction**: If standard extraction fails:
  - RINEX-specific data analysis
  - Measurement validation
  - Up to 10 retry attempts

### 4. Data Validation
Each stage includes validation:

- Format validation
- Required fields check
- Coordinate range verification
- Timestamp consistency
- Data quality metrics

### 5. Output Generation
Produces standardized location data in JSONL format:
```json
{
    "timestamp_ms": 1234567890000,
    "latitude": 22.3456,
    "longitude": 114.2345,
    "altitude": 100.5,
    "num_sats": 8,
    "hdop": 1.2,
    "quality": "1"
}
```

## Setup and Dependencies

### Required Software
- Python 3.11+
- Redis Server
- Celery

### Python Dependencies
```
flask>=2.0.1
openai>=1.0.0
python-dotenv>=0.19.0
georinex>=1.13.0
pynmea2>=1.19.0
pandas>=1.3.0
xarray>=2022.3.0
celery>=5.3.0
redis>=4.0.0
```

### Environment Variables
```
AZURE_OPENAI_ENDPOINT=your_endpoint_here
AZURE_OPENAI_API_KEY=your_api_key_here
AZURE_OPENAI_ENGINE=your_deployment_name_here
AZURE_OPENAI_API_VERSION=2024-08-01-preview
```

## Development Setup

### Prerequisites
- Python 3.11 or higher
- Redis server
- pip (Python package installer)

### Environment Setup
1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/GNSS_IMU_AutoConversion.git
   cd GNSS_IMU_AutoConversion
   ```

2. Create and activate a virtual environment:
   ```bash
   python3.11 -m venv venv
   source venv/bin/activate  # On Unix/macOS
   # or
   .\venv\Scripts\activate  # On Windows
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   - Copy `.env.example` to `.env`
   - Update the values in `.env` with your Azure OpenAI credentials:
     ```
     AZURE_OPENAI_ENDPOINT=your_endpoint_here
     AZURE_OPENAI_API_KEY=your_api_key_here
     AZURE_OPENAI_ENGINE=your_deployment_name_here
     AZURE_OPENAI_API_VERSION=2024-08-01-preview
     ```

### Running the Application

1. Start Redis server:
   ```bash
   redis-server
   ```

2. Start Celery worker (in a new terminal):
   ```bash
   export PYTHONPATH="${PYTHONPATH}:${PWD}/src"  # On Unix/macOS
   # or
   set PYTHONPATH=%PYTHONPATH%;%CD%\src  # On Windows
   celery -A app.celery worker --loglevel=info
   ```

3. Start Flask application (in a new terminal):
   ```bash
   export PYTHONPATH="${PYTHONPATH}:${PWD}/src"  # On Unix/macOS
   # or
   set PYTHONPATH=%PYTHONPATH%;%CD%\src  # On Windows
   PORT=5005 python3.11 app.py
   ```

4. Access the web interface at http://127.0.0.1:5005

### Troubleshooting

1. Port conflicts:
   - If Redis fails to start: `pkill redis-server`
   - If Flask port is in use: Change port using `PORT=xxxx`
   - If Celery worker fails: `pkill -f "celery"`

2. Python path issues:
   - Ensure PYTHONPATH includes the src directory
   - Check imports in Python files use correct paths

3. OpenAI API issues:
   - Verify Azure OpenAI credentials in .env
   - Check API version compatibility
   - Monitor token limits in requests

4. Data processing issues:
   - Check input file format compatibility
   - Monitor Celery worker logs for errors
   - Verify file permissions in uploads directory

## Error Handling

The system implements comprehensive error handling:

1. File Format Errors
   - Invalid file format
   - Corrupted data
   - Missing required fields
   - LLM fallback triggers:
     - Standard conversion failure
     - Validation errors
     - Missing required fields

2. Processing Errors
   - Conversion failures with automatic LLM fallback
   - Validation errors with retry mechanism
   - LLM processing issues with:
     - Error feedback loop
     - Progressive improvement
     - Maximum 10 retry attempts

3. System Errors
   - Service unavailability
   - Resource constraints
   - Network issues
   - LLM API failures with fallback options

## License

MIT License - See LICENSE file for details.

## Citation

If you use this software in your research, please cite:
```bibtex
@software{gnss_imu_autoconversion,
  title={GNSS IMU Auto Conversion: An Intelligent GNSS Data Format Converter},
  author={LIN, Ju and ZHU, Lingyao},
  year={2025},
  url={https://github.com/Thorkee/GNSS_IMU_AutoConversion}
}
```

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

3. Set up environment variables:
   - Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
   - Edit `.env` with your API credentials. The application supports various LLM API services:
     - Azure OpenAI (default)
     - OpenAI
     - DeepSeek
     - Anthropic Claude
     - Other compatible LLM APIs

   Note: The `.env` file containing your actual API credentials should never be committed to version control.
   Always use the provided `.env.example` as a template.

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

## Citation

While this software is free to use, modify, and distribute under the MIT License, we kindly request that you cite this repository in any academic or professional work that uses this toolbox. This helps us track the tool's impact and benefits the research community.

To cite this software in your work:

```bibtex
@software{gnss_imu_autoconversion,
  author = {Thorkee},
  title = {GNSS IMU Auto Conversion: An Intelligent GNSS Data Format Converter},
  year = {2025},
  url = {https://github.com/Thorkee/GNSS_IMU_AutoConversion},
  version = {1.0.0}
}
```

Or in text:
> Thorkee. (2025). GNSS IMU Auto Conversion: An Intelligent GNSS Data Format Converter (Version 1.0.0) [Computer software]. https://github.com/Thorkee/GNSS_IMU_AutoConversion

## License

MIT License

## Acknowledgments

- Azure OpenAI for format detection
- georinex for RINEX file processing
- pynmea2 for NMEA file processing
