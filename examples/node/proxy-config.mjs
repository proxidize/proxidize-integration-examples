import { isIP } from 'node:net';

const PROFILE_PREFIXES = {
  mobile: 'MOBILE_HTTPS_PROXY',
  residential: 'RESIDENTIAL_HTTPS_PROXY',
};

function required(name) {
  const value = process.env[name]?.trim();
  if (!value) throw new Error(`${name} is required`);
  return value;
}

function positiveNumber(name, fallback) {
  const value = Number(process.env[name] ?? fallback);
  if (!Number.isFinite(value) || value <= 0) {
    throw new Error(`${name} must be a number greater than zero`);
  }
  return value;
}

export function selectedProfile() {
  const value = (process.env.PROXY_PROFILE ?? 'mobile').trim().toLowerCase();
  if (!(value in PROFILE_PREFIXES)) {
    throw new Error('PROXY_PROFILE must be "mobile" or "residential"');
  }
  return value;
}

export function loadHttpsProxy(profile = selectedProfile()) {
  const prefix = PROFILE_PREFIXES[profile];
  if (!prefix) throw new Error(`Unsupported proxy profile: ${profile}`);

  const server = required(`${prefix}_SERVER`);
  let parsed;
  try {
    parsed = new URL(server);
  } catch {
    throw new Error(`${prefix}_SERVER must be an absolute proxy URL`);
  }
  if (!['http:', 'https:'].includes(parsed.protocol) || !parsed.hostname) {
    throw new Error(`${prefix}_SERVER must use http:// or https://`);
  }
  if (parsed.username || parsed.password) {
    throw new Error(
      `${prefix}_SERVER must not contain credentials; use the username and password variables`,
    );
  }

  return {
    profile,
    server: parsed.toString().replace(/\/$/, ''),
    username: required(`${prefix}_USERNAME`),
    password: required(`${prefix}_PASSWORD`),
  };
}

export function basicProxyToken(proxy) {
  return `Basic ${Buffer.from(`${proxy.username}:${proxy.password}`, 'utf8').toString('base64')}`;
}

export function proxyUrlWithCredentials(proxy) {
  const value = new URL(proxy.server);
  value.username = proxy.username;
  value.password = proxy.password;
  return value.toString();
}

export function playwrightProxy(proxy) {
  return {
    server: proxy.server,
    username: proxy.username,
    password: proxy.password,
  };
}

export function axiosProxy(proxy) {
  const value = new URL(proxy.server);
  return {
    protocol: value.protocol.slice(0, -1),
    host: value.hostname,
    port: Number(value.port || (value.protocol === 'https:' ? 443 : 80)),
    auth: {
      username: proxy.username,
      password: proxy.password,
    },
  };
}

export function redactedProxy(proxy) {
  const value = new URL(proxy.server);
  return `${value.protocol}//${value.host}`;
}

export function parseExitIp(payload) {
  const trimmed = payload.trim();
  let candidate = trimmed;
  try {
    const decoded = JSON.parse(trimmed);
    candidate = decoded?.ip;
  } catch {
    // Plain-text IP services are also supported.
  }
  if (typeof candidate !== 'string' || isIP(candidate.trim()) === 0) {
    throw new Error(`Unexpected IP-check response: ${trimmed.slice(0, 160)}`);
  }
  return candidate.trim();
}

export function requestSettings() {
  return {
    ipCheckUrl:
      process.env.IP_CHECK_URL ?? 'https://api.ipify.org?format=json',
    targetUrl: process.env.TARGET_URL ?? 'https://example.com',
    requestTimeoutMs:
      positiveNumber('REQUEST_TIMEOUT_SECONDS', 30) * 1000,
    navigationTimeoutMs: positiveNumber('NAVIGATION_TIMEOUT_MS', 30000),
  };
}
