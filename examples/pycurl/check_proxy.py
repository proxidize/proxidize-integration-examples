from __future__ import annotations

from io import BytesIO
from pathlib import Path
import sys

import pycurl

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))

from proxy_config import (  # noqa: E402
    ip_check_url,
    load_https_proxy,
    parse_exit_ip,
    request_timeout_seconds,
)


proxy = load_https_proxy()
buffer = BytesIO()
client = pycurl.Curl()

try:
    client.setopt(pycurl.URL, ip_check_url())
    client.setopt(pycurl.PROXY, proxy.server)
    client.setopt(pycurl.PROXYUSERNAME, proxy.username)
    client.setopt(pycurl.PROXYPASSWORD, proxy.password)
    client.setopt(pycurl.CONNECTTIMEOUT, int(request_timeout_seconds()))
    client.setopt(pycurl.TIMEOUT, int(request_timeout_seconds()))
    client.setopt(pycurl.FAILONERROR, True)
    client.setopt(pycurl.WRITEFUNCTION, buffer.write)
    client.perform()
finally:
    client.close()

print(f"Profile: {proxy.profile}")
print(f"Proxy: {proxy.redacted_server}")
print(f"Exit IP: {parse_exit_ip(buffer.getvalue().decode('utf-8'))}")
