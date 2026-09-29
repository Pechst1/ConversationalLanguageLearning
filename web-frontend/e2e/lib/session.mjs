// Sign-in by API: register through the real endpoint, log in for tokens, mint the
// NextAuth session cookie. No password is ever typed into a page.
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const { encode } = require('next-auth/jwt');

export async function registerLearner({ api, secret, native = 'en', level = 'A1.1', tag = 'walk' }) {
  const email = `${tag}-${native}-${Date.now()}-${Math.floor(Math.random() * 1e4)}@example.com`;
  const password = `Walk-${Math.random().toString(36).slice(2)}-Aa1!`;
  const reg = await fetch(`${api}/auth/register`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ email, password, full_name: `Walk ${native}`, native_language: native, starting_point: level.startsWith('B') ? 'comfortable' : level.startsWith('A2') ? 'some' : 'new' }),
  });
  if (!reg.ok) throw new Error(`register failed ${reg.status}: ${await reg.text()}`);
  const login = await fetch(`${api}/auth/login`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  if (!login.ok) throw new Error(`login failed ${login.status}`);
  const tokens = await login.json();
  const me = await (await fetch(`${api}/users/me`, { headers: { authorization: `Bearer ${tokens.access_token}` } })).json();
  const exp = JSON.parse(Buffer.from(tokens.access_token.split('.')[1], 'base64url').toString()).exp * 1000;
  const cookie = await encode({
    secret,
    token: {
      accessToken: tokens.access_token,
      refreshToken: tokens.refresh_token,
      accessTokenExpires: exp,
      id: me.id,
      sub: me.id,
      email,
      name: me.full_name,
    },
  });
  return { email, id: me.id, accessToken: tokens.access_token, cookie, me };
}
