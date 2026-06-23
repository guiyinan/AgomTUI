from __future__ import annotations

from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = "agomtui-demo-django-host"
DEBUG = True
ALLOWED_HOSTS = ["127.0.0.1", "localhost", "testserver"]
ROOT_URLCONF = "django_host.urls"
MIDDLEWARE = [
    "django.middleware.common.CommonMiddleware",
]
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
]
TEMPLATES: list[dict[str, object]] = []
WSGI_APPLICATION = "django_host.wsgi.application"
STATIC_URL = "/static/"
STATIC_ROOT = str(BASE_DIR / "staticfiles")
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
TIME_ZONE = "UTC"
