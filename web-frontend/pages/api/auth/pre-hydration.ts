import type { NextApiRequest, NextApiResponse } from 'next';

/**
 * Where an auth form goes when the page has not hydrated yet.
 *
 * `pages/auth/*` render real `<form>` elements whose submit handlers only exist
 * once React has hydrated. A submit before that — a fast typist, a password
 * manager, a scripted submit, a browser restoring a session — used to fall back
 * to the browser's default: a GET to the current URL with `email` and
 * `password` in the query string. Credentials then sit in the address bar,
 * `history`, the `Referer` header of every later request and any access log in
 * front of the app.
 *
 * The forms therefore declare `method="post" action="/api/auth/pre-hydration"`,
 * which makes the pre-hydration fallback a POST to this route. It reads
 * nothing, logs nothing and forwards nothing: `bodyParser` is off, so the
 * credentials are never materialised, and the response never echoes the
 * submitted values. Once React has hydrated, `onSubmit` calls
 * `event.preventDefault()` and this route is never reached — NextAuth's normal
 * client flow is unchanged.
 */
export const config = {
  api: {
    bodyParser: false,
  },
};

const NOTICE = `<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sign-in needs JavaScript</title></head>
<body style="font-family: system-ui, sans-serif; margin: 3rem auto; max-width: 34rem; line-height: 1.5">
<h1 style="font-size: 1.25rem">Sign-in needs JavaScript</h1>
<p>The form was submitted before the page finished loading, so nothing was sent to the
server. Enable JavaScript, reload the page and try again.</p>
<p><a href="/auth/signin">Back to sign in</a></p>
</body></html>`;

export default function handler(req: NextApiRequest, res: NextApiResponse) {
  // Discard the request body without parsing or reading it.
  req.resume();

  if (req.method !== 'POST') {
    res.setHeader('Allow', 'POST');
    return res.status(405).end();
  }

  // Nothing was authenticated, and nothing may be cached or referred onward.
  res.setHeader('Cache-Control', 'no-store');
  res.setHeader('Referrer-Policy', 'no-referrer');
  res.setHeader('Content-Type', 'text/html; charset=utf-8');
  return res.status(503).send(NOTICE);
}
