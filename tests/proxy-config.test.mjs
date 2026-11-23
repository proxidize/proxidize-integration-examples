import assert from 'node:assert/strict';
import test, { afterEach } from 'node:test';

import {
  axiosProxy,
  loadHttpsProxy,
  parseExitIp,
  playwrightProxy,
  proxyUrlWithCredentials,
  redactedProxy,
  selectedProfile,
} from '../examples/node/proxy-config.mjs';

const originalEnvironment = { ...process.env };

afterEach(() => {
  for (const key of Object.keys(process.env)) {
    if (!(key in originalEnvironment)) delete process.env[key];
  }
  Object.assign(process.env, originalEnvironment);
});

function setMobileEnvironment() {
  process.env.PROXY_PROFILE = 'mobile';
  process.env.MOBILE_HTTPS_PROXY_SERVER = 'https://proxy.example:20000';
  process.env.MOBILE_HTTPS_PROXY_USERNAME = 'user@example';
  process.env.MOBILE_HTTPS_PROXY_PASSWORD = 'p@ss:word';
}

test('loads a mobile HTTPS profile and keeps credentials separate', () => {
  setMobileEnvironment();
  const proxy = loadHttpsProxy();
  assert.equal(selectedProfile(), 'mobile');
  assert.equal(proxy.server, 'https://proxy.example:20000');
  assert.deepEqual(playwrightProxy(proxy), {
    server: 'https://proxy.example:20000',
    username: 'user@example',
    password: 'p@ss:word',
  });
});

test('builds an Axios proxy object without embedding credentials in a URL', () => {
  setMobileEnvironment();
  assert.deepEqual(axiosProxy(loadHttpsProxy()), {
    protocol: 'https',
    host: 'proxy.example',
    port: 20000,
    auth: {
      username: 'user@example',
      password: 'p@ss:word',
    },
  });
});

test('encodes credentials only in clients that require a URL', () => {
  setMobileEnvironment();
  const proxy = loadHttpsProxy();
  const value = proxyUrlWithCredentials(proxy);
  assert.match(value, /^https:\/\/user%40example:p%40ss%3Aword@proxy\.example:20000\/$/);
  assert.equal(redactedProxy(proxy), 'https://proxy.example:20000');
  assert.equal(redactedProxy(proxy).includes(proxy.password), false);
});

test('parses JSON and plain-text IP-check responses', () => {
  assert.equal(parseExitIp('{"ip":"203.0.113.8"}'), '203.0.113.8');
  assert.equal(parseExitIp('2001:db8::8\n'), '2001:db8::8');
  assert.throws(() => parseExitIp('<html>not an IP</html>'));
});

test('rejects credentials embedded in the server URL', () => {
  setMobileEnvironment();
  process.env.MOBILE_HTTPS_PROXY_SERVER =
    'https://embedded:secret@proxy.example:20000';
  assert.throws(() => loadHttpsProxy(), /must not contain credentials/);
});
