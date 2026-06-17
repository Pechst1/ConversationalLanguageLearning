import { spawnSync } from 'node:child_process';

await import('./ensure-native-api-env.mjs');

const skipBuild = process.argv.includes('--skip-build');
const nativeEnv = {
  ...process.env,
  NATIVE_STATIC_EXPORT: process.env.NATIVE_STATIC_EXPORT || 'true',
  CAPACITOR_WEB_DIR: process.env.CAPACITOR_WEB_DIR || 'out',
};

if (!skipBuild) {
  console.log('Building static native web bundle...');
  const build = spawnSync('npm', ['run', 'build:native'], {
    stdio: 'inherit',
    env: nativeEnv,
  });

  if (build.status !== 0) {
    process.exit(build.status ?? 1);
  }
}

if (nativeEnv.CAPACITOR_SERVER_URL) {
  console.log(`Syncing Capacitor iOS shell with server.url=${nativeEnv.CAPACITOR_SERVER_URL}`);
} else {
  console.log(`Syncing Capacitor iOS shell from ${nativeEnv.CAPACITOR_WEB_DIR}/`);
}

const result = spawnSync('npx', ['cap', 'sync', 'ios'], {
  stdio: 'inherit',
  env: nativeEnv,
});

process.exit(result.status ?? 1);
