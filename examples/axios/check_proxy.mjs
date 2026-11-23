import axios from 'axios';

import {
  axiosProxy,
  loadHttpsProxy,
  parseExitIp,
  redactedProxy,
  requestSettings,
} from '../node/proxy-config.mjs';

const proxy = loadHttpsProxy();
const settings = requestSettings();
const response = await axios.get(settings.ipCheckUrl, {
  proxy: axiosProxy(proxy),
  timeout: settings.requestTimeoutMs,
  maxContentLength: 1024 * 1024,
  responseType: 'text',
  transformResponse: [(body) => body],
  redact: ['auth', 'proxy', 'password'],
});

console.log(`Profile: ${proxy.profile}`);
console.log(`Proxy: ${redactedProxy(proxy)}`);
console.log(`Exit IP: ${parseExitIp(response.data)}`);
