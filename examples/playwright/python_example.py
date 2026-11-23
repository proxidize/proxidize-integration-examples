"""Verify a Proxidize HTTPS access point inside a Playwright page."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))

from proxy_config import (  # noqa: E402
    ip_check_url,
    load_https_proxy,
    navigation_timeout_ms,
    parse_exit_ip,
)


def main() -> None:
    proxy = load_https_proxy()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            context = browser.new_context(proxy=proxy.playwright_settings)
            try:
                context.set_default_navigation_timeout(navigation_timeout_ms())
                page = context.new_page()
                response = page.goto(ip_check_url(), wait_until="domcontentloaded")
                if response is None or not response.ok:
                    status = "none" if response is None else response.status
                    raise RuntimeError(f"IP check returned HTTP {status}")
                exit_ip = parse_exit_ip(page.locator("body").inner_text())
            finally:
                context.close()
        finally:
            browser.close()

    print(
        json.dumps(
            {
                "client": "playwright-python",
                "profile": proxy.profile,
                "proxy": proxy.redacted_server,
                "exit_ip": exit_ip,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Playwright proxy check failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
