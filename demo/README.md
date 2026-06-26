# Demo Surfaces

## 1. Standalone product demo

Run the local demo server from the repository root:

```powershell
.\scripts\start_standalone.ps1
```

Equivalent raw command:

```powershell
python demo\standalone_server.py
```

Then open:

- `http://localhost:8020/` for the product overview
- `http://localhost:8020/standalone/` for the runtime workbench
- `http://localhost:8020/standalone/?mode=integration` for the simulated host-mounted runtime using the integration adapter surface
- `http://localhost:8020/compiler/` for the compiler walkthrough
- `http://localhost:8020/integration/` for the integration contract demo
- `http://localhost:8020/migration/` for the migration checklist

The standalone server uses only the Python standard library. It reads the compiler packages from `packages/agomtui-core/src` and `packages/agomtui-compiler/src`, loads the demo fixtures under `demo/fixtures/`, and exposes a mock `/api/tui/*` adapter surface so the extracted runtime shell can run without a host business system.

## 2. Real Django host demo

Start the real host in a second terminal:

```powershell
.\scripts\start_django_host.ps1
```

Equivalent raw command:

```powershell
python demo\django_host\manage.py runserver 127.0.0.1:8030 --noreload
```

Then open:

- `http://localhost:8030/` for the Django host landing page
- `http://localhost:8030/tui/` for the Django-mounted runtime
- `http://localhost:8030/contracts/openapi.json` for the OpenAPI export
- `http://localhost:8030/contracts/django-contract-manifest.json` for the Django contract export
- `http://localhost:8030/contracts/published-metadata.json` for the published metadata artifact

## 3. Combined startup

If you want one command for both surfaces:

```powershell
.\scripts\start_frontend.ps1
```

Equivalent raw command:

```powershell
python demo\run_demo_stack.py
```

The frontend/runtime surface is currently served by these Python demo servers. There is no npm/Vite dev server in this repository.

For a VPS or other remote host, keep the local defaults unchanged and override bind addresses explicitly:

```bash
AGOMTUI_HOST=0.0.0.0 AGOMTUI_DJANGO_HOST=0.0.0.0 AGOMTUI_DJANGO_ALLOWED_HOSTS='*' python demo/run_demo_stack.py
```

## 4. Verification

Compiler tests:

```powershell
$env:PYTHONPATH='D:\githv\AgomTUI\packages\agomtui-core\src;D:\githv\AgomTUI\packages\agomtui-compiler\src'
python -m unittest discover packages\agomtui-compiler\tests
```

Django host tests:

```powershell
python demo\django_host\manage.py test django_host
```
