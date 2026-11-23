"""Validate mobile UDP-over-SOCKS5 with an authenticated QUIC handshake."""

from __future__ import annotations

import ipaddress
import json
import os
import socket
import ssl
import struct
import sys
import time
from dataclasses import dataclass

import certifi
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.connection import QuicConnection
from aioquic.quic.events import ConnectionTerminated, HandshakeCompleted


SOCKS_REPLY = {
    0x01: "general SOCKS server failure",
    0x02: "connection not allowed by ruleset",
    0x03: "network unreachable",
    0x04: "host unreachable",
    0x05: "connection refused",
    0x06: "TTL expired",
    0x07: "command not supported",
    0x08: "address type not supported",
}


@dataclass(frozen=True)
class Settings:
    proxy_host: str
    proxy_port: int
    username: str
    password: str
    target_host: str
    target_port: int
    timeout: float


def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"{name} is required")
    return value


def integer(name: str, fallback: str | None = None) -> int:
    value = os.getenv(name, fallback or "").strip()
    try:
        parsed = int(value)
    except ValueError as error:
        raise ValueError(f"{name} must be an integer") from error
    if not 1 <= parsed <= 65535:
        raise ValueError(f"{name} must be between 1 and 65535")
    return parsed


def load_settings() -> Settings:
    target_port = integer("UDP_TARGET_PORT", "443")
    if target_port not in {80, 443}:
        raise ValueError("UDP_TARGET_PORT must be 80 or 443")
    try:
        timeout = float(os.getenv("UDP_TIMEOUT_SECONDS", "15"))
    except ValueError as error:
        raise ValueError("UDP_TIMEOUT_SECONDS must be a number") from error
    if not 1 <= timeout <= 60:
        raise ValueError("UDP_TIMEOUT_SECONDS must be between 1 and 60")

    return Settings(
        proxy_host=required("MOBILE_SOCKS5_PROXY_HOST"),
        proxy_port=integer("MOBILE_SOCKS5_PROXY_PORT"),
        username=required("MOBILE_SOCKS5_PROXY_USERNAME"),
        password=required("MOBILE_SOCKS5_PROXY_PASSWORD"),
        target_host=os.getenv("UDP_TARGET_HOST", "cloudflare.com").strip(),
        target_port=target_port,
        timeout=timeout,
    )


def receive_exact(connection: socket.socket, size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining:
        chunk = connection.recv(remaining)
        if not chunk:
            raise ConnectionError("the SOCKS5 control connection closed early")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def encode_socks_address(host: str) -> tuple[int, bytes]:
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        encoded = host.encode("idna")
        if not 1 <= len(encoded) <= 255:
            raise ValueError("SOCKS5 domain names must contain 1 to 255 bytes")
        return 0x03, bytes([len(encoded)]) + encoded
    if address.version == 4:
        return 0x01, address.packed
    return 0x04, address.packed


def receive_socks_address(connection: socket.socket, address_type: int) -> str:
    if address_type == 0x01:
        return socket.inet_ntop(socket.AF_INET, receive_exact(connection, 4))
    if address_type == 0x04:
        return socket.inet_ntop(socket.AF_INET6, receive_exact(connection, 16))
    if address_type == 0x03:
        length = receive_exact(connection, 1)[0]
        if length == 0:
            raise ValueError("SOCKS5 returned an empty relay hostname")
        return receive_exact(connection, length).decode("idna")
    raise ValueError(f"unsupported SOCKS5 address type 0x{address_type:02x}")


def decode_socks_address(
    packet: bytes, offset: int, address_type: int
) -> tuple[str, int]:
    if address_type == 0x01:
        end = offset + 4
        if end > len(packet):
            raise ValueError("truncated IPv4 address in SOCKS5 UDP packet")
        return socket.inet_ntop(socket.AF_INET, packet[offset:end]), end
    if address_type == 0x04:
        end = offset + 16
        if end > len(packet):
            raise ValueError("truncated IPv6 address in SOCKS5 UDP packet")
        return socket.inet_ntop(socket.AF_INET6, packet[offset:end]), end
    if address_type == 0x03:
        if offset >= len(packet):
            raise ValueError("missing domain length in SOCKS5 UDP packet")
        length = packet[offset]
        start = offset + 1
        end = start + length
        if length == 0 or end > len(packet):
            raise ValueError("invalid domain in SOCKS5 UDP packet")
        return packet[start:end].decode("idna"), end
    raise ValueError(f"unsupported SOCKS5 UDP address type 0x{address_type:02x}")


def authenticate(
    connection: socket.socket, username: str, password: str
) -> None:
    connection.sendall(b"\x05\x01\x02")
    version, method = receive_exact(connection, 2)
    if version != 0x05:
        raise RuntimeError(f"unexpected SOCKS version 0x{version:02x}")
    if method != 0x02:
        raise RuntimeError(
            f"the proxy did not select username/password authentication (0x{method:02x})"
        )

    username_bytes = username.encode("utf-8")
    password_bytes = password.encode("utf-8")
    if not 1 <= len(username_bytes) <= 255:
        raise ValueError("the username must contain 1 to 255 bytes")
    if not 1 <= len(password_bytes) <= 255:
        raise ValueError("the password must contain 1 to 255 bytes")
    request = (
        bytes([0x01, len(username_bytes)])
        + username_bytes
        + bytes([len(password_bytes)])
        + password_bytes
    )
    connection.sendall(request)
    auth_version, status = receive_exact(connection, 2)
    if auth_version != 0x01 or status != 0x00:
        raise RuntimeError("the SOCKS5 proxy rejected the supplied credentials")


def request_udp_association(
    connection: socket.socket, udp_socket: socket.socket
) -> tuple[str, int]:
    local_host, local_port = udp_socket.getsockname()[:2]
    address_type, encoded_address = encode_socks_address(local_host)
    request = (
        b"\x05\x03\x00"
        + bytes([address_type])
        + encoded_address
        + struct.pack("!H", local_port)
    )
    connection.sendall(request)

    version, reply, reserved, address_type = receive_exact(connection, 4)
    if version != 0x05 or reserved != 0x00:
        raise RuntimeError("the proxy returned an invalid UDP ASSOCIATE response")
    if reply != 0x00:
        meaning = SOCKS_REPLY.get(reply, "unassigned reply code")
        raise RuntimeError(
            f"the proxy rejected UDP ASSOCIATE: 0x{reply:02x} ({meaning})"
        )
    relay_host = receive_socks_address(connection, address_type)
    relay_port = struct.unpack("!H", receive_exact(connection, 2))[0]
    if relay_port == 0:
        raise RuntimeError("the proxy returned UDP relay port 0")

    try:
        relay_address = ipaddress.ip_address(relay_host)
    except ValueError:
        relay_address = None
    if relay_address is not None and relay_address.is_unspecified:
        relay_host = connection.getpeername()[0]
    return relay_host, relay_port


def resolve_udp_endpoint(
    host: str, port: int, family: socket.AddressFamily
) -> tuple[tuple, set[tuple[str, int]]]:
    records = socket.getaddrinfo(host, port, family, socket.SOCK_DGRAM)
    if not records:
        raise OSError("the UDP relay address did not resolve")
    endpoint = records[0][4]
    accepted = {
        (str(ipaddress.ip_address(record[4][0])), record[4][1])
        for record in records
    }
    return endpoint, accepted


def wrap_udp_datagram(destination: tuple, payload: bytes) -> bytes:
    address_type, encoded_address = encode_socks_address(destination[0])
    return (
        b"\x00\x00\x00"
        + bytes([address_type])
        + encoded_address
        + struct.pack("!H", destination[1])
        + payload
    )


def unwrap_udp_datagram(packet: bytes) -> tuple[str, int, bytes]:
    if len(packet) < 4 or packet[:2] != b"\x00\x00":
        raise ValueError("invalid SOCKS5 UDP response header")
    if packet[2] != 0:
        raise ValueError("fragmented SOCKS5 UDP responses are unsupported")
    host, offset = decode_socks_address(packet, 4, packet[3])
    if offset + 2 > len(packet):
        raise ValueError("SOCKS5 UDP response is missing its remote port")
    port = struct.unpack("!H", packet[offset : offset + 2])[0]
    payload = packet[offset + 2 :]
    if not payload:
        raise ValueError("SOCKS5 UDP response contains no payload")
    return host, port, payload


def run_check(settings: Settings) -> dict[str, object]:
    started = time.monotonic()
    control: socket.socket | None = None
    udp_socket: socket.socket | None = None
    response_count = 0
    stage = "configuration"

    try:
        stage = "tcp_connect"
        control = socket.create_connection(
            (settings.proxy_host, settings.proxy_port), timeout=settings.timeout
        )
        control.settimeout(settings.timeout)

        stage = "authentication"
        authenticate(control, settings.username, settings.password)

        local_host = control.getsockname()[0]
        udp_socket = socket.socket(control.family, socket.SOCK_DGRAM)
        udp_socket.settimeout(0.25)
        if control.family == socket.AF_INET6:
            udp_socket.bind((local_host, 0, 0, 0))
        else:
            udp_socket.bind((local_host, 0))

        stage = "udp_associate"
        relay_host, relay_port = request_udp_association(control, udp_socket)
        relay_endpoint, accepted_relay_sources = resolve_udp_endpoint(
            relay_host, relay_port, control.family
        )

        stage = "target_resolution"
        target_records = socket.getaddrinfo(
            settings.target_host,
            settings.target_port,
            control.family,
            socket.SOCK_DGRAM,
        )
        if not target_records:
            raise OSError("the QUIC target did not resolve")
        target_address = target_records[0][4]

        configuration = QuicConfiguration(
            is_client=True,
            alpn_protocols=["h3"],
            server_name=settings.target_host,
            cafile=certifi.where(),
            verify_mode=ssl.CERT_REQUIRED,
        )
        quic = QuicConnection(configuration=configuration)
        quic.connect(target_address, time.time())

        stage = "quic_handshake"
        deadline = time.monotonic() + settings.timeout
        termination: str | None = None
        passed = False
        while time.monotonic() < deadline and not passed and termination is None:
            now = time.time()
            for payload, destination in quic.datagrams_to_send(now):
                udp_socket.sendto(
                    wrap_udp_datagram(destination, payload), relay_endpoint
                )

            try:
                packet, sender = udp_socket.recvfrom(65535)
                sender_key = (
                    str(ipaddress.ip_address(sender[0])),
                    sender[1],
                )
                if sender_key not in accepted_relay_sources:
                    continue
                remote_host, remote_port, payload = unwrap_udp_datagram(packet)
                response_count += 1
                quic.receive_datagram(
                    payload, (remote_host, remote_port), time.time()
                )
            except socket.timeout:
                pass

            while True:
                event = quic.next_event()
                if event is None:
                    break
                if isinstance(event, HandshakeCompleted):
                    passed = True
                elif isinstance(event, ConnectionTerminated):
                    termination = (
                        f"QUIC connection terminated with code {event.error_code}"
                    )

            timer = quic.get_timer()
            if timer is not None and timer <= time.time():
                quic.handle_timer(time.time())

        if not passed:
            raise TimeoutError(
                termination or "timed out waiting for the QUIC handshake"
            )

        return {
            "passed": True,
            "authentication": "username_password",
            "udp_associate": "accepted",
            "udp_responses": response_count,
            "quic_handshake": "completed",
            "target": settings.target_host,
            "target_port": settings.target_port,
            "elapsed_ms": round((time.monotonic() - started) * 1000, 1),
        }
    except Exception as error:
        return {
            "passed": False,
            "stage": stage,
            "error": str(error),
            "target": settings.target_host,
            "target_port": settings.target_port,
            "elapsed_ms": round((time.monotonic() - started) * 1000, 1),
        }
    finally:
        if udp_socket is not None:
            udp_socket.close()
        if control is not None:
            control.close()


def main() -> int:
    try:
        settings = load_settings()
        result = run_check(settings)
    except Exception as error:
        result = {"passed": False, "stage": "configuration", "error": str(error)}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
