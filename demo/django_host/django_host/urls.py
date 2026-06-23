from __future__ import annotations

from django.urls import path

from . import views


urlpatterns = [
    path("", views.host_home, name="host-home"),
    path("tui/", views.host_tui, name="host-tui"),
    path("api/tui/catalog/", views.host_catalog, name="host-catalog"),
    path("api/tui/screens/<path:screen_key>/", views.host_screen, name="host-screen"),
    path("api/tui/actions/<path:action_key>/run/", views.host_action, name="host-action"),
    path("contracts/openapi.json", views.openapi_contract, name="openapi-contract"),
    path("contracts/django-contract-manifest.json", views.django_contract, name="django-contract"),
    path("contracts/published-metadata.json", views.published_metadata, name="published-metadata"),
]
