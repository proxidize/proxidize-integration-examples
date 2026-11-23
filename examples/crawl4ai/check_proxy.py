"""Verify a Proxidize HTTPS access point with Crawl4AI."""

from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path

from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, ProxyConfig

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))

from proxy_config import ip_check_url, load_https_proxy, parse_exit_ip  # noqa: E402


async def check_proxy() -> dict[str, str]:
    proxy = load_https_proxy()
    config = CrawlerRunConfig(
        proxy_config=ProxyConfig(
            server=proxy.server,
            username=proxy.username,
            password=proxy.password,
        )
    )

    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url=ip_check_url(), config=config)

    if not result.success:
        raise RuntimeError(result.error_message or "Crawl4AI request failed")

    payload = "\n".join(
        str(value)
        for value in (result.markdown, result.cleaned_html, result.html)
        if value
    )
    match = re.search(r'"ip"\s*:\s*"([^"]+)"', payload)
    exit_ip = parse_exit_ip(match.group(1) if match else payload)
    return {
        "client": "crawl4ai",
        "profile": proxy.profile,
        "proxy": proxy.redacted_server,
        "exit_ip": exit_ip,
    }


def main() -> None:
    print(json.dumps(asyncio.run(check_proxy()), indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Crawl4AI proxy check failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
