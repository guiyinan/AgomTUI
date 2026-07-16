from __future__ import annotations

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from playwright.sync_api import sync_playwright


@override_settings(ALLOWED_HOSTS=["*"])
class RuntimeBrowserSmokeTests(StaticLiveServerTestCase):
    """Exercise the synchronized Runtime in a real browser against Django."""

    def test_runtime_loads_catalog_and_initial_screen_without_browser_errors(
        self,
    ) -> None:
        console_errors: list[str] = []
        page_errors: list[str] = []
        api_responses: list[tuple[str, int]] = []

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.on(
                "console",
                lambda message: (
                    console_errors.append(message.text)
                    if message.type == "error"
                    else None
                ),
            )
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            page.on(
                "response",
                lambda response: (
                    api_responses.append((response.url, response.status))
                    if "/api/tui/" in response.url
                    else None
                ),
            )

            page.goto(f"{self.live_server_url}/tui/")
            page.wait_for_load_state("networkidle")
            page.locator("[data-screen-key]").first.wait_for(state="visible")
            page.locator("[data-action-ui-key]").first.wait_for(state="attached")

            self.assertEqual(page.title(), "AgomTUI Django Host TUI")
            self.assertFalse(page.locator("body").get_by_text("加载失败").count())
            browser.close()

        successful_urls = {url for url, status in api_responses if status == 200}
        self.assertTrue(
            any(url.endswith("/api/tui/bootstrap/") for url in successful_urls)
        )
        self.assertEqual(page_errors, [])
        self.assertEqual(console_errors, [])
