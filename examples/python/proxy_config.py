"""Shared, environment-driven configuration for the Python examples."""

from __future__ import annotations

import ipaddress
import json
import os
from dataclasses import dataclass
from urllib.parse import quote, urlsplit, urlunsplit


PROFILE_PREFIXES = {
    "mobile": "MOBILE_HTTPS_PROXY",
    "residential": "RESIDENTIAL_HTTPS_PROXY",
}


@dataclass(frozen=True)
class HttpsProxy:
    profile: str
    server: str
    username: str
    password: str

    @property
    def authenticated_url(self) -> str:
        parsed = urlsplit(self.server)
        netloc = (
            f"{quote(self.username, safe='')}:{quote(self.password, safe='')}"
            f"@{parsed.netloc}"
        )
        return urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))

    @property
    def redacted_server(self) -> str:
        parsed = urlsplit(self.server)
        return urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))

    @property
    def playwright_settings(self) -> dict[str, str]:
        return {
            "server": self.server,
            "username": self.username,
            "password": self.password,
        }


def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"{name} is required")
    return value


def positive_number(name: str, fallback: str) -> float:
    raw = os.getenv(name, fallback)
    try:
        value = float(raw)
    except ValueError as error:
        raise ValueError(f"{name} must be a number") from error
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return value


def selected_profile() -> str:
    profile = os.getenv("PROXY_PROFILE", "mobile").strip().lower()
    if profile not in PROFILE_PREFIXES:
        raise ValueError('PROXY_PROFILE must be "mobile" or "residential"')
    return profile


def load_https_proxy(profile: str | None = None) -> HttpsProxy:
    chosen = profile or selected_profile()
    try:
        prefix = PROFILE_PREFIXES[chosen]
    except KeyError as error:
        raise ValueError(f"Unsupported proxy profile: {chosen}") from error

    server = required(f"{prefix}_SERVER")
    parsed = urlsplit(server)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError(f"{prefix}_SERVER must use http:// or https://")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError(
            f"{prefix}_SERVER must not contain credentials; use the username "
            "and password variables"
        )

    return HttpsProxy(
        profile=chosen,
        server=server.rstrip("/"),
        username=required(f"{prefix}_USERNAME"),
        password=required(f"{prefix}_PASSWORD"),
    )


def parse_exit_ip(payload: str) -> str:
    text = payload.strip()
    candidate: object = text
    try:
        candidate = json.loads(text).get("ip")
    except (AttributeError, json.JSONDecodeError):
        pass
    try:
        return str(ipaddress.ip_address(str(candidate).strip()))
    except ValueError as error:
        raise RuntimeError(f"Unexpected IP-check response: {text[:160]!r}") from error


def ip_check_url() -> str:
    return os.getenv("IP_CHECK_URL", "https://api.ipify.org?format=json")


def request_timeout_seconds() -> float:
    return positive_number("REQUEST_TIMEOUT_SECONDS", "30")


def navigation_timeout_ms() -> float:
    return positive_number("NAVIGATION_TIMEOUT_MS", "30000")
