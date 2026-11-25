from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from email.utils import parseaddr
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable, Iterable, Protocol
from urllib.parse import urlsplit

import httpx
from agentmail import AgentMail
from agentmail.inboxes import CreateInboxRequest


EXAMPLES_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXAMPLES_ROOT / "python"))

from proxy_config import HttpsProxy, load_https_proxy  # noqa: E402


@dataclass(frozen=True)
class ProductSnapshot:
    name: str
    price: Decimal
    currency: str
    source_url: str
    observed_at: datetime


@dataclass(frozen=True)
class PriceChange:
    product_key: str
    previous: ProductSnapshot
    current: ProductSnapshot
    event_id: str

    @property
    def difference(self) -> Decimal:
        return self.current.price - self.previous.price

    @property
    def percentage(self) -> Decimal:
        if self.previous.price == 0:
            return Decimal("0")
        return self.difference / self.previous.price * Decimal("100")


@dataclass(frozen=True)
class SendResult:
    message_id: str
    thread_id: str


class MailGateway(Protocol):
    inbox_id: str

    def send_change(self, change: PriceChange, recipient: str) -> SendResult: ...

    def reply(self, message_id: str, text: str, event_id: str) -> SendResult: ...


class ProductMarkupParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.attribute_products: list[dict[str, str]] = []
        self.json_ld: list[str] = []
        self.meta_price: str | None = None
        self.meta_currency: str | None = None
        self.meta_name: str | None = None
        self._json_depth = 0
        self._json_buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.lower(): value or "" for key, value in attrs}
        if "data-price" in values:
            self.attribute_products.append(values)

        if tag.lower() == "meta":
            itemprop = values.get("itemprop", "").lower()
            property_name = values.get("property", "").lower()
            content = values.get("content", "")
            if itemprop == "price" or property_name == "product:price:amount":
                self.meta_price = content
            elif (
                itemprop == "pricecurrency" or property_name == "product:price:currency"
            ):
                self.meta_currency = content
            elif itemprop == "name" or property_name in {"og:title", "product:name"}:
                self.meta_name = content

        if tag.lower() == "script" and values.get("type", "").lower() == (
            "application/ld+json"
        ):
            self._json_depth += 1
            self._json_buffer = []

    def handle_data(self, data: str) -> None:
        if self._json_depth:
            self._json_buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "script" and self._json_depth:
            self._json_depth -= 1
            payload = "".join(self._json_buffer).strip()
            if payload:
                self.json_ld.append(payload)
            self._json_buffer = []


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_price(value: object) -> Decimal:
    text = str(value).strip().replace("\u00a0", "").replace(" ", "")
    filtered = "".join(character for character in text if character in "0123456789,.-")
    if not filtered:
        raise ValueError(f"Could not parse a price from {value!r}")
    if "," in filtered and "." in filtered:
        if filtered.rfind(",") > filtered.rfind("."):
            filtered = filtered.replace(".", "").replace(",", ".")
        else:
            filtered = filtered.replace(",", "")
    elif filtered.count(",") == 1:
        left, right = filtered.split(",")
        filtered = f"{left}.{right}" if len(right) == 2 else left + right
    else:
        filtered = filtered.replace(",", "")
    try:
        price = Decimal(filtered)
    except InvalidOperation as error:
        raise ValueError(f"Could not parse a price from {value!r}") from error
    if not price.is_finite() or price < 0:
        raise ValueError("Price must be a finite, non-negative number")
    return price.quantize(Decimal("0.01"))


def iter_json_objects(value: object) -> Iterable[dict[str, object]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from iter_json_objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_json_objects(child)


def product_from_json_ld(
    payloads: Iterable[str], source_url: str, observed_at: datetime
) -> ProductSnapshot | None:
    candidates: list[ProductSnapshot] = []
    for payload in payloads:
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError:
            continue
        for item in iter_json_objects(decoded):
            item_type = item.get("@type")
            types = item_type if isinstance(item_type, list) else [item_type]
            if not any(str(value).lower() == "product" for value in types):
                continue
            offers = item.get("offers")
            offer_items = offers if isinstance(offers, list) else [offers]
            for offer in offer_items:
                if not isinstance(offer, dict) or offer.get("price") is None:
                    continue
                currency = str(offer.get("priceCurrency") or "").strip().upper()
                if len(currency) != 3:
                    continue
                candidates.append(
                    ProductSnapshot(
                        name=str(item.get("name") or "Monitored product").strip(),
                        price=parse_price(offer["price"]),
                        currency=currency,
                        source_url=source_url,
                        observed_at=observed_at,
                    )
                )
    if not candidates:
        return None
    unique = {(item.price, item.currency, item.name) for item in candidates}
    if len(unique) != 1:
        raise ValueError("The page contains multiple conflicting product offers")
    return candidates[0]


def extract_product(
    markup: str, source_url: str, observed_at: datetime | None = None
) -> ProductSnapshot:
    timestamp = observed_at or utc_now()
    parser = ProductMarkupParser()
    parser.feed(markup)

    structured = product_from_json_ld(parser.json_ld, source_url, timestamp)
    if structured is not None:
        return structured

    if parser.attribute_products:
        products = []
        for values in parser.attribute_products:
            currency = values.get("data-currency", "").strip().upper()
            if len(currency) != 3:
                raise ValueError(
                    "data-currency must contain a three-letter currency code"
                )
            products.append(
                ProductSnapshot(
                    name=values.get("data-product-name", "Monitored product").strip(),
                    price=parse_price(values["data-price"]),
                    currency=currency,
                    source_url=source_url,
                    observed_at=timestamp,
                )
            )
        unique = {(item.price, item.currency, item.name) for item in products}
        if len(unique) != 1:
            raise ValueError("The page contains multiple conflicting data-price values")
        return products[0]

    if parser.meta_price and parser.meta_currency:
        currency = parser.meta_currency.strip().upper()
        if len(currency) != 3:
            raise ValueError("The product price currency is invalid")
        return ProductSnapshot(
            name=(parser.meta_name or "Monitored product").strip(),
            price=parse_price(parser.meta_price),
            currency=currency,
            source_url=source_url,
            observed_at=timestamp,
        )

    raise ValueError(
        "No unambiguous product price found. Provide Product JSON-LD, product price "
        "meta tags, or data-price/data-currency attributes."
    )


def fetch_markup(url: str, proxy: HttpsProxy, timeout_seconds: float) -> str:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("PRICE_MONITOR_URL must use http:// or https://")
    headers = {
        "Accept": "text/html,application/xhtml+xml",
        "User-Agent": "ProxidizePriceMonitor/1.0 (+https://proxidize.com/)",
    }
    with httpx.Client(
        proxy=proxy.authenticated_url,
        timeout=timeout_seconds,
        follow_redirects=True,
        headers=headers,
    ) as client:
        response = client.get(url)
        response.raise_for_status()
        if len(response.content) > 5_000_000:
            raise RuntimeError("Response exceeded the 5 MB safety limit")
        return response.text


def snapshot_from_row(row: sqlite3.Row) -> ProductSnapshot:
    return ProductSnapshot(
        name=row["name"],
        price=Decimal(row["price"]),
        currency=row["currency"],
        source_url=row["source_url"],
        observed_at=datetime.fromisoformat(row["observed_at"]),
    )


class MonitorStore:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_key TEXT NOT NULL,
                name TEXT NOT NULL,
                price TEXT NOT NULL,
                currency TEXT NOT NULL,
                source_url TEXT NOT NULL,
                observed_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS observations_product_time
            ON observations(product_key, id DESC);

            CREATE TABLE IF NOT EXISTS alerts (
                event_id TEXT PRIMARY KEY,
                message_id TEXT,
                thread_id TEXT,
                sent_at TEXT
            );

            CREATE TABLE IF NOT EXISTS processed_messages (
                message_id TEXT PRIMARY KEY,
                processed_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS reply_outbox (
                message_id TEXT PRIMARY KEY,
                command TEXT NOT NULL,
                reply_text TEXT NOT NULL,
                event_id TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def latest(self, product_key: str) -> ProductSnapshot | None:
        row = self.connection.execute(
            """
            SELECT name, price, currency, source_url, observed_at
            FROM observations
            WHERE product_key = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (product_key,),
        ).fetchone()
        return snapshot_from_row(row) if row is not None else None

    def save(self, product_key: str, current: ProductSnapshot) -> None:
        self.connection.execute(
            """
            INSERT INTO observations (
                product_key, name, price, currency, source_url, observed_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                product_key,
                current.name,
                str(current.price),
                current.currency,
                current.source_url,
                current.observed_at.isoformat(),
            ),
        )
        self.connection.commit()

    def compare(
        self,
        product_key: str,
        previous: ProductSnapshot | None,
        current: ProductSnapshot,
    ) -> PriceChange | None:
        if previous is None:
            return None
        if previous.price == current.price and previous.currency == current.currency:
            return None
        if previous.currency != current.currency:
            raise ValueError(
                f"Currency changed from {previous.currency} to {current.currency}; "
                "no alert was generated"
            )
        event_payload = json.dumps(
            {
                "product_key": product_key,
                "previous_observed_at": previous.observed_at.isoformat(),
                "previous_price": str(previous.price),
                "current_name": current.name,
                "current_price": str(current.price),
                "currency": current.currency,
                "source_url": current.source_url,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        event_id = hashlib.sha256(event_payload.encode()).hexdigest()
        return PriceChange(product_key, previous, current, event_id)

    def record(self, product_key: str, current: ProductSnapshot) -> PriceChange | None:
        previous = self.latest(product_key)
        self.save(product_key, current)
        return self.compare(product_key, previous, current)

    def reserve_alert(self, event_id: str) -> bool:
        cursor = self.connection.execute(
            "INSERT OR IGNORE INTO alerts (event_id) VALUES (?)", (event_id,)
        )
        self.connection.commit()
        if cursor.rowcount == 1:
            return True
        row = self.connection.execute(
            "SELECT message_id FROM alerts WHERE event_id = ?", (event_id,)
        ).fetchone()
        return row is not None and row["message_id"] is None

    def complete_alert(self, event_id: str, result: SendResult) -> None:
        self.connection.execute(
            """
            UPDATE alerts
            SET message_id = ?, thread_id = ?, sent_at = ?
            WHERE event_id = ?
            """,
            (result.message_id, result.thread_id, utc_now().isoformat(), event_id),
        )
        self.connection.commit()

    def release_alert(self, event_id: str) -> None:
        self.connection.execute(
            "DELETE FROM alerts WHERE event_id = ? AND message_id IS NULL", (event_id,)
        )
        self.connection.commit()

    def is_message_processed(self, message_id: str) -> bool:
        row = self.connection.execute(
            "SELECT 1 FROM processed_messages WHERE message_id = ?", (message_id,)
        ).fetchone()
        return row is not None

    def mark_message_processed(self, message_id: str) -> None:
        self.connection.execute(
            """
            INSERT OR IGNORE INTO processed_messages (message_id, processed_at)
            VALUES (?, ?)
            """,
            (message_id, utc_now().isoformat()),
        )
        self.connection.commit()

    def prepared_reply(self, message_id: str) -> tuple[str, str, str] | None:
        row = self.connection.execute(
            """
            SELECT command, reply_text, event_id
            FROM reply_outbox
            WHERE message_id = ?
            """,
            (message_id,),
        ).fetchone()
        if row is None:
            return None
        return row["command"], row["reply_text"], row["event_id"]

    def prepare_reply(
        self, message_id: str, command: str, reply_text: str
    ) -> tuple[str, str, str]:
        event_id = hashlib.sha256(f"reply|{message_id}|{command}".encode()).hexdigest()
        self.connection.execute(
            """
            INSERT OR IGNORE INTO reply_outbox (
                message_id, command, reply_text, event_id, created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (message_id, command, reply_text, event_id, utc_now().isoformat()),
        )
        self.connection.commit()
        prepared = self.prepared_reply(message_id)
        if prepared is None:
            raise RuntimeError("Could not prepare a deterministic reply")
        return prepared

    def mute_for(self, duration: timedelta) -> datetime:
        muted_until = utc_now() + duration
        self.connection.execute(
            """
            INSERT INTO state (key, value) VALUES ('muted_until', ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (muted_until.isoformat(),),
        )
        self.connection.commit()
        return muted_until

    def is_muted(self) -> bool:
        row = self.connection.execute(
            "SELECT value FROM state WHERE key = 'muted_until'"
        ).fetchone()
        return row is not None and datetime.fromisoformat(row["value"]) > utc_now()

    def history(self, product_key: str, limit: int = 5) -> list[ProductSnapshot]:
        rows = self.connection.execute(
            """
            SELECT name, price, currency, source_url, observed_at
            FROM observations
            WHERE product_key = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (product_key, limit),
        ).fetchall()
        return [snapshot_from_row(row) for row in rows]


class AgentMailGateway:
    def __init__(
        self,
        api_key: str,
        client_id: str,
        inbox_id: str | None = None,
        display_name: str = "Price Monitor",
    ) -> None:
        self.client = AgentMail(api_key=api_key)
        identity = self.client.auth.me()
        scoped_inbox_id = getattr(identity, "inbox_id", None)

        if inbox_id:
            self.inbox_id = inbox_id
            self.email = inbox_id
        elif scoped_inbox_id:
            # An inbox-scoped key cannot create or list inboxes, but auth.me()
            # identifies the one inbox it can safely use.
            self.inbox_id = scoped_inbox_id
            self.email = scoped_inbox_id
        else:
            inbox = self.client.inboxes.create(
                request=CreateInboxRequest(
                    client_id=client_id,
                    display_name=display_name,
                    metadata={"integration": "proxidize-price-monitor"},
                )
            )
            self.inbox_id = inbox.inbox_id
            self.email = inbox.email

    def send_change(self, change: PriceChange, recipient: str) -> SendResult:
        direction = "decreased" if change.difference < 0 else "increased"
        text = (
            f"{change.current.name} {direction} in price.\n\n"
            f"Previous: {change.previous.currency} {change.previous.price}\n"
            f"Current: {change.current.currency} {change.current.price}\n"
            f"Change: {change.percentage:+.2f}%\n"
            f"Source: {change.current.source_url}\n\n"
            "Reply with: check now, show history, mute 24h, or help."
        )
        response = self.client.inboxes.messages.send(
            self.inbox_id,
            to=[recipient],
            subject=f"Price changed: {change.current.name}",
            text=text,
            labels=["price-monitor", "price-change"],
            idempotency_key=change.event_id,
        )
        return SendResult(response.message_id, response.thread_id)

    def reply(self, message_id: str, text: str, event_id: str) -> SendResult:
        response = self.client.inboxes.messages.reply(
            self.inbox_id,
            message_id,
            text=text,
            idempotency_key=event_id,
        )
        return SendResult(response.message_id, response.thread_id)


def require_environment(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"{name} is required")
    return value


def normalize_email(value: str) -> str:
    _, address = parseaddr(value)
    return address.strip().lower()


def positive_float(name: str, default: str) -> float:
    raw = os.getenv(name, default)
    try:
        value = float(raw)
    except ValueError as error:
        raise ValueError(f"{name} must be a number") from error
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return value


def gateway_from_environment() -> AgentMailGateway:
    return AgentMailGateway(
        api_key=require_environment("AGENTMAIL_API_KEY"),
        client_id=os.getenv(
            "PRICE_MONITOR_INBOX_CLIENT_ID", "proxidize-price-monitor-v1"
        ),
        inbox_id=os.getenv("AGENTMAIL_INBOX_ID", "").strip() or None,
    )


def monitor_once(
    store: MonitorStore,
    product_key: str,
    snapshot: ProductSnapshot,
    gateway: MailGateway | None,
    recipient: str | None,
) -> tuple[str, PriceChange | None]:
    previous = store.latest(product_key)
    try:
        change = store.compare(product_key, previous, snapshot)
    except ValueError:
        store.save(product_key, snapshot)
        raise
    if change is None:
        store.save(product_key, snapshot)
        return "recorded-no-change", None
    if store.is_muted():
        store.save(product_key, snapshot)
        return "recorded-muted", change
    if gateway is None or not recipient:
        store.save(product_key, snapshot)
        return "recorded-no-email", change
    if not store.reserve_alert(change.event_id):
        store.save(product_key, snapshot)
        return "duplicate-suppressed", change
    try:
        result = gateway.send_change(change, recipient)
    except Exception:
        store.release_alert(change.event_id)
        raise
    store.complete_alert(change.event_id, result)
    store.save(product_key, snapshot)
    return "alert-sent", change


SUPPORTED_COMMANDS = {
    "check now": "check-now",
    "show history": "show-history",
    "mute 24h": "mute-24h",
    "help": "help",
}


def parse_command(text: str) -> str | None:
    normalized = " ".join(text.strip().lower().split())
    return SUPPORTED_COMMANDS.get(normalized)


def format_history(items: Iterable[ProductSnapshot]) -> str:
    rows = list(items)
    if not rows:
        return "No confirmed observations are available yet."
    return "Recent confirmed observations:\n" + "\n".join(
        f"- {item.observed_at.isoformat()}: {item.currency} {item.price}"
        for item in rows
    )


def process_command(
    store: MonitorStore,
    gateway: MailGateway,
    *,
    message_id: str,
    sender: str,
    authorized_sender: str,
    body: str,
    product_key: str,
    run_check: Callable[[], str],
) -> str:
    if normalize_email(sender) != normalize_email(authorized_sender):
        return "unauthorized-sender"
    if store.is_message_processed(message_id):
        return "duplicate-message"

    prepared = store.prepared_reply(message_id)
    if prepared is None:
        command = parse_command(body)
        if command == "check-now":
            reply_text = run_check()
        elif command == "show-history":
            reply_text = format_history(store.history(product_key))
        elif command == "mute-24h":
            muted_until = store.mute_for(timedelta(hours=24))
            reply_text = f"Alerts are muted until {muted_until.isoformat()}."
        else:
            command = "help"
            reply_text = (
                "Supported commands: check now, show history, mute 24h, or help."
            )
        prepared = store.prepare_reply(message_id, command, reply_text)

    command, reply_text, event_id = prepared
    gateway.reply(message_id, reply_text, event_id)
    store.mark_message_processed(message_id)
    return command


def snapshot_from_args(args: argparse.Namespace) -> ProductSnapshot:
    if args.fixture:
        source_url = args.url or f"file://{Path(args.fixture).resolve()}"
        markup = Path(args.fixture).read_text(encoding="utf-8")
    else:
        source_url = args.url or require_environment("PRICE_MONITOR_URL")
        profile = os.getenv("PRICE_MONITOR_PROXY_PROFILE", "residential")
        proxy = load_https_proxy(profile)
        markup = fetch_markup(
            source_url,
            proxy,
            positive_float("REQUEST_TIMEOUT_SECONDS", "30"),
        )
    return extract_product(markup, source_url)


def selected_product_key(args: argparse.Namespace) -> str:
    return args.product_key or os.getenv("PRICE_MONITOR_PRODUCT_KEY", "demo-product")


def run_check(args: argparse.Namespace) -> int:
    store = MonitorStore(Path(args.database))
    try:
        snapshot = snapshot_from_args(args)
        product_key = selected_product_key(args)
        recipient = os.getenv("PRICE_MONITOR_OPERATOR_EMAIL", "").strip() or None
        gateway = (
            gateway_from_environment() if recipient and not args.no_email else None
        )
        status, change = monitor_once(store, product_key, snapshot, gateway, recipient)
        output = {
            "status": status,
            "product": snapshot.name,
            "price": str(snapshot.price),
            "currency": snapshot.currency,
            "changed": change is not None,
        }
        print(json.dumps(output, indent=2))
        return 0
    finally:
        store.close()


def run_inbox(args: argparse.Namespace) -> int:
    operator = require_environment("PRICE_MONITOR_OPERATOR_EMAIL")
    store = MonitorStore(Path(args.database))
    gateway = gateway_from_environment()
    product_key = selected_product_key(args)
    processed = []

    def manual_check() -> str:
        snapshot = snapshot_from_args(args)
        change = store.record(product_key, snapshot)
        if change is None:
            return (
                f"Check completed: {snapshot.currency} {snapshot.price}. "
                "No confirmed price change."
            )
        return (
            f"Check completed: {change.previous.currency} {change.previous.price} "
            f"to {change.current.currency} {change.current.price} "
            f"({change.percentage:+.2f}%)."
        )

    try:
        response = gateway.client.inboxes.messages.list(
            gateway.inbox_id,
            limit=args.limit,
            ascending=True,
            from_=[operator],
        )
        for message in response.messages:
            body = message.extracted_text or message.text or ""
            status = process_command(
                store,
                gateway,
                message_id=message.message_id,
                sender=message.from_,
                authorized_sender=operator,
                body=body,
                product_key=product_key,
                run_check=manual_check,
            )
            if status not in {"duplicate-message", "unauthorized-sender"}:
                processed.append({"message_id": message.message_id, "command": status})
        print(
            json.dumps(
                {
                    "status": "processed",
                    "inbox_id": gateway.inbox_id,
                    "processed_count": len(processed),
                    "messages": processed,
                },
                indent=2,
            )
        )
        return 0
    finally:
        store.close()


def run_history(args: argparse.Namespace) -> int:
    store = MonitorStore(Path(args.database))
    try:
        print(format_history(store.history(args.product_key, args.limit)))
        return 0
    finally:
        store.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Monitor one authorized product page and send threaded AgentMail alerts."
    )
    parser.set_defaults(handler=None)
    subparsers = parser.add_subparsers(dest="command")

    check = subparsers.add_parser("check", help="Record one confirmed observation")
    check.add_argument("--url")
    check.add_argument("--fixture")
    check.add_argument("--product-key")
    check.add_argument("--database", default=".local/price-monitor.sqlite3")
    check.add_argument("--no-email", action="store_true")
    check.set_defaults(handler=run_check)

    history = subparsers.add_parser("history", help="Show recent observations")
    history.add_argument("--product-key", default="demo-product")
    history.add_argument("--database", default=".local/price-monitor.sqlite3")
    history.add_argument("--limit", type=int, default=5)
    history.set_defaults(handler=run_history)

    inbox = subparsers.add_parser(
        "process-inbox", help="Process new commands from the authorized operator"
    )
    inbox.add_argument("--url")
    inbox.add_argument("--fixture")
    inbox.add_argument("--product-key")
    inbox.add_argument("--database", default=".local/price-monitor.sqlite3")
    inbox.add_argument("--limit", type=int, default=50)
    inbox.set_defaults(handler=run_inbox)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.handler is None:
        raise SystemExit("Choose a command: check, process-inbox, or history")
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
