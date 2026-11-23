"""Verify a Proxidize HTTPS access point with Requests."""

from __future__ import annotations

import json
import sys

import requests

from proxy_config import (
    ip_check_url,
    load_https_proxy,
    parse_exit_ip,
    request_timeout_seconds,
)


def main() -> None:
    proxy = load_https_proxy()
    proxy_url = proxy.authenticated_url
    response = requests.get(
        ip_check_url(),
        proxies={"http": proxy_url, "https": proxy_url},
        timeout=request_timeout_seconds(),
    )
    response.raise_for_status()
    print(
        json.dumps(
            {
                "client": "requests",
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
        print(f"Requests proxy check failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
