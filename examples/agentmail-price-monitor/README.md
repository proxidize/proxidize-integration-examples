# AgentMail Price Monitor

This example checks one authorized product page through a Proxidize Residential Proxy, stores confirmed observations in SQLite, sends a single AgentMail alert when the price changes, and accepts a restricted set of reply commands.

Supported commands are `check now`, `show history`, `mute 24h`, and `help`. Incoming email is untrusted input; the example never turns arbitrary message text into a URL, shell command, purchase, or browser action.

## Set up

From the repository root:

```bash
uv sync --locked
cp examples/agentmail-price-monitor/.env.example .env.agentmail.local
```

Fill in the local file with an AgentMail API key, the authorized operator address, and your Proxidize Residential Proxy access point. An inbox-scoped key is the least-privilege option and discovers its own inbox through `auth.me()`. An organization- or pod-scoped key creates or reuses the inbox identified by `PRICE_MONITOR_INBOX_CLIENT_ID`; set `AGENTMAIL_INBOX_ID` to force an existing inbox. The repository ignores `.env.agentmail.local`.

## Run the deterministic fixture

The first observation establishes a baseline and does not send an alert:

```bash
uv run --env-file .env.agentmail.local \
  python examples/agentmail-price-monitor/monitor.py check \
  --fixture examples/agentmail-price-monitor/fixtures/product-before.html \
  --no-email
```

The second fixture records a price change:

```bash
uv run --env-file .env.agentmail.local \
  python examples/agentmail-price-monitor/monitor.py check \
  --fixture examples/agentmail-price-monitor/fixtures/product-after.html \
  --no-email
```

Remove `--no-email` to send a threaded alert to `PRICE_MONITOR_OPERATOR_EMAIL`.

Process new commands from that authorized operator with one bounded poll:

```bash
uv run --env-file .env.agentmail.local \
  python examples/agentmail-price-monitor/monitor.py process-inbox \
  --fixture examples/agentmail-price-monitor/fixtures/product-after.html
```

Run `process-inbox` from a scheduler for a simple worker. For lower latency, pass the same message IDs and extracted reply text into `process_command` from a signed AgentMail webhook or polling-webhook consumer.

## Check an authorized page through Proxidize

Set `PRICE_MONITOR_URL` to a page you are allowed to monitor, then run:

```bash
uv run --env-file .env.agentmail.local \
  python examples/agentmail-price-monitor/monitor.py check
```

The extractor accepts one unambiguous Product JSON-LD offer, product price meta tags, or an element containing `data-price`, `data-currency`, and optional `data-product-name` attributes. Adapt the extractor for a target-specific schema rather than weakening its validation.

## Inspect history

```bash
uv run python examples/agentmail-price-monitor/monitor.py history
```

Runtime data is written under `.local/`, which is not intended for version control. Use a managed database and a job queue when multiple workers can process the same product or mailbox.

## Security boundaries

- Keep AgentMail and proxy credentials in a private environment or secret store.
- Allow only known operators to send commands.
- Verify webhook signatures before processing production events.
- Use AgentMail idempotency keys and the local event ledger to suppress duplicate sends.
- Collect only data you are authorized to access and use destination-aware request limits.
- Do not use AgentMail for unsolicited outreach.

Read the complete tutorial at [Build an AI Price Monitoring Agent With Email Alerts](https://proxidize.com/blog/ai-price-monitoring-agent-email-alerts/).
