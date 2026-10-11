// WP-72 — check a built native bundle before it is archived.
//
//   node scripts/verify-native-bundle.mjs [--release] [dir]
//
// `dir` defaults to ios/App/App/public (what Xcode copies into the app).
// Without --release: the bundle has its build manifest, no dev/QA pages, and the
// API URL it was built with is really inlined. With --release, additionally: the
// API is HTTPS and neither local nor a placeholder, native push is on, and the
// APNs environment is production. Exit 1 on any problem.
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { verifyNativeBundle } from './native-export-policy.mjs';

const webRoot = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const args = process.argv.slice(2);
const release = args.includes('--release');
const target = args.find((arg) => !arg.startsWith('--')) || path.join('ios', 'App', 'App', 'public');
const dir = path.resolve(webRoot, target);

const problems = verifyNativeBundle(dir, { release });
if (problems.length) {
  console.error(`Native bundle check failed for ${path.relative(webRoot, dir) || '.'}:`);
  for (const problem of problems) console.error(`  - ${problem}`);
  process.exit(1);
}
console.log(`Native bundle OK${release ? ' for release' : ''}: ${path.relative(webRoot, dir)}`);

// Not a failure (internal TestFlight needs no policy), but App Review does.
const legal = JSON.parse(readFileSync(path.join(webRoot, 'lib', 'legal-content.json'), 'utf8'));
if (release && !String(legal.contact_email || '').includes('@')) {
  console.warn(
    `Warning: the privacy policy's contact is still "${legal.contact_email}". ` +
      'Fill app/data/legal/legal_content.json before App Store submission.',
  );
}
