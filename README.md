# Proxidize Proxy Integration Examples

Runnable, credential-safe examples for connecting Proxidize Mobile and Residential Proxies to popular HTTP clients, browser automation tools, and crawling frameworks.

**[Browse all Proxidize integrations](https://proxidize.com/integrations/)** · **[Use the official Proxidize MCP server](https://github.com/proxidize/proxidize-mcp)** · **[Review the sanitized live-test record](docs/LIVE_TESTS.md)**

These examples use standard HTTP, HTTPS, and SOCKS5 proxy protocols. You do not need a Proxidize SDK, and no real credentials, complete exit IPs, cookies, browser state, or traces are stored in this repository.

## Integration directory

Choose a runnable example below, then open its Proxidize guide for setup details, rotation guidance, and troubleshooting.

| Integration | Runtime | Recommended access point | Code | Proxidize guide |
| --- | --- | --- | --- | --- |
| cURL | Shell | Mobile or residential HTTPS | [`check.sh`](examples/curl/check.sh) | [cURL integration](https://proxidize.com/integrations/curl/) |
| Undici | Node.js 24+ | Mobile or residential HTTPS | [`undici.mjs`](examples/node/undici.mjs) | [Node.js and Undici integration](https://proxidize.com/integrations/nodejs-undici/) |
| Axios | Node.js 24+ | Mobile or residential HTTPS | [`check_proxy.mjs`](examples/axios/check_proxy.mjs) | [Axios integration](https://proxidize.com/integrations/axios/) |
| Requests | Python 3.11.5+ | Mobile or residential HTTPS | [`requests_example.py`](examples/python/requests_example.py) | [Requests and HTTPX integration](https://proxidize.com/integrations/python-requests-httpx/) |
| HTTPX | Python 3.11.5+ | Mobile or residential HTTPS | [`httpx_example.py`](examples/python/httpx_example.py) | [Requests and HTTPX integration](https://proxidize.com/integrations/python-requests-httpx/) |
| aiohttp | Python 3.11.5+ | Mobile or residential HTTP(S) | [`check_proxy.py`](examples/aiohttp/check_proxy.py) | [aiohttp integration](https://proxidize.com/integrations/python-aiohttp/) |
| PycURL | Python 3.11.5+ | Mobile or residential HTTPS | [`check_proxy.py`](examples/pycurl/check_proxy.py) | [PycURL integration](https://proxidize.com/integrations/pycurl/) |
| Playwright | Node.js 24+ | Mobile or residential HTTPS | [`node.mjs`](examples/playwright/node.mjs) | [Playwright integration](https://proxidize.com/integrations/playwright/) |
| Playwright | Python 3.11.5+ | Mobile or residential HTTPS | [`python_example.py`](examples/playwright/python_example.py) | [Playwright integration](https://proxidize.com/integrations/playwright/) |
| Puppeteer | Node.js 24+ | Mobile or residential HTTPS | [`check_proxy.mjs`](examples/puppeteer/check_proxy.mjs) | [Puppeteer integration](https://proxidize.com/integrations/puppeteer/) |
| Scrapy | Python 3.11.5+ | Mobile or residential HTTPS | [`check_proxy.py`](examples/scrapy/check_proxy.py) | [Scrapy integration](https://proxidize.com/integrations/scrapy/) |
| Scrapy Playwright | Python 3.11.5+ | Mobile or residential HTTPS | [`check_proxy.py`](examples/scrapy-playwright/check_proxy.py) | [Scrapy Playwright integration](https://proxidize.com/integrations/scrapy-playwright/) |
| Crawl4AI | Python 3.11.5+ | Mobile or residential HTTPS | [`check_proxy.py`](examples/crawl4ai/check_proxy.py) | [Crawl4AI integration](https://proxidize.com/integrations/crawl4ai/) |
| Selenium | Python 3.11.5+ | IP-allowlisted HTTP(S) | [`python_ip_allowlist.py`](examples/selenium/python_ip_allowlist.py) | [Selenium integration](https://proxidize.com/integrations/selenium/) |
| Mobile UDP over SOCKS5 | Python 3.11.5+ | Mobile SOCKS5 with UDP enabled | [`quic_check.py`](examples/mobile-udp/quic_check.py) | [Mobile UDP over SOCKS5](https://proxidize.com/integrations/mobile-udp-socks5/) |
| PHP cURL | PHP 8+ | Mobile or residential HTTPS | [`check_proxy.php`](examples/php-curl/check_proxy.php) | [PHP cURL integration](https://proxidize.com/integrations/php-curl/) |
| Go `net/http` | Go 1.19+ | Mobile or residential HTTP(S) | [`check_proxy.go`](examples/go-net-http/check_proxy.go) | [Go net/http integration](https://proxidize.com/integrations/go-net-http/) |
| Java `HttpClient` | Java 17+ | HTTP proxy with HTTPS CONNECT | [`ProxyCheck.java`](examples/java-httpclient/ProxyCheck.java) | [Java HttpClient integration](https://proxidize.com/integrations/java-httpclient/) |
| C# `HttpClient` | .NET 8+ | HTTP proxy with HTTPS CONNECT | [`ProxyCheck.cs`](examples/csharp-httpclient/ProxyCheck.cs) | [C# HttpClient integration](https://proxidize.com/integrations/csharp-httpclient/) |
| Ruby `Net::HTTP` | Ruby 3.1+ | HTTP proxy with HTTPS CONNECT | [`check_proxy.rb`](examples/ruby-net-http/check_proxy.rb) | [Ruby Net::HTTP integration](https://proxidize.com/integrations/ruby-net-http/) |

## Manage Proxidize with MCP

The official [Proxidize MCP server](https://github.com/proxidize/proxidize-mcp) lets MCP-compatible clients manage supported Proxidize account and proxy operations, including IP rotation, locations, access points, usage, and analytics. It is the management layer; requests to target websites still travel through the HTTP, HTTPS, or SOCKS5 integrations above.

It requires Node.js 18 or later, an active Proxidize subscription, and a Proxidize API token. For Claude Code, add it as a local MCP server:

```bash
claude mcp add proxidize \
  -e PROXIDIZE_API_TOKEN=YOUR_API_TOKEN \
  -- npx -y @proxidize/mcp
```

Run that command locally and replace `YOUR_API_TOKEN` there. Never put the real token in this README, source code, `.env.example`, a committed `.mcp.json`, screenshots, or logs. For a project configuration that supports environment-variable expansion, keep only the reference in version control:

```json
{
  "mcpServers": {
    "proxidize": {
      "command": "npx",
      "args": ["-y", "@proxidize/mcp"],
      "env": {
        "PROXIDIZE_API_TOKEN": "${PROXIDIZE_API_TOKEN}"
      }
    }
  }
}
```

Set `PROXIDIZE_API_TOKEN` in your local environment or MCP client's private secret store before starting the client. Review state-changing tool calls before approving them. See the official MCP repository for supported clients, tools, and configuration options.

## Quick start

### 1. Clone the repository

```bash
git clone https://github.com/proxidize/proxidize-integration-examples.git
cd proxidize-integration-examples
```

### 2. Configure credentials

Copy the safe template into a local file that Git ignores:

```bash
cp .env.example .env.local
```

Fill in the host, port, username, and password shown in the Proxidize dashboard. Keep the endpoint and credentials in separate variables; do not embed credentials in `PROXY_SERVER` values.

Select the profile used by the HTTP(S) examples:

```dotenv
PROXY_PROFILE=mobile
```

Supported values are `mobile` and `residential`. The UDP checker always uses the dedicated `MOBILE_SOCKS5_PROXY_*` variables.

Never commit `.env.local`. The repository ignores common secret, trace, browser-state, and result files.

### 3. Create the Python virtual environment with uv

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then create the project environment and install the locked dependencies:

```bash
uv venv --python 3.11.5
uv sync --locked --all-extras
uv run playwright install chromium
```

`uv` stores the environment in `.venv` and uses `uv.lock` for reproducible installs. Activating the environment is optional because `uv run` automatically uses it. If you prefer an activated shell:

```bash
source .venv/bin/activate
```

Run this once before using Crawl4AI:

```bash
uv run crawl4ai-setup
```

There are no `requirements.txt` files. Add or update Python packages through `pyproject.toml` and refresh the lockfile with `uv lock`.

### 4. Install Node.js dependencies

Only Node.js, Playwright, Axios, Undici, or Puppeteer examples need this step:

```bash
npm ci
npx playwright install chromium
```

Puppeteer installs its compatible browser during `npm ci` unless browser downloads are disabled. Selenium requires a compatible Chrome or Chromium installation.

## Run an example

### Node.js

The npm scripts load `.env.local` without printing it:

```bash
npm run live:node
npm run live:axios
npm run live:playwright
npm run live:puppeteer
```

### Python

`uv run --env-file` loads the same local credentials into one command:

```bash
uv run --env-file .env.local python examples/python/requests_example.py
uv run --env-file .env.local python examples/python/httpx_example.py
uv run --env-file .env.local python examples/aiohttp/check_proxy.py
uv run --env-file .env.local python examples/pycurl/check_proxy.py
uv run --env-file .env.local python examples/playwright/python_example.py
uv run --env-file .env.local python examples/scrapy/check_proxy.py
uv run --env-file .env.local python examples/scrapy-playwright/check_proxy.py
uv run --env-file .env.local python examples/crawl4ai/check_proxy.py
uv run --env-file .env.local python examples/selenium/python_ip_allowlist.py
```

### cURL, PHP, Go, Java, C#, and Ruby

Load `.env.local` into the current shell, then run the client you need:

```bash
set -a
. ./.env.local
set +a

bash examples/curl/check.sh
php examples/php-curl/check_proxy.php
go run examples/go-net-http/check_proxy.go
java -Djdk.http.auth.tunneling.disabledSchemes= examples/java-httpclient/ProxyCheck.java
dotnet run --project examples/csharp-httpclient
ruby examples/ruby-net-http/check_proxy.rb
```

The Java flag permits Basic proxy authentication for HTTPS CONNECT in that Java process. Keep the change scoped to the command rather than setting it globally.

Each example requests only the configured IP-check URL, validates the response, and prints the selected profile, a redacted endpoint, and the visible exit IP. Set `IP_CHECK_URL` to an approved endpoint if your organization does not use the default.

## Verify mobile UDP over SOCKS5

In the Proxidize Mobile Proxy dashboard:

1. Enable UDP.
2. Select `SOCKS5 Proxy`.
3. Generate a United States access point.
4. Put its host, port, username, and password in the `MOBILE_SOCKS5_PROXY_*` variables.

Run the QUIC checker through the same uv environment:

```bash
uv run --env-file .env.local python examples/mobile-udp/quic_check.py
```

The checker performs username/password authentication, requests SOCKS5 `UDP ASSOCIATE`, and completes a QUIC handshake through the negotiated relay. It defaults to `cloudflare.com:443`; set `UDP_TARGET_HOST` to a permitted endpoint you control when required. The checker accepts only ports 80 and 443 to match the tested mobile UDP path.

An HTTPS request through a SOCKS5 endpoint validates only the TCP path. A successful QUIC handshake confirms that response datagrams traveled through the UDP relay.

## Choose the correct endpoint

| Client type | Endpoint guidance |
| --- | --- |
| Axios, aiohttp, cURL, Go, HTTPX, PycURL, Requests, and Scrapy | Use the HTTP or HTTPS access point supported by the client. Keep TLS verification enabled for the destination. |
| Playwright and Puppeteer | Use an authenticated HTTP(S) access point. Keep one sticky session aligned with one browser context or worker. |
| Selenium | Use an IP-allowlisted endpoint. The standard browser proxy capability does not provide portable username/password proxy authentication. |
| Java `HttpClient`, C# `HttpClient`, and Ruby `Net::HTTP` | Use an `http://` proxy endpoint. HTTPS destinations remain encrypted through a CONNECT tunnel. |
| Mobile UDP checker | Use a mobile SOCKS5 endpoint with UDP enabled. Do not use the residential HTTPS profile for this test. |

Do not put credentials inside browser profiles, source files, proxy URLs committed to Git, screenshots, or logs.

## Tests

The default test suite does not require live proxy credentials:

```bash
npm test
npm run check
uv run python -m unittest discover -s tests -p 'test_*.py'
uv run python -m compileall -q examples tests
uv lock --check
```

See [`docs/LIVE_TESTS.md`](docs/LIVE_TESTS.md) for the sanitized mobile, residential, browser, crawler, UDP, and second-batch validation matrix. A successful IP-check request validates routing and authentication; it does not promise access to every destination or measure proxy-network quality.

## Repository layout

```text
.
├── examples/          Runnable examples grouped by integration
├── tests/             Credential-free configuration and protocol tests
├── docs/              Sanitized validation notes
├── .env.example       Safe credential-variable template
├── pyproject.toml     Python dependencies managed by uv
├── uv.lock            Reproducible Python dependency lockfile
├── package.json       Node.js scripts and dependencies
├── LICENSE            MIT license
└── README.md          Setup, integration links, and run commands
```

## Responsible use

Use these examples only for lawful, authorized web access, testing, monitoring, automation, and public-data collection. Respect applicable laws, third-party terms, destination-aware rate limits, and the Proxidize Acceptable Use Policy. A working proxy connection does not authorize access to a target.

## License

Released under the [MIT License](LICENSE). Copyright (c) 2026 Proxidize.
