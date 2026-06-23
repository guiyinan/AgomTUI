from __future__ import annotations

import os
import sys
import threading
from pathlib import Path
from wsgiref.simple_server import make_server

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "demo" / ".vendor"
CORE_SRC = ROOT / "packages" / "agomtui-core" / "src"
COMPILER_SRC = ROOT / "packages" / "agomtui-compiler" / "src"
DJANGO_HOST_ROOT = ROOT / "demo" / "django_host"

for path in (VENDOR, ROOT, CORE_SRC, COMPILER_SRC, DJANGO_HOST_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_host.settings")

from demo import standalone_server  # noqa: E402
from django.core.wsgi import get_wsgi_application  # noqa: E402


def main() -> None:
    demo_server = standalone_server.create_demo_server()
    django_app = get_wsgi_application()
    django_server = make_server(standalone_server.DJANGO_HOST, standalone_server.DJANGO_PORT, django_app)

    demo_thread = threading.Thread(target=demo_server.serve_forever, daemon=True)
    django_thread = threading.Thread(target=django_server.serve_forever, daemon=True)
    demo_thread.start()
    django_thread.start()

    print(f"Standalone demo: http://{standalone_server.HOST}:{standalone_server.PORT}/")
    print(f"Django host demo: http://{standalone_server.DJANGO_HOST}:{standalone_server.DJANGO_PORT}/")
    print("Press Ctrl+C to stop both servers.")
    try:
        demo_thread.join()
        django_thread.join()
    except KeyboardInterrupt:
        pass
    finally:
        demo_server.shutdown()
        django_server.shutdown()


if __name__ == "__main__":
    main()
