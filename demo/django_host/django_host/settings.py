from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = "agomtui-demo-django-host"
DEBUG = True
ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get(
        "AGOMTUI_DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost,testserver"
    ).split(",")
    if host.strip()
]
ROOT_URLCONF = "django_host.urls"
MIDDLEWARE = [
    "django.middleware.common.CommonMiddleware",
]
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
]
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}
TEMPLATES: list[dict[str, object]] = []
WSGI_APPLICATION = "django_host.wsgi.application"
STATIC_URL = "/static/"
STATIC_ROOT = str(BASE_DIR / "staticfiles")
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
TIME_ZONE = "UTC"
