# GNSS/IMU Data Processing System

**UNDER DEVELOPMENT, CONTACT JU.LIN@CONNECT.POLYU.HK FOR INQUIRIES**

A robust system for processing various GNSS and IMU data formats, with automatic format detection and conversion capabilities.

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

## Module Implementation Details

### Core Processing Modules

#### 1. GNSS Processor (`src/gnss_processor.py`)
The main processing class that orchestrates the entire pipeline:
- Implements the core `GNSSProcessor` class
- Handles format detection and conversion routing
- Provides custom JSON serialization for GNSS-specific data types
- Implements coordinate conversion utilities
- Contains the main processing logic for both RINEX and NMEA formats
- Manages the LLM fallback mechanism

#### 2. Format Converters

##### RINEX Converter (`src/rinex_converter.py`)
Specialized module for RINEX format processing:
```python
def convert_rinex_to_jsonl(input_file, output_file):
    # Reads RINEX data using georinex
    obs_data = gr.load(input_file)
    # Converts to DataFrame
    df = obs_data.to_dataframe().reset_index()
    # Adds timestamp_ms
    df['timestamp_ms'] = df['time'].apply(lambda x: int(x.timestamp() * 1000))
    # Writes standardized JSONL
```

##### NMEA Converter (`src/nmea_converter.py`)
Handles NMEA format processing:
```python
def convert_nmea_to_jsonl(input_file, output_file):
    # Processes NMEA sentences
    msg = pynmea2.parse(nmea_msg)
    # Extracts GGA/RMC messages
    if msg.sentence_type in ['GGA', 'RMC', 'GNS']:
        record = extract_location_data(msg, timestamp)
    # Converts to standardized format
```

#### 3. Location Data Extractors (`src/location_extractor.py`)
Specialized module for extracting standardized location data:

##### NMEA Location Extraction
```python
def extract_nmea_location_data(input_file):
    # Processes GGA messages
    if data.get('sentence_type') == 'GGA':
        record = {
            'timestamp_ms': data.get('timestamp_ms'),
            'latitude': latitude,
            'longitude': longitude,
            'altitude': float(altitude),
            'num_satellites': int(num_sats),
            'hdop': float(horizontal_dil),
            'quality': int(gps_qual)
        }
```

##### RINEX Location Extraction
```python
def extract_rinex_location(record):
    location = {
        'timestamp_ms': int(record['time'].timestamp() * 1000),
        'satellite_system': sat_sys,
        'satellite_number': sat_num,
        'pseudorange': float(record['C1']),
        'carrier_phase': float(record['L1']),
        'doppler': float(record['D1']),
        'signal_strength': float(record['S1'])
    }
```

#### 4. Data Validation (`src/gnss_processor.py`)
Comprehensive validation implementation:

##### Record Validation
```python
def _validate_records(self, records):
    required_fields = {'timestamp_ms', 'latitude', 'longitude'}
    numeric_fields = {'latitude', 'longitude', 'altitude', 'hdop', 'speed'}
    
    for record in records:
        # Validates required fields
        if not all(field in record for field in required_fields):
            return False
        # Validates numeric fields
        for field in numeric_fields:
            if field in record and record[field] is not None:
                try:
                    float(record[field])
                except (ValueError, TypeError):
                    return False
```

##### Location Validation
```python
def validate_location_record(record):
    # Format-specific validation
    if 'satellite_system' in record:
        # RINEX format validation
        required_fields = ['timestamp_ms', 'satellite_system', 'satellite_number']
        optional_fields = ['pseudorange', 'carrier_phase', 'doppler', 'signal_strength']
    else:
        # NMEA format validation
        required_fields = ['timestamp_ms']
        optional_fields = ['latitude', 'longitude', 'altitude', 'num_satellites',
                         'hdop', 'quality', 'speed', 'course']
```

#### 5. LLM Integration (`src/format_converter.py`)
Implements the LLM fallback mechanism:
```python
def convert_with_llm(input_file, output_file, format_type=None):
    # Format-specific system messages
    system_messages = {
        'RINEX': """Expert RINEX processing instructions...""",
        'NMEA': """Expert NMEA processing instructions..."""
    }
    # Implements retry mechanism
    # Handles error analysis and feedback
    # Maximum 10 retry attempts
```

### Supporting Modules

#### 1. Utility Functions (`src/utils.py`)
Common utilities used across modules:
- Custom JSON serialization
- Coordinate conversion functions
- Timestamp handling
- Error logging

#### 2. Data Filtering (`src/filter_location.py`)
Specialized filtering functionality:
- Filters invalid records
- Removes duplicate timestamps
- Handles missing data
- Implements quality thresholds

### Module Interactions

1. Data Flow:
   ```
   File Upload → Format Detection → Conversion → Location Extraction → Validation → Output
   ```

2. Error Handling Flow:
   ```
   Standard Processing → Validation → [If Failed] → LLM Fallback → Validation → [If Failed] → Retry Loop
   ```

3. Quality Control Flow:
   ```
   Data Input → Format Validation → Field Validation → Numeric Validation → Quality Metrics → Output Validation
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
   git clone https://github.com/Thorkee/GNSS_IMU_AutoConversion.git
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
   redis-server --port 6383
   ```

2. Start Celery worker:
   ```bash
   export REDIS_PORT=6383 && celery -A app.celery worker --loglevel=info
   ```

3. Start Flask application:
   ```bash
   export REDIS_PORT=6383 && export PYTHONPATH="${PYTHONPATH}:${PWD}/src" && PORT=5010 python3 app.py
   ```

The application will be accessible at http://127.0.0.1:5010

### Troubleshooting

### Common Issues

1. Redis Port Conflicts
   - Check if Redis is already running on the port
   - Use `lsof -ti:6383 | xargs kill -9` to free the port
   - Restart Redis server

2. File Processing Errors
   - Verify file encoding (UTF-8 recommended)
   - Check file permissions
   - Ensure proper format of input files

3. Task Queue Issues
   - Verify Redis connection
   - Check Celery worker status
   - Review task logs for errors

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

If you use this software in your research, please cite it as below:

```bibtex
@software{gnss_imu_autoconversion,
  title = {GNSS IMU Auto Conversion: An Intelligent GNSS Data Format Converter},
  author = {LIN, Ju and ZHU, Lingyao},
  year = {2025},
  version = {1.0.0},
  date-released = {2025-02-24},
  url = {https://github.com/Thorkee/GNSS_IMU_AutoConversion}
}
```

Or in text:
> LIN, Ju and ZHU, Lingyao. (2025). GNSS IMU Auto Conversion: An Intelligent GNSS Data Format Converter (Version 1.0.0) [Computer software]. https://github.com/Thorkee/GNSS_IMU_AutoConversion

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

1. Start Redis server:
```bash
redis-server --port 6383
```

2. Start Celery worker:
```bash
export REDIS_PORT=6383 && celery -A app.celery worker --loglevel=info
```

3. Start the Flask application:
```bash
export REDIS_PORT=6383 && export PYTHONPATH="${PYTHONPATH}:${PWD}/src" && PORT=5010 python3 app.py
```

The application will be accessible at http://127.0.0.1:5010

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

MIT License - See LICENSE file for details.

## Acknowledgments

- Azure OpenAI for format detection
- georinex for RINEX file processing
- pynmea2 for NMEA file processing

## Recent Updates

### Configuration Changes
- Redis port configuration updated to use port 6383
- Flask application configured to run on port 5010
- Maximum tokens for LLM requests adjusted to comply with model limits (16384 tokens)

### Bug Fixes
- Fixed issues with Redis port conflicts
- Improved error handling in NMEA file processing
- Enhanced LLM-assisted format conversion reliability
- Added better validation for location data extraction

### Performance Improvements
- Optimized file processing pipeline
- Enhanced error recovery in format conversion
- Improved task queue management with Celery
- Better handling of UTF-8 encoded NMEA files
