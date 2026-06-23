from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
VENDOR = ROOT / "demo" / ".vendor"
CORE_SRC = ROOT / "packages" / "agomtui-core" / "src"
COMPILER_SRC = ROOT / "packages" / "agomtui-compiler" / "src"

for path in (VENDOR, ROOT, CORE_SRC, COMPILER_SRC):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_host.settings")

from django.core.wsgi import get_wsgi_application  # noqa: E402


application = get_wsgi_application()
