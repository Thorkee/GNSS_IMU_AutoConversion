from flask import Flask, request, jsonify, render_template
from celery import Celery
import os
from pathlib import Path
from src.format_converter import convert_to_jsonl
from src.location_extractor import extract_location_data

app = Flask(__name__)

# Configure Celery
app.config['CELERY_BROKER_URL'] = 'redis://localhost:6379/0'
app.config['CELERY_RESULT_BACKEND'] = 'redis://localhost:6379/0'

celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'])
celery.conf.update(app.config)

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@celery.task(bind=True)
def process_gnss_data(self, file_path):
    """Process GNSS data file in two steps:
    1. Convert to JSONL format
    2. Extract location data
    """
    try:
        output = []
        
        # Step 1: Convert to JSONL
        output.append("Starting file format detection and conversion...")
        self.update_state(state='PROGRESS', meta={'output': output})
        
        jsonl_file = convert_to_jsonl(file_path)
        if not jsonl_file:
            output.append("Failed to convert file to JSONL format")
            return {
                'status': 'error',
                'message': f'Failed to convert file {file_path} to JSONL format',
                'output': output
            }
        
        output.append(f"Successfully converted file to JSONL: {Path(jsonl_file).name}")
        self.update_state(state='PROGRESS', meta={'output': output})
        
        # Step 2: Extract location data
        output.append("Starting location data extraction...")
        self.update_state(state='PROGRESS', meta={'output': output})
        
        result_file = extract_location_data(jsonl_file)
        if not result_file:
            output.append("Failed to extract location data")
            return {
                'status': 'error',
                'message': f'Failed to extract location data from {jsonl_file}',
                'output': output
            }
        
        output.append(f"Successfully extracted location data: {Path(result_file).name}")
        
        # Return success with the location data file path and output messages
        return {
            'status': 'success',
            'result_file': Path(result_file).name,
            'output': output
        }
        
    except Exception as e:
        output.append(f"Error: {str(e)}")
        return {
            'status': 'error',
            'message': f'Error processing file {file_path}: {str(e)}',
            'output': output
        }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'No file part'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'status': 'error', 'message': 'No selected file'})
    
    try:
        # Save uploaded file
        file_path = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(file_path)
        
        # Start processing task
        task = process_gnss_data.delay(file_path)
        
        return jsonify({
            'status': 'success',
            'task_id': task.id
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

@app.route('/status/<task_id>')
def get_status(task_id):
    task = process_gnss_data.AsyncResult(task_id)
    
    if task.state == 'PENDING':
        response = {
            'state': task.state,
            'result': {'status': 'pending', 'output': ['Task pending...']}
        }
    elif task.state == 'PROGRESS':
        response = {
            'state': task.state,
            'result': {'status': 'processing', 'output': task.info.get('output', [])}
        }
    else:
        response = {
            'state': task.state,
            'result': task.result or {'status': 'error', 'output': ['Task failed']}
        }
    
    return jsonify(response)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, port=port) 