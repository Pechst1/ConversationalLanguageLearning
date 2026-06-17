import type { CapacitorConfig } from '@capacitor/cli';

const serverUrl = process.env.CAPACITOR_SERVER_URL;

const config: CapacitorConfig = {
  appId: 'com.pixellab.feuilleton',
  appName: 'Feuilleton',
  webDir: process.env.CAPACITOR_WEB_DIR || 'out',
};

if (serverUrl) {
  config.server = {
    url: serverUrl,
    cleartext: serverUrl.startsWith('http://'),
  };
}

export default config;
