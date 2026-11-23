"""Verify a Proxidize HTTPS access point with HTTPX."""

from __future__ import annotations

import json
import sys

import httpx

from proxy_config import (
    ip_check_url,
    load_https_proxy,
    parse_exit_ip,
    request_timeout_seconds,
)


def main() -> None:
    proxy = load_https_proxy()
    with httpx.Client(
        proxy=proxy.authenticated_url,
        timeout=request_timeout_seconds(),
        follow_redirects=True,
        verify=True,
    ) as client:
        response = client.get(ip_check_url())
        response.raise_for_status()

    print(
        json.dumps(
            {
                "client": "httpx",
                "profile": proxy.profile,
                "proxy": proxy.redacted_server,
                "exit_ip": parse_exit_ip(response.text),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"HTTPX proxy check failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
