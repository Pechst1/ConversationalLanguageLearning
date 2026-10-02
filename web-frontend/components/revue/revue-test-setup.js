// Shared setup for the components/revue node tests: sucrase for .ts/.tsx, the
// `@/` alias, a stub for the axios client (the tests never touch the network).
const path = require('node:path');
const Module = require('node:module');

const WEB_ROOT = path.resolve(__dirname, '..', '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/tsx'));

const originalResolve = Module._resolveFilename;
if (!Module._revueAlias) {
  Module._revueAlias = true;
  Module._resolveFilename = function resolve(request, ...rest) {
    if (request.startsWith('@/')) return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
    return originalResolve.call(this, request, ...rest);
  };
}

const apiPath = Module._resolveFilename('@/services/api', module, false);
require.cache[apiPath] = {
  id: apiPath,
  filename: apiPath,
  loaded: true,
  exports: { __esModule: true, default: {}, apiService: {} },
};

const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
global.React = React;

const decode = (html) =>
  html.replace(/&#x27;|&#39;/g, "'").replace(/&quot;/g, '"').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&nbsp;/g, ' ');
const visibleText = (html) =>
  decode(html.replace(/<span class="av2-sr">[\s\S]*?<\/span>/g, ' ').replace(/<[^>]+>/g, ' ')).replace(/\s+/g, ' ').trim();

const fixture = (name) => require(path.join(__dirname, 'fixtures', `${name}.json`));

module.exports = { WEB_ROOT, React, h: React.createElement, render: (el) => renderToStaticMarkup(el), visibleText, decode, fixture };
