/* Test-only stand-in for next/link, so the reader can be server-rendered
   outside a Next app in `reader-render.test.js`. */
const React = require('react');

function LinkStub({ children, href, ...rest }) {
  return React.createElement('a', { href, ...rest }, children);
}

module.exports = LinkStub;
module.exports.default = LinkStub;
