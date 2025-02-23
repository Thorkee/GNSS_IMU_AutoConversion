broker_url = 'redis://localhost:6379/0'
result_backend = 'redis://localhost:6379/0'
broker_connection_retry_on_startup = True

task_serializer = 'json'
result_serializer = 'json'
accept_content = ['json']
timezone = 'UTC'
enable_utc = True

task_routes = {
    'tasks.process_gnss_data': {'queue': 'celery'}
}

imports = ('app',) 