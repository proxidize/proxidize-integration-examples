from __future__ import annotations

import importlib.util
import socket
import struct
import sys
import unittest
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "examples" / "mobile-udp" / "quic_check.py"
)
SPEC = importlib.util.spec_from_file_location("quic_check", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("could not load the mobile UDP checker")
CHECKER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = CHECKER
SPEC.loader.exec_module(CHECKER)


class MobileUdpTests(unittest.TestCase):
    def test_round_trips_ipv4_udp_envelope(self) -> None:
        destination = ("203.0.113.9", 443)
        payload = b"quic-test-payload"
        packet = CHECKER.wrap_udp_datagram(destination, payload)
        host, port, decoded = CHECKER.unwrap_udp_datagram(packet)
        self.assertEqual((host, port, decoded), (*destination, payload))

    def test_round_trips_domain_udp_envelope(self) -> None:
        address_type, encoded = CHECKER.encode_socks_address("example.com")
        packet = (
            b"\x00\x00\x00"
            + bytes([address_type])
            + encoded
            + struct.pack("!H", 443)
            + b"payload"
        )
        self.assertEqual(
            CHECKER.unwrap_udp_datagram(packet),
            ("example.com", 443, b"payload"),
        )

    def test_rejects_fragmented_response(self) -> None:
        packet = b"\x00\x00\x01\x01" + socket.inet_aton("203.0.113.9")
        packet += struct.pack("!H", 443) + b"payload"
        with self.assertRaisesRegex(ValueError, "fragmented"):
            CHECKER.unwrap_udp_datagram(packet)


if __name__ == "__main__":
    unittest.main()
