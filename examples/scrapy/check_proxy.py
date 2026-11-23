"""Make one proxied IP-check request through Scrapy."""

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
    parse_exit_ip,
    request_timeout_seconds,
)


def main() -> None:
    proxy = load_https_proxy()
    observations: list[str] = []
    errors: list[str] = []

    class ProxyCheckSpider(scrapy.Spider):
        name = "proxidize_proxy_check"
        custom_settings = {
            "DOWNLOAD_TIMEOUT": request_timeout_seconds(),
            "LOG_LEVEL": os.getenv("SCRAPY_LOG_LEVEL", "ERROR"),
            "RETRY_ENABLED": False,
            "TELNETCONSOLE_ENABLED": False,
        }

        def proxy_request(self):
            return scrapy.Request(
                ip_check_url(),
                meta={"proxy": proxy.authenticated_url},
                callback=self.parse_ip,
                errback=self.capture_error,
            )

        async def start(self):
            yield self.proxy_request()

        def start_requests(self):
            # Compatibility path for Scrapy releases before async start().
            yield self.proxy_request()

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
        raise RuntimeError(
            f"Scrapy did not return a successful IP-check response: {detail}"
        )

    print(
        json.dumps(
            {
                "client": "scrapy",
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
        print(f"Scrapy proxy check failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
