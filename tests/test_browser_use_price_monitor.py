from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "examples"
    / "browser-use-price-monitor"
    / "price_monitor.py"
)
SPEC = importlib.util.spec_from_file_location("browser_use_price_monitor", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("could not load the Browser Use price monitor")
MONITOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MONITOR
SPEC.loader.exec_module(MONITOR)


def output(country: str = "US", source_url: str = "https://example.com/product"):
    return {
        "status": "ok",
        "product_name": "Demo shoes",
        "price": "129.00",
        "currency": "USD",
        "source_url": source_url,
        "observed_country_code": country,
        "observed_region": "New York",
        "observed_city": "New York",
        "evidence": "The product card showed USD 129.00.",
        "error": "",
    }


class FakeRuns:
    def __init__(self, result: dict[str, object]) -> None:
        self.result = result
        self.created = None

    def create(self, task, **kwargs):
        self.created = {"task": task, **kwargs}
        return SimpleNamespace(id="run-created")

    def wait_for_completion(self, run_id, **kwargs):
        return SimpleNamespace(
            id=run_id,
            status="completed",
            output=self.result,
            error=None,
            total_cost_usd="0.08",
        )


class BrowserUsePriceMonitorTests(unittest.TestCase):
    def route(self, mode: str = "sticky"):
        return MONITOR.ProxyRoute(
            label=f"us-{mode}",
            country_code="US",
            session_mode=mode,
            username="account-session-us" if mode == "sticky" else None,
            username_template=(
                "account-s-{session_id}-co-US" if mode == "rotating" else None
            ),
        )

    def config(self, database_path: Path):
        return MONITOR.MonitorConfig(
            browser_use_api_key="browser-use-secret",
            target_url="https://example.com/product",
            product_hint="Demo shoes",
            geo_check_url="https://ipwho.is/",
            model="bu-4.0-mini",
            max_cost_usd=Decimal("1.00"),
            timeout_seconds=60,
            endpoint=MONITOR.ProxyEndpoint(
                host="proxy.example",
                port=20000,
                protocol="https",
                password="proxy-secret",
            ),
            database_path=database_path,
        )

    def test_rotating_route_changes_session_and_sticky_route_does_not(self) -> None:
        rotating = self.route("rotating")
        first = rotating.username_for_observation()
        second = rotating.username_for_observation()
        self.assertNotEqual(first, second)
        self.assertNotIn("{session_id}", first)
        sticky = self.route("sticky")
        self.assertEqual(
            sticky.username_for_observation(), sticky.username_for_observation()
        )

    def test_rejects_an_unsafe_rotating_template(self) -> None:
        with self.assertRaisesRegex(ValueError, "one .*session_id"):
            MONITOR.ProxyRoute(
                label="bad-route",
                country_code="US",
                session_mode="rotating",
                username_template="account-{country}-{session_id}",
            )

    def test_validates_country_source_currency_and_price(self) -> None:
        observation = MONITOR.validate_agent_output(
            output(),
            target_url="https://example.com/product",
            route=self.route(),
            run_id="run-1",
        )
        self.assertEqual(observation.price, Decimal("129.00"))
        self.assertEqual(observation.currency, "USD")

        with self.assertRaisesRegex(ValueError, "did not match"):
            MONITOR.validate_agent_output(
                output(country="GB"),
                target_url="https://example.com/product",
                route=self.route(),
                run_id="run-2",
            )
        with self.assertRaisesRegex(ValueError, "unsigned decimal"):
            bad = output()
            bad["price"] = "$129.00"
            MONITOR.validate_agent_output(
                bad,
                target_url="https://example.com/product",
                route=self.route(),
                run_id="run-3",
            )

    def test_rejects_city_mismatch_and_credential_bearing_source_url(self) -> None:
        city_route = MONITOR.ProxyRoute(
            label="us-miami",
            country_code="US",
            session_mode="sticky",
            username="account-session-us-miami",
            expected_city="Miami",
        )
        with self.assertRaisesRegex(ValueError, "city .* did not match"):
            MONITOR.validate_agent_output(
                output(),
                target_url="https://example.com/product",
                route=city_route,
                run_id="run-city",
            )
        with self.assertRaisesRegex(ValueError, "must not contain credentials"):
            MONITOR.canonical_https_url(
                "https://user:password@example.com/product",
                "source_url",
            )

    def test_builds_a_bounded_cloud_v4_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = self.config(Path(directory) / "history.sqlite3")
            runs = FakeRuns(output())
            observation = MONITOR.collect_observation(runs, config, self.route())

        self.assertEqual(observation.run_id, "run-created")
        self.assertEqual(runs.created["model"], "bu-4.0-mini")
        self.assertEqual(runs.created["max_cost_usd"], "1.00")
        proxy = runs.created["browser_settings"]["customProxy"]
        self.assertEqual(proxy["protocol"], "https")
        self.assertFalse(proxy["ignoreCertErrors"])
        self.assertIn("Do not sign in", runs.created["task"])
        self.assertIn("Never return or mention the exit IP", runs.created["task"])

    def test_records_baseline_then_change_by_route(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = MONITOR.MonitorStore(Path(directory) / "history.sqlite3")
            try:
                first = MONITOR.validate_agent_output(
                    output(),
                    target_url="https://example.com/product",
                    route=self.route(),
                    run_id="run-1",
                )
                changed_output = output()
                changed_output["price"] = "119.00"
                second = MONITOR.validate_agent_output(
                    changed_output,
                    target_url="https://example.com/product",
                    route=self.route(),
                    run_id="run-2",
                )
                baseline = store.record("demo", first)
                changed = store.record("demo", second)
            finally:
                store.close()

        self.assertEqual(baseline["status"], "baseline")
        self.assertEqual(changed, {"status": "changed", "difference": "-10.00"})

    def test_rejects_currency_change_before_recording_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = MONITOR.MonitorStore(Path(directory) / "history.sqlite3")
            try:
                first = MONITOR.validate_agent_output(
                    output(),
                    target_url="https://example.com/product",
                    route=self.route(),
                    run_id="run-usd",
                )
                euro_output = output()
                euro_output["currency"] = "EUR"
                second = MONITOR.validate_agent_output(
                    euro_output,
                    target_url="https://example.com/product",
                    route=self.route(),
                    run_id="run-eur",
                )
                store.record("demo", first)
                with self.assertRaisesRegex(ValueError, "currency changed"):
                    store.record("demo", second)
                self.assertEqual(len(store.history()), 1)
            finally:
                store.close()

    def test_fixture_never_prints_credentials(self) -> None:
        fixture = MODULE_PATH.parent / "fixtures" / "us-observation.json"
        with tempfile.TemporaryDirectory() as directory:
            result = MONITOR.run_fixture(fixture, Path(directory) / "fixture.sqlite3")
        serialized = json.dumps(result)
        self.assertNotIn("password", serialized.lower())
        self.assertNotIn("username", serialized.lower())

    def test_redacts_secrets_and_credentials_from_errors(self) -> None:
        error = RuntimeError(
            "request failed for https://demo:proxy-secret@proxy.example "
            '{"api_key":"browser-secret","password":"proxy-secret"}'
        )
        message = MONITOR.redact_error(
            error,
            ["browser-secret", "proxy-secret"],
        )
        self.assertNotIn("browser-secret", message)
        self.assertNotIn("proxy-secret", message)
        self.assertNotIn("demo:", message)
        self.assertIn("[REDACTED]", message)


if __name__ == "__main__":
    unittest.main()
