import { chromium } from 'playwright';

import {
  loadHttpsProxy,
  parseExitIp,
  playwrightProxy,
  redactedProxy,
  requestSettings,
} from '../node/proxy-config.mjs';

async function main() {
  const proxy = loadHttpsProxy();
  const settings = requestSettings();
  const browser = await chromium.launch({ headless: true });

  try {
    const context = await browser.newContext({
      proxy: playwrightProxy(proxy),
    });
    try {
      context.setDefaultNavigationTimeout(settings.navigationTimeoutMs);
      const page = await context.newPage();
      const response = await page.goto(settings.ipCheckUrl, {
        waitUntil: 'domcontentloaded',
      });
      if (!response?.ok()) {
        throw new Error(`IP check returned HTTP ${response?.status() ?? 'none'}`);
      }

      console.log(
        JSON.stringify(
          {
            client: 'playwright-node',
            profile: proxy.profile,
            proxy: redactedProxy(proxy),
            exit_ip: parseExitIp(await page.locator('body').innerText()),
          },
          null,
          2,
        ),
      );
    } finally {
      await context.close();
    }
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(
    `Playwright proxy check failed: ${error instanceof Error ? error.message : error}`,
  );
  process.exitCode = 1;
});
