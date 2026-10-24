// Le Quartier · one self-contained HTML file of the 3D scene (three.js, React, the cast's
// drawings and the app's two typefaces inlined), to open on a phone without the app.
//   node scripts/quartier/build-standalone.mjs [out.html] [--fragment]
// --fragment leaves out the document's skeleton (doctype, head, body), for a host that adds its own.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { build } from 'esbuild';

const here = path.dirname(fileURLToPath(import.meta.url));
const web = path.resolve(here, '..', '..');
const args = process.argv.slice(2);
const fragment = args.includes('--fragment');
const out = path.resolve(args.find((a) => !a.startsWith('--')) ?? path.join(web, 'out-quartier', 'le-quartier.html'));

const result = await build({
  entryPoints: [path.join(here, 'standalone.tsx')],
  bundle: true,
  write: false,
  format: 'iife',
  platform: 'browser',
  target: ['safari15', 'chrome100'],
  jsx: 'automatic',
  minify: true,
  legalComments: 'none',
  tsconfig: path.join(web, 'tsconfig.json'),
  define: { 'process.env.NODE_ENV': '"production"' },
  logLevel: 'warning',
});
const js = result.outputFiles[0].text.replace(/<\/script/gi, '<\\/script');

const font = (family, style, weight, file) => {
  const b64 = fs.readFileSync(path.join(web, 'public', 'fonts', file)).toString('base64');
  return `@font-face{font-family:'${family}';font-style:${style};font-weight:${weight};font-display:block;src:url(data:font/woff2;base64,${b64}) format('woff2');}`;
};
const fonts = [
  font('AtelierSerif', 'italic', '400 800', 'eb-garamond-italic-latin.woff2'),
  font('AtelierSans', 'normal', '400 700', 'instrument-sans-latin.woff2'),
].join('');

const style = `<style>${fonts}html,body{margin:0;height:100%;background:#0d1430;overscroll-behavior:none}#root{height:100%}</style>`;
const html = fragment
  ? `<title>Le Quartier</title>
${style}
<div id="root"></div>
<script>${js}</script>
`
  : `<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#0d1430">
<title>Le Quartier</title>
${style}
</head>
<body>
<div id="root"></div>
<script>${js}</script>
</body>
</html>
`;
fs.mkdirSync(path.dirname(out), { recursive: true });
fs.writeFileSync(out, html);
console.log(`wrote ${path.relative(process.cwd(), out)} (${(html.length / 1024 / 1024).toFixed(2)} MB)`);
