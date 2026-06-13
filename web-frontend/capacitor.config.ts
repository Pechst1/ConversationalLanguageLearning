import type { CapacitorConfig } from '@capacitor/cli';

const serverUrl = process.env.CAPACITOR_SERVER_URL || 'http://127.0.0.1:3000';

const config: CapacitorConfig = {
  appId: 'com.pixellab.feuilleton',
  appName: 'Feuilleton',
  webDir: 'public',
  server: {
    url: serverUrl,
    cleartext: true,
  },
};

export default config;
