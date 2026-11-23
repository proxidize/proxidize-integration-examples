from __future__ import annotations

import asyncio

from aiohttp import ClientSession, ClientTimeout, encode_basic_auth

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))

from proxy_config import (  # noqa: E402
    ip_check_url,
    load_https_proxy,
    parse_exit_ip,
    request_timeout_seconds,
)


async def main() -> None:
    proxy = load_https_proxy()
    proxy_headers = {
        "Proxy-Authorization": encode_basic_auth(proxy.username, proxy.password)
    }
    timeout = ClientTimeout(total=request_timeout_seconds())

    async with ClientSession(timeout=timeout) as session:
        async with session.get(
            ip_check_url(), proxy=proxy.server, proxy_headers=proxy_headers
        ) as response:
            response.raise_for_status()
            payload = await response.text()

    print(f"Profile: {proxy.profile}")
    print(f"Proxy: {proxy.redacted_server}")
    print(f"Exit IP: {parse_exit_ip(payload)}")


if __name__ == "__main__":
    asyncio.run(main())
