import puppeteer from 'puppeteer';

import {
  loadHttpsProxy,
  parseExitIp,
  redactedProxy,
  requestSettings,
} from '../node/proxy-config.mjs';

async function main() {
  const proxy = loadHttpsProxy();
  const settings = requestSettings();
  const args = [`--proxy-server=${proxy.server}`];
  if (process.env.PUPPETEER_NO_SANDBOX === 'true') {
    args.push('--no-sandbox', '--disable-setuid-sandbox');
  }
  const browser = await puppeteer.launch({
    headless: true,
    args,
  });

  try {
    const page = await browser.newPage();
    await page.authenticate({
      username: proxy.username,
      password: proxy.password,
    });
    page.setDefaultNavigationTimeout(settings.navigationTimeoutMs);
    const response = await page.goto(settings.ipCheckUrl, {
      waitUntil: 'domcontentloaded',
    });
    if (!response?.ok()) {
      throw new Error(`IP check returned HTTP ${response?.status() ?? 'none'}`);
    }

    console.log(
      JSON.stringify(
        {
          client: 'puppeteer',
          profile: proxy.profile,
          proxy: redactedProxy(proxy),
          exit_ip: parseExitIp(await page.$eval('body', (node) => node.innerText)),
        },
        null,
        2,
      ),
    );
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(
    `Puppeteer proxy check failed: ${error instanceof Error ? error.message : error}`,
  );
  process.exitCode = 1;
});
