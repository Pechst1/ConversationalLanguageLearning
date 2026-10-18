"""#211: a collection's root must answer with and without the trailing slash.

The web app asks for `/vocabulary`, `/users`, `/intake`, `/missions`. A route
declared only as `"/"` answers those with a 307 to `/vocabulary/`. Behind the
host's TLS proxy that Location is built with the wrong scheme, the browser
refuses the hop, and the Cahier's word list failed for good ("Try again" asked
the same question and got the same refusal). `missions` and `intake` declare
both spellings; `vocabulary` and `users` did not, and nothing checked.
"""

from __future__ import annotations

import pytest
from fastapi.routing import APIRoute

from app.config import settings
from app.main import create_app


def _roots_missing_slashless_twin() -> list[str]:
    app = create_app()
    prefix = settings.API_V1_STR.rstrip("/")
    registered: set[tuple[str, str]] = set()
    for route in app.routes:
        if isinstance(route, APIRoute):
            for method in route.methods or ():
                registered.add((method, route.path))
    missing = []
    for method, path in sorted(registered):
        if path.endswith("/") and path.startswith(prefix + "/") and path != prefix + "/":
            if (method, path.rstrip("/")) not in registered:
                missing.append(f"{method} {path}")
    return missing


def test_roots_have_slashless_twin():
    missing = _roots_missing_slashless_twin()
    assert not missing, (
        "These routes only answer with a trailing slash, so a client that omits it "
        f"is redirected (307) instead of served: {missing}"
    )


@pytest.mark.asyncio
async def test_vocabulary_no_redirect(async_client, french_vocabulary):
    response = await async_client.get(
        f"{settings.API_V1_STR}/vocabulary",
        params={"language": "fr", "limit": 80, "offset": 0},
        follow_redirects=False,
    )

    assert response.status_code == 200, (
        f"307? got {response.status_code} "
        f"(Location: {response.headers.get('location')})"
    )
    payload = response.json()
    assert payload["total"] == len(french_vocabulary)
    assert {item["word"] for item in payload["items"]} == {w.word for w in french_vocabulary}
