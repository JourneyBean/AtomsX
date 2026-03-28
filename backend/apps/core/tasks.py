"""
Celery tasks for AtomsX Visual Coding Platform.
"""
from config.celery import app


@app.task(bind=True)
def debug_task(self):
    """Debug task for testing Celery setup."""
    print(f'Debug task executed: {self.request.id}')
    return 'OK'