"""The auth forms must never put credentials in a URL.

Static regression for a real defect: `pages/auth/signin.tsx` rendered a `<form>`
with no `method` and no `action`, and its only submit handler was the hydrated
React one. A submit that reached the browser before hydration — a scripted
submit, a password manager, a fast typist — therefore took the browser default:
a **GET to the current URL** with `email` and `password` in the query string.
The credentials then sat in the address bar, in session history, in the
`Referer` header of every subsequent request and in any access log in front of
the app.

The fix is `method="post" action="/api/auth/pre-hydration"`: the pre-hydration
fallback becomes a POST to a route that reads nothing and stores nothing.
NextAuth's client flow is untouched, because the hydrated handler still calls
`preventDefault()`.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web-frontend"
AUTH_PAGES = ("signin.tsx", "signup.tsx", "forgot-password.tsx")
REFUSAL_ROUTE = "/api/auth/pre-hydration"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _form_tags(source: str) -> list[str]:
    return re.findall(r"<form\b[^>]*>", source, flags=re.DOTALL)


def test_every_auth_form_submits_by_post_to_the_refusal_route() -> None:
    for name in AUTH_PAGES:
        source = read(WEB / "pages" / "auth" / name)
        tags = _form_tags(source)
        assert tags, f"{name} has no <form> to check"
        for tag in tags:
            assert 'method="post"' in tag, (
                f"{name}: a form without method=post falls back to GET before "
                f"hydration, which puts the password in the URL: {tag}"
            )
            assert f'action="{REFUSAL_ROUTE}"' in tag, (
                f"{name}: the pre-hydration fallback must target {REFUSAL_ROUTE}, "
                f"not the page's own URL: {tag}"
            )


def test_the_hydrated_handlers_still_own_the_submit() -> None:
    """The POST action is only a fallback; NextAuth's client flow is unchanged."""
    signin = read(WEB / "pages" / "auth" / "signin.tsx")
    assert "onSubmit={handleSubmit(onSubmit)}" in signin
    assert "auth.signInWithCredentials(data.email, data.password)" in signin

    signup = read(WEB / "pages" / "auth" / "signup.tsx")
    assert "onSubmit={handleSubmit(onSubmit)}" in signup

    # The hand-written handlers must prevent the native submit themselves.
    forgot = read(WEB / "pages" / "auth" / "forgot-password.tsx")
    assert forgot.count("event.preventDefault();") >= 2


def test_the_refusal_route_never_reads_or_echoes_the_credentials() -> None:
    route = WEB / "pages" / "api" / "auth" / "pre-hydration.ts"
    assert route.exists(), "the pre-hydration fallback route is missing"
    source = read(route)

    # Body parsing off: the credentials are never materialised server-side.
    assert "bodyParser: false" in source
    assert "req.resume()" in source

    # It refuses rather than authenticating, and forwards nothing onward.
    assert "res.status(503)" in source
    assert "'no-referrer'" in source or '"no-referrer"' in source
    assert "'no-store'" in source or '"no-store"' in source

    # Nothing may log or reflect the submitted values.
    assert "console.log" not in source
    assert "req.body" not in source
    assert "req.query" not in source
    for forbidden in ("password", "email"):
        assert f"req.body.{forbidden}" not in source


def test_no_auth_form_falls_back_to_a_get_submit() -> None:
    """A `method="get"` form, or a bare one, is the exact defect this guards."""
    for name in AUTH_PAGES:
        source = read(WEB / "pages" / "auth" / name)
        for tag in _form_tags(source):
            assert 'method="get"' not in tag.lower(), f"{name}: {tag}"
