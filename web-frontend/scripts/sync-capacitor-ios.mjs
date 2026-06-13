import { spawnSync } from 'node:child_process';

const serverUrl = process.env.CAPACITOR_SERVER_URL || 'http://127.0.0.1:3000';

console.log(`Syncing Capacitor iOS shell with server.url=${serverUrl}`);

const result = spawnSync('npx', ['cap', 'sync', 'ios'], {
  stdio: 'inherit',
  env: {
    ...process.env,
    CAPACITOR_SERVER_URL: serverUrl,
  },
});

process.exit(result.status ?? 1);
