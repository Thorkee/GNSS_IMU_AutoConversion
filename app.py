from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename
import os
from celery import Celery
from datetime import datetime
import json
from pathlib import Path
import openai
from dotenv import load_dotenv
from gnss_processor import GNSSProcessor

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['CELERY_BROKER_URL'] = 'redis://localhost:6379/0'
app.config['CELERY_RESULT_BACKEND'] = 'redis://localhost:6379/0'

# Configure Azure OpenAI
openai.api_type = "azure"
openai.api_base = os.getenv('AZURE_OPENAI_ENDPOINT')
openai.api_version = os.getenv('AZURE_OPENAI_API_VERSION', '2023-05-15')  # Use environment variable with fallback
openai.api_key = os.getenv('AZURE_OPENAI_API_KEY')

# Initialize Celery
celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'])
celery.conf.update(app.config)

# Initialize GNSS Processor
processor = GNSSProcessor()

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    files = request.files.getlist('file')
    if not files or files[0].filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    tasks = []
    for file in files:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Start processing task
        task = process_gnss_data.delay(filepath)
        tasks.append({
            'filename': filename,
            'task_id': task.id
        })
    
    return jsonify({
        'message': f'Successfully uploaded {len(tasks)} files',
        'tasks': tasks
    })

@app.route('/status/<task_id>')
def get_status(task_id):
    task = process_gnss_data.AsyncResult(task_id)
    if task.state == 'PENDING':
        response = {
            'state': task.state,
            'status': 'Task is pending...'
        }
    elif task.state == 'SUCCESS':
        response = {
            'state': task.state,
            'result': task.get()
        }
    else:
        response = {
            'state': task.state,
            'status': str(task.info)
        }
    return jsonify(response)

@app.route('/download/<filename>')
def download_file(filename):
    return send_file(
        os.path.join(app.config['UPLOAD_FOLDER'], filename),
        as_attachment=True
    )

@celery.task(bind=True)
def process_gnss_data(self, filepath):
    try:
        # Process the file using our GNSS processor
        result_file = processor.process_file(filepath)
        
        return {
            'status': 'success',
            'result_file': os.path.basename(result_file)
        }
    except Exception as e:
        return {
            'status': 'error',
            'message': str(e)
        }

if __name__ == '__main__':
    app.run(debug=True) 