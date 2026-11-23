# Sanitized live-test record

Test date: November 23, 2026

Target market: United States

## Verified network paths

| Path | Authentication | Result | Sanitized observation |
| --- | --- | --- | --- |
| Mobile HTTPS | Username/password | Passed | US exit on a real mobile carrier network |
| Residential HTTPS | Username/password | Passed | US residential/network exit |
| Mobile SOCKS5 TCP | Username/password | Passed | US exit on a real mobile carrier network |
| Mobile SOCKS5 UDP | Username/password plus UDP ASSOCIATE | Passed | QUIC handshake completed through the negotiated UDP relay on port 443 |

The first protocol check returned the same sticky US mobile exit through the mobile HTTPS and SOCKS5 paths. The residential profile returned a separate US exit. Full IP addresses are intentionally omitted.

## HTTPS client matrix

Every client below completed a live IP-check request through both the mobile and residential HTTPS profiles:

| Client | Mobile HTTPS | Residential HTTPS |
| --- | --- | --- |
| cURL 7.88 | Passed | Passed |
| Undici 8.13.1 on Node.js 24 | Passed | Passed |
| Requests 2.34.2 | Passed | Passed |
| HTTPX 0.28.1 | Passed | Passed |
| Playwright 1.65.1 on Node.js | Passed | Passed |
| Playwright 1.65.2 on Python | Passed | Passed |
| Puppeteer 25.18.1 | Passed | Passed |
| Scrapy 2.20.0 | Passed | Passed |

Puppeteer ran with Chromium's sandbox disabled only because this validation environment runs as root inside an isolated container. The public example keeps sandboxing enabled by default. Selenium is syntax- and configuration-tested but is not included in the live username/password matrix because its standard proxy capability requires an IP-allowlisted endpoint for portable authenticated-proxy use.

## Extended crawler checks

| Client | Version | Validation |
| --- | --- | --- |
| Crawl4AI | 0.9.5 | Package import, per-run `ProxyConfig`, browser launch, and direct IP-check smoke test passed |
| scrapy-playwright | 0.0.48 | Package import, context-level proxy configuration, and Python compilation passed |

These two additions were validated without reusing the exposed test credentials, so they are not added to the earlier live username/password matrix.

## Second-batch integration checks

The eight integrations added after the original live run were validated without live proxy credentials.

| Client | Version or runtime | Local validation |
| --- | --- | --- |
| Axios | 1.21.1 on Node.js 24 | Unit tests and authenticated CONNECT smoke test passed |
| aiohttp | 3.14.5 on Python 3.11 | Compilation and authenticated CONNECT smoke test passed |
| PycURL | 7.49.0 on Python 3.11 | Compilation and authenticated CONNECT smoke test passed |
| PHP cURL | PHP 8.2 with libcurl 7.88 | Syntax and authenticated CONNECT smoke test passed |
| Go net/http | Go standard library | Compilation and authenticated CONNECT smoke test passed |
| Java HttpClient | Java 17 standard library | Compilation and authenticated CONNECT smoke test passed |
| C# HttpClient | .NET 8 standard library | Project build and authenticated CONNECT smoke test passed |
| Ruby Net::HTTP | Ruby standard library | Syntax and authenticated CONNECT smoke test passed |

Java, C#, and Ruby require an HTTP proxy endpoint for these standard-library configurations. The Go, Axios, aiohttp, PycURL, and PHP cURL examples accept the HTTP or HTTPS scheme supported by their clients.

## UDP acceptance criteria

The UDP test was considered successful only after all of these stages completed:

1. TCP connection to the SOCKS5 control endpoint.
2. SOCKS5 username/password authentication.
3. Successful `UDP ASSOCIATE` response with a relay address and port.
4. QUIC Initial datagrams sent through the SOCKS5 UDP relay.
5. Response datagrams returned through that relay.
6. TLS-authenticated QUIC handshake completion with the configured UDP/443 target.

The validation run received nine response datagrams and completed the QUIC handshake in approximately 495 ms. That number is a single functional check, not a latency benchmark or service-level claim.

## Safety and interpretation

- An IP-check request validates routing, authentication, and visible egress. It does not establish success against every destination.
- One successful UDP/443 handshake validates the configured path, not all UDP applications or destinations.
- Sticky-session checks should be repeated within the intended session lifetime. Rotation checks should use intentionally different session identifiers.
- Concurrency should increase gradually and remain consistent with destination rules and responsible request pacing.
- Tests must keep TLS verification enabled and must not log proxy credentials.
