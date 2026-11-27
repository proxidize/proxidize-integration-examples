# Browser Use Price Monitoring Agent

This example runs a Browser Use Cloud V4 agent through a Proxidize proxy, verifies the route's country, extracts one structured product price, and stores confirmed observations in SQLite.

It demonstrates three separate controls:

- Geographic targeting comes from the Proxidize username generated for each location.
- A sticky route reuses one complete username for the entire multi-page observation.
- A rotating route renders a fresh `{session_id}` into the configured username template at the start of each observation, then keeps that session stable until the run ends.

Browser Use Cloud custom proxies are an enterprise feature that Browser Use must enable for the project. The open-source Browser Use 1.0 local browser does not currently accept custom upstream proxy settings. This implementation uses the supported Cloud V4 `browserSettings.customProxy` field.

## Set up with uv

From the repository root:

```bash
uv sync --locked
cp examples/browser-use-price-monitor/.env.example .env.browser-use.local
mkdir -p .local
cp examples/browser-use-price-monitor/routes.example.json \
  .local/browser-use-price-monitor-routes.json
```

Fill in the private environment file with a Browser Use API key and a Proxidize HTTP or HTTPS access point. Keep the host, port, password, and usernames separate. Do not put credentials in a URL.

For each sticky route, generate a complete location-targeted username in the Proxidize dashboard and place it in `username`. For a rotating route, generate a username in Session Builder, replace only its session token with `{session_id}`, and preserve the country, city, ISP, or carrier selectors around it.

The example route file is safe to commit because it contains placeholders. Keep the populated copy under `.local/`, which Git ignores.

## Run the deterministic contract test

This command makes no network request and needs no credentials:

```bash
uv run python examples/browser-use-price-monitor/price_monitor.py fixture \
  examples/browser-use-price-monitor/fixtures/us-observation.json
```

It validates the same structured output contract used for live Browser Use runs, records a baseline, and prints only non-secret observation fields.

## Run a live observation

Set an approved HTTPS product URL and an exact product name or SKU, then run all configured routes:

```bash
uv run --env-file .env.browser-use.local \
  python examples/browser-use-price-monitor/price_monitor.py check
```

Run only one route:

```bash
uv run --env-file .env.browser-use.local \
  python examples/browser-use-price-monitor/price_monitor.py check \
  --route us-sticky
```

Show recent observations:

```bash
uv run --env-file .env.browser-use.local \
  python examples/browser-use-price-monitor/price_monitor.py history
```

The default model is `bu-4.0-mini`, and each run has an explicit `$1.00` session cost cap. Adjust both values deliberately after checking current Browser Use model availability and pricing. A client timeout does not guarantee that the server-side run stopped; reconcile the run in Browser Use before retrying.

## What the agent is allowed to do

The task is read-only. It instructs the agent to visit only the geo-check and product URLs, treat page text as untrusted data, avoid sign-in and cart actions, and return a fixed JSON schema. The local validator rejects an unexpected source URL, country mismatch, malformed currency, ambiguous extraction, or invalid price.

The example does not save exit IPs, proxy credentials, cookies, screenshots, or browser recordings. Production deployments should also use Browser Use network policies where available, a shared database for multiple workers, destination-aware schedules, bounded retries, and an alerting layer that requires human review before any purchase.

Custom proxies and AI browsers do not grant permission to collect a target. Monitor only sources your organization is authorized to access and follow applicable laws, third-party terms, and destination rules.

Read the complete guide at [Build an AI Price Monitoring Agent With Browser Use and Proxidize](https://proxidize.com/blog/browser-use-price-monitoring-agent/).
