"""Use an IP-allowlisted Proxidize endpoint with Selenium and Chromium."""

from __future__ import annotations

import ipaddress
import json
import os
import sys
from urllib.parse import urlsplit

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By


def main() -> None:
    server = os.getenv("SELENIUM_PROXY_SERVER", "").strip()
    if not server:
        raise ValueError("SELENIUM_PROXY_SERVER is required")
    parsed = urlsplit(server)
    if parsed.scheme not in {"http", "https", "socks5"} or not parsed.hostname:
        raise ValueError(
            "SELENIUM_PROXY_SERVER must be an absolute http://, https://, or socks5:// URL"
        )
    if parsed.username is not None or parsed.password is not None:
        raise ValueError(
            "Do not put credentials in SELENIUM_PROXY_SERVER. Configure an "
            "IP-allowlisted endpoint in the Proxidize dashboard."
        )

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument(f"--proxy-server={server}")
    driver = webdriver.Chrome(options=options)
    try:
        driver.set_page_load_timeout(float(os.getenv("REQUEST_TIMEOUT_SECONDS", "30")))
        driver.get(os.getenv("IP_CHECK_URL", "https://api.ipify.org?format=json"))
        payload = driver.find_element(By.TAG_NAME, "body").text.strip()
        try:
            candidate = json.loads(payload)["ip"]
        except (KeyError, TypeError, json.JSONDecodeError):
            candidate = payload
        exit_ip = str(ipaddress.ip_address(str(candidate).strip()))
    finally:
        driver.quit()

    print(
        json.dumps(
            {
                "client": "selenium-python",
                "authentication": "ip-allowlist",
                "proxy": f"{parsed.scheme}://{parsed.netloc}",
                "exit_ip": exit_ip,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Selenium proxy check failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
