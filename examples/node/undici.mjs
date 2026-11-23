import { ProxyAgent, request } from 'undici';

import {
  basicProxyToken,
  loadHttpsProxy,
  parseExitIp,
  redactedProxy,
  requestSettings,
} from './proxy-config.mjs';

async function main() {
  const proxy = loadHttpsProxy();
  const settings = requestSettings();
  const dispatcher = new ProxyAgent({
    uri: proxy.server,
    token: basicProxyToken(proxy),
    requestTls: { rejectUnauthorized: true },
    proxyTls: { rejectUnauthorized: true },
  });

  try {
    const response = await request(settings.ipCheckUrl, {
      dispatcher,
      headersTimeout: settings.requestTimeoutMs,
      bodyTimeout: settings.requestTimeoutMs,
    });
    const payload = await response.body.text();
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw new Error(`IP check returned HTTP ${response.statusCode}`);
    }

    console.log(
      JSON.stringify(
        {
          client: 'undici',
          profile: proxy.profile,
          proxy: redactedProxy(proxy),
          exit_ip: parseExitIp(payload),
        },
        null,
        2,
      ),
    );
  } finally {
    await dispatcher.close();
  }
}

main().catch((error) => {
  console.error(
    `Undici proxy check failed: ${error instanceof Error ? error.message : error}`,
  );
  process.exitCode = 1;
});
