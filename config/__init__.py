"""Django configuration package for the HomoRepeat web app."""
from .celery import app as celery_app

__all__ = ("celery_app",)
