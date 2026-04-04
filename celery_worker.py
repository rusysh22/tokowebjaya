"""
Entry point for Celery worker and beat scheduler.

Usage:
  # Start worker:
  celery -A celery_worker.celery worker --loglevel=info

  # Start beat (periodic tasks scheduler):
  celery -A celery_worker.celery beat --loglevel=info

  # Start both in one process (development only):
  celery -A celery_worker.celery worker --beat --loglevel=info
"""
from app.tasks.celery_app import celery  # noqa: F401 — re-export for CLI
