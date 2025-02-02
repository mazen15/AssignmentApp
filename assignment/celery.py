from celery import Celery
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'assignment.settings')

app = Celery('assignment')
app.config_from_object('django.conf:settings', namespace='CELERY')

print(f"Using broker URL: {app.conf.broker_url}")

app.autodiscover_tasks()

# Use Redis as the result backend

# Define your result backend
app.conf.update(
    result_backend='redis://127.0.0.1:6381/0',  # Using Redis as the result backend
)
