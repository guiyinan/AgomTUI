from __future__ import annotations

import json
from typing import Any

from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from demo import standalone_server as demo


def _json_response(payload: Any, *, status: int = 200) -> JsonResponse:
    return JsonResponse(
        payload, status=status, json_dumps_params={"ensure_ascii": False, "indent": 2}
    )


@require_GET
def host_home(request: HttpRequest) -> HttpResponse:
    del request
    body = f"""
    <section class="hero">
      <div class="eyebrow">Real Django Host</div>
      <h1>{demo.HOST_DEMO_INFO["project_name"]}</h1>
      <p>This page is served by a real Django process. It mounts the extracted runtime, serves published metadata and action endpoints under <code>/api/tui/*</code>, and exposes code-owned export contracts for the compiler.</p>
      <div class="hero-actions">
        <a class="button" href="/tui/">Open Django-Mounted TUI</a>
        <a class="button alt" href="/contracts/openapi.json">OpenAPI Export</a>
        <a class="button alt" href="/contracts/django-contract-manifest.json">Django Contract Export</a>
      </div>
      <div class="status">Django host / {demo.HOST_DEMO_INFO["environment"]} / user {demo.HOST_DEMO_INFO["user"]}</div>
    </section>
    <section class="grid">
      <div class="panel">
        <h2>Host-owned responsibilities</h2>
        <ul>
          <li>Serve the runtime through a Django route and keep auth, permission, and host wiring local to Django.</li>
          <li>Return one published metadata artifact through a repository-shaped endpoint contract.</li>
          <li>Execute host actions and re-enter Django-owned user context before returning view models.</li>
          <li>Export OpenAPI and Django contracts so the compiler can regenerate metadata safely.</li>
        </ul>
      </div>
      <div class="panel">
        <h2>Live endpoints</h2>
        {demo.json_html({
            "home": "/",
            "runtime": "/tui/",
            "catalog": "/api/tui/catalog/",
            "screen_example": "/api/tui/screens/execution.accounts/",
            "action_example": "/api/tui/actions/execution.tasks.ai-brief/run/",
        })}
      </div>
    </section>
    """
    return HttpResponse(
        demo.layout("AgomTUI Django Host", body, active="integration"),
        content_type="text/html; charset=utf-8",
    )


@require_GET
def host_tui(request: HttpRequest) -> HttpResponse:
    del request
    html = demo.render_runtime_html(
        title="AgomTUI Django Host TUI",
        home_href="/",
        brand_label="AgomTUI Host",
        api_base="/api/tui",
        asset_base="/tui/static",
    )
    return HttpResponse(html, content_type="text/html; charset=utf-8")


@require_GET
def host_runtime_asset(request: HttpRequest, asset_path: str) -> HttpResponse:
    del request
    try:
        body, mime = demo.runtime_asset_payload(asset_path)
    except FileNotFoundError as error:
        raise Http404(f"Unknown asset: {asset_path}") from error
    return HttpResponse(body, content_type=mime)


@require_GET
def host_catalog(request: HttpRequest) -> JsonResponse:
    del request
    return _json_response(demo.hostify_catalog(demo.build_catalog()))


@require_GET
def host_bootstrap(request: HttpRequest) -> JsonResponse:
    """Return the optimized Runtime bootstrap contract for the demo host."""

    catalog = demo.hostify_catalog(demo.build_catalog())
    requested_screen = str(request.GET.get("screen_key") or "").strip()
    resolved_screen = requested_screen or str(catalog["default_screen"])
    restored = False
    try:
        screen = demo.hostify_screen_spec(demo.build_screen_spec(resolved_screen))
    except KeyError:
        resolved_screen = str(catalog["default_screen"])
        screen = demo.hostify_screen_spec(demo.build_screen_spec(resolved_screen))
        restored = bool(requested_screen)
    return _json_response(
        {
            "contract": "tui-bootstrap.v1",
            "catalog": catalog,
            "screen": screen,
            "requested_screen": requested_screen,
            "resolved_screen": resolved_screen,
            "restored": restored,
        }
    )


@require_GET
def host_screen(request: HttpRequest, screen_key: str) -> JsonResponse:
    del request
    try:
        payload = demo.hostify_screen_spec(demo.build_screen_spec(screen_key))
    except KeyError:
        return _json_response(
            {"ok": False, "error": f"Unknown screen: {screen_key}"}, status=404
        )
    return _json_response(payload)


@csrf_exempt
@require_POST
def host_action(request: HttpRequest, action_key: str) -> JsonResponse:
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return _json_response({"ok": False, "error": "Invalid JSON body"}, status=400)
    params = body.get("params") or {}
    confirmed = bool(body.get("confirmed"))
    confirmation_evidence = (
        body.get("confirmation") if isinstance(body.get("confirmation"), dict) else None
    )
    reauth_evidence = (
        body.get("reauth") if isinstance(body.get("reauth"), dict) else None
    )
    try:
        payload = demo.hostify_action_result(
            demo.handle_action(
                action_key, params, confirmed, confirmation_evidence, reauth_evidence
            ),
            api_base="/api/tui",
        )
    except KeyError:
        return _json_response(
            {"ok": False, "error": f"Unknown action: {action_key}"}, status=404
        )
    return _json_response(payload)


@require_GET
def openapi_contract(request: HttpRequest) -> JsonResponse:
    del request
    return _json_response(demo.OPENAPI_FIXTURE)


@require_GET
def django_contract(request: HttpRequest) -> JsonResponse:
    del request
    return _json_response(demo.DJANGO_CONTRACT_FIXTURE)


@require_GET
def published_metadata(request: HttpRequest) -> JsonResponse:
    del request
    return _json_response(demo.VALIDATED_METADATA)
