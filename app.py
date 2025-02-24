from flask import Flask, request, jsonify, render_template, send_file
from celery import Celery
import os
from pathlib import Path
from src.format_converter import convert_to_jsonl
from src.location_extractor import extract_location_data
from werkzeug.utils import secure_filename
import uuid
import json

app = Flask(__name__)

# Configure Celery
app.config['CELERY_BROKER_URL'] = 'redis://localhost:6383/0'
app.config['CELERY_RESULT_BACKEND'] = 'redis://localhost:6383/0'

celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'])
celery.conf.update(app.config)

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@celery.task(bind=True)
def process_gnss_data(self, file_path, original_filename=None):
    """Process GNSS data file in two steps:
    1. Convert to JSONL format
    2. Extract location data
    If standard processing fails, fall back to LLM assistance
    """
    try:
        output = []
        
        # Use original filename if provided, otherwise use base name of file_path
        if original_filename is None:
            original_filename = os.path.basename(file_path)
            
        # Generate output filenames based on original filename
        base_name = os.path.splitext(original_filename)[0]
        jsonl_output = f"{base_name}.jsonl"
        location_output = f"{base_name}.location.jsonl"
        
        # Step 1: Convert to JSONL - Try standard conversion once
        output.append("Starting file format detection and conversion...")
        self.update_state(state='PROGRESS', meta={'output': output})
        
        try:
            # Try standard conversion once
            jsonl_file = convert_to_jsonl(file_path, os.path.join(UPLOAD_FOLDER, jsonl_output))
            if jsonl_file:
                output.append("Standard conversion successful")
            else:
                raise Exception("Standard conversion failed")
        except Exception as e:
            output.append(f"Standard conversion failed: {str(e)}")
            output.append("Falling back to LLM assistance for conversion...")
            self.update_state(state='PROGRESS', meta={'output': output})
            
            # Initialize GNSSProcessor for LLM assistance with 10 attempts
            from src.gnss_processor import GNSSProcessor
            processor = GNSSProcessor()
            processor.output_callback = lambda msg: output.append(msg)
            
            try:
                jsonl_file = processor.process_file(file_path)
                if not jsonl_file:
                    raise Exception("LLM-assisted conversion failed")
                output.append("LLM-assisted conversion successful")
            except Exception as llm_error:
                output.append(f"LLM-assisted conversion failed: {str(llm_error)}")
                return {
                    'status': 'error',
                    'message': f'Failed to convert file {original_filename} (both standard and LLM methods failed)',
                    'output': output
                }
        
        output.append(f"Successfully converted file to JSONL: {jsonl_output}")
        self.update_state(state='PROGRESS', meta={'output': output})
        
        # Step 2: Extract location data - Try standard extraction once
        output.append("Starting location data extraction...")
        self.update_state(state='PROGRESS', meta={'output': output})
        
        try:
            # Try standard extraction once
            result_file = extract_location_data(jsonl_file, os.path.join(UPLOAD_FOLDER, location_output))
            if result_file:
                output.append("Standard location extraction successful")
            else:
                raise Exception("No valid location records found in standard extraction")
        except Exception as e:
            output.append(f"Standard extraction failed: {str(e)}")
            output.append("Falling back to LLM assistance for extraction...")
            self.update_state(state='PROGRESS', meta={'output': output})
            
            try:
                # Check if Azure OpenAI is properly configured
                if not os.getenv('AZURE_OPENAI_API_KEY') or not os.getenv('AZURE_OPENAI_ENDPOINT'):
                    raise Exception("Azure OpenAI credentials not configured")
                
                # Use GNSSProcessor for LLM-assisted extraction with 10 attempts
                processor = GNSSProcessor()
                processor.output_callback = lambda msg: output.append(msg)
                result_file = processor.process_file(jsonl_file)
                if result_file:
                    output.append("LLM-assisted extraction successful")
                else:
                    raise Exception("LLM-assisted extraction failed")
            except Exception as llm_error:
                output.append(f"LLM-assisted extraction failed: {str(llm_error)}")
                return {
                    'status': 'error',
                    'message': f'Failed to extract location data from {jsonl_output} (all methods failed)',
                    'output': output
                }
        
        output.append(f"Successfully extracted location data: {location_output}")
        
        # Clean up temporary files
        try:
            os.remove(file_path)  # Remove the uploaded file with UUID name
            if jsonl_file != os.path.join(UPLOAD_FOLDER, location_output):  # Don't remove if it's the same as output
                os.remove(jsonl_file)  # Remove intermediate JSONL file
        except Exception as e:
            output.append(f"Warning: Could not clean up temporary files: {str(e)}")
        
        # Return success with the location data file path and output messages
        return {
            'status': 'success',
            'result_file': location_output,
            'output': output
        }
        
    except Exception as e:
        output.append(f"Error: {str(e)}")
        return {
            'status': 'error',
            'message': f'Error processing file {original_filename}: {str(e)}',
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
        # Generate a unique filename to avoid conflicts
        original_filename = secure_filename(file.filename)
        file_extension = os.path.splitext(original_filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        
        # Save uploaded file with unique name
        file_path = os.path.join(UPLOAD_FOLDER, unique_filename)
        file.save(file_path)
        
        # Start processing task
        task = process_gnss_data.delay(file_path, original_filename)
        
        return jsonify({
            'status': 'success',
            'task_id': task.id,
            'original_filename': original_filename
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

@app.route('/status/<task_id>')
def get_status(task_id):
    try:
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
            if task.successful():
                response = {
                    'state': task.state,
                    'result': task.result
                }
            else:
                # Handle failed tasks
                error = str(task.result) if task.result else 'Unknown error occurred'
                response = {
                    'state': task.state,
                    'result': {
                        'status': 'error',
                        'message': error,
                        'output': ['Task failed with error: ' + error]
                    }
                }
        
        return jsonify(response)
        
    except Exception as e:
        return jsonify({
            'state': 'error',
            'result': {
                'status': 'error',
                'message': str(e),
                'output': ['Error checking task status: ' + str(e)]
            }
        })

@app.route('/download/<filename>')
def download_file(filename):
    """Download a processed file."""
    try:
        # Ensure the file exists in the upload folder
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        if not os.path.exists(file_path):
            return jsonify({
                'status': 'error',
                'message': 'File not found'
            }), 404
            
        # Set content disposition to trigger save dialog
        response = send_file(
            file_path,
            as_attachment=True,
            download_name=filename,
            mimetype='application/json'
        )
        response.headers["Content-Disposition"] = f"attachment; filename={filename}"
        return response
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, port=port) 