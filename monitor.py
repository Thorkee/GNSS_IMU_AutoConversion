import time
import requests
import json
from datetime import datetime
import subprocess
import sys
from typing import Dict, Any
import re

def log_with_timestamp(message: str, level: str = "INFO") -> None:
    timestamp = datetime.now().strftime('%H:%M:%S')
    print(f"[{timestamp}] [{level}] {message}")

def get_celery_logs() -> str:
    """Get Celery worker logs using ps and grep"""
    try:
        # Get Celery process output
        celery_process = subprocess.run(
            ['ps', 'aux'],
            capture_output=True,
            text=True
        )
        celery_lines = [line for line in celery_process.stdout.split('\n') if 'celery' in line.lower()]
        
        if not celery_lines:
            return "No Celery processes found"
            
        # Get Celery worker status
        celery_status = subprocess.run(
            ['celery', '-A', 'app.celery', 'status'],
            capture_output=True,
            text=True
        )
        
        # Combine process info and status
        output = "Celery Worker Status:\n"
        output += "-" * 40 + "\n"
        output += celery_status.stdout if celery_status.stdout else "Status command failed"
        output += "\nActive Processes:\n"
        output += "\n".join(celery_lines)
        return output
    except Exception as e:
        return f"Error getting Celery logs: {str(e)}"

def get_service_status() -> Dict[str, bool]:
    """Check core services status"""
    services = {
        'redis': False,
        'celery': False,
        'flask': False
    }
    
    try:
        # Check Redis
        redis_process = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        services['redis'] = '6383' in redis_process.stdout and 'redis-server' in redis_process.stdout
        
        # Check Celery
        celery_output = get_celery_logs()
        services['celery'] = 'celery@' in celery_output and 'ready' in celery_output.lower()
        
        # Check Flask
        try:
            response = requests.get('http://localhost:8000/', timeout=2)
            services['flask'] = response.status_code == 200
        except requests.exceptions.RequestException:
            services['flask'] = False
            
    except Exception as e:
        log_with_timestamp(f"Error checking services: {str(e)}", "ERROR")
    
    return services

def monitor_api_status() -> None:
    """Monitor API status and important messages"""
    try:
        response = requests.get('http://localhost:8000/status/health', timeout=2)
        if response.status_code == 200:
            data = response.json()
            
            # Extract and log important information
            if 'result' in data:
                result = data['result']
                
                # Log task status
                if 'status' in result:
                    status = result['status']
                    log_with_timestamp(f"Task Status: {status.upper()}")
                
                # Log important output messages
                if 'output' in result and isinstance(result['output'], list):
                    for msg in result['output']:
                        if any(key in msg.lower() for key in ['error', 'failed', 'success', 'completed', 'processing']):
                            log_with_timestamp(msg)
                            
                # Log execution results if present
                if 'execution_result' in result:
                    log_with_timestamp(f"Execution Result: {result['execution_result']}", "EXEC")
                    
    except requests.exceptions.RequestException as e:
        log_with_timestamp(f"API Status Check Failed: {str(e)}", "ERROR")

def main():
    log_with_timestamp("Starting GNSS Data Converter Monitoring")
    log_with_timestamp("Press Ctrl+C to stop")
    print("-" * 80)
    
    last_service_status = {}
    last_celery_log = ""
    
    try:
        while True:
            # Check services status
            current_status = get_service_status()
            
            # Only log service status changes
            if current_status != last_service_status:
                log_with_timestamp("Services Status:")
                for service, status in current_status.items():
                    status_symbol = "✓" if status else "✗"
                    status_level = "INFO" if status else "WARN"
                    log_with_timestamp(f"{service.capitalize()}: {status_symbol}", status_level)
                print("-" * 40)
                
                last_service_status = current_status.copy()
            
            # Get and display Celery logs
            celery_log = get_celery_logs()
            if celery_log != last_celery_log:
                log_with_timestamp("Celery Worker Logs:", "INFO")
                print("-" * 40)
                print(celery_log)
                print("-" * 40)
                last_celery_log = celery_log
            
            # Monitor API status and messages
            monitor_api_status()
            
            sys.stdout.flush()
            time.sleep(5)
            
    except KeyboardInterrupt:
        log_with_timestamp("Monitoring stopped by user")

if __name__ == '__main__':
    main() 