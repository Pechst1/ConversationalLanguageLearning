import { spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import openapiTS, { astToString } from 'openapi-typescript';

const root = fileURLToPath(new URL('../../', import.meta.url));
const output = fileURLToPath(new URL('../types/generated/api.ts', import.meta.url));

export async function renderTypes(schema) {
  return '/** Generated from app.main.create_app().openapi(). Run npm run types:generate. */\n'
    + astToString(await openapiTS(schema, { alphabetize: true, defaultNonNullable: false }));
}

export function exportSchema() {
  const localPython = `${root}venv/bin/python`;
  const python = process.env.OPENAPI_PYTHON || (existsSync(localPython) ? localPython : 'python');
  const result = spawnSync(python, ['scripts/export_openapi.py'], {
    cwd: root, encoding: 'utf8', maxBuffer: 20 * 1024 * 1024,
  });
  if (result.error || result.status !== 0) {
    throw new Error(result.error?.message || result.stderr || 'OpenAPI export failed');
  }
  return JSON.parse(result.stdout);
}

export function checkFreshness(expected, actual) {
  if (expected !== actual) {
    throw new Error('Generated API types are stale. Run npm run types:generate and commit types/generated/api.ts.');
  }
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const generated = await renderTypes(exportSchema());
  if (process.argv.includes('--check')) {
    checkFreshness(generated, existsSync(output) ? readFileSync(output, 'utf8') : '');
    console.log('Generated API types are current.');
  } else {
    mkdirSync(fileURLToPath(new URL('../types/generated/', import.meta.url)), { recursive: true });
    writeFileSync(output, generated);
    console.log('Generated types/generated/api.ts');
  }
}
