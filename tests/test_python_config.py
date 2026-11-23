from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "examples" / "python"))

from proxy_config import load_https_proxy, parse_exit_ip  # noqa: E402


class ProxyConfigTests(unittest.TestCase):
    def environment(self) -> dict[str, str]:
        return {
            "PROXY_PROFILE": "mobile",
            "MOBILE_HTTPS_PROXY_SERVER": "https://proxy.example:20000",
            "MOBILE_HTTPS_PROXY_USERNAME": "user@example",
            "MOBILE_HTTPS_PROXY_PASSWORD": "p@ss:word",
        }

    def test_loads_and_redacts_mobile_proxy(self) -> None:
        with patch.dict(os.environ, self.environment(), clear=True):
            proxy = load_https_proxy()
        self.assertEqual(proxy.profile, "mobile")
        self.assertEqual(proxy.redacted_server, "https://proxy.example:20000")
        self.assertNotIn(proxy.password, proxy.redacted_server)

    def test_encodes_credentials_for_url_clients(self) -> None:
        with patch.dict(os.environ, self.environment(), clear=True):
            proxy = load_https_proxy()
        self.assertEqual(
            proxy.authenticated_url,
            "https://user%40example:p%40ss%3Aword@proxy.example:20000",
        )

    def test_parses_ip_check_responses(self) -> None:
        self.assertEqual(parse_exit_ip('{"ip":"203.0.113.8"}'), "203.0.113.8")
        self.assertEqual(parse_exit_ip("2001:db8::8\n"), "2001:db8::8")
        with self.assertRaises(RuntimeError):
            parse_exit_ip("not an IP")

    def test_rejects_embedded_credentials(self) -> None:
        values = self.environment()
        values["MOBILE_HTTPS_PROXY_SERVER"] = (
            "https://embedded:secret@proxy.example:20000"
        )
        with patch.dict(os.environ, values, clear=True):
            with self.assertRaisesRegex(ValueError, "must not contain credentials"):
                load_https_proxy()


if __name__ == "__main__":
    unittest.main()
