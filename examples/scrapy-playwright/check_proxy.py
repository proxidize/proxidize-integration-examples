"""Verify a Proxidize HTTPS access point with Scrapy Playwright."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import scrapy
from scrapy.crawler import CrawlerProcess

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))

from proxy_config import (  # noqa: E402
    ip_check_url,
    load_https_proxy,
    navigation_timeout_ms,
    parse_exit_ip,
)


def main() -> None:
    proxy = load_https_proxy()
    observations: list[str] = []
    errors: list[str] = []

    class ProxyCheckSpider(scrapy.Spider):
        name = "proxidize_scrapy_playwright_check"
        custom_settings = {
            "DOWNLOAD_HANDLERS": {
                "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
                "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
            },
            "TWISTED_REACTOR": (
                "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
            ),
            "PLAYWRIGHT_BROWSER_TYPE": "chromium",
            "PLAYWRIGHT_CONTEXTS": {
                "proxidize": {"proxy": proxy.playwright_settings}
            },
            "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": navigation_timeout_ms(),
            "LOG_LEVEL": os.getenv("SCRAPY_LOG_LEVEL", "ERROR"),
            "RETRY_ENABLED": False,
            "TELNETCONSOLE_ENABLED": False,
        }

        async def start(self):
            yield scrapy.Request(
                ip_check_url(),
                callback=self.parse_ip,
                errback=self.capture_error,
                meta={"playwright": True, "playwright_context": "proxidize"},
            )

        def parse_ip(self, response):
            observations.append(parse_exit_ip(response.text))

        def capture_error(self, failure):
            message = str(failure.value)
            message = message.replace(proxy.username, "[redacted]")
            message = message.replace(proxy.password, "[redacted]")
            errors.append(message)

    process = CrawlerProcess()
    process.crawl(ProxyCheckSpider)
    process.start()

    if not observations:
        detail = errors[0] if errors else "no response or error detail"
        raise RuntimeError(f"Scrapy Playwright request failed: {detail}")

    print(
        json.dumps(
            {
                "client": "scrapy-playwright",
                "profile": proxy.profile,
                "proxy": proxy.redacted_server,
                "exit_ip": observations[0],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Scrapy Playwright proxy check failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
