#!/usr/bin/env python
"""WP-120 phase D · the walk API with La Revue switched on, for ``carte-shows-where-i-was``.

``scripts/dev_walk_server.py`` (the fake story engine, the test clock, the throwaway-
database guard) plus ``REVUE_ENABLED``, with Romy and the vignette's pictogram on their
deterministic providers. The walk server fakes every provider key, so the Revue's own
``default_provider()`` would otherwise pick the real model clients: here they are
replaced in-process, and no model call can leave it. Started by ``e2e/lib/stack.mjs``
when the walk asks for ``revue: true``; the 7-day walk keeps the Revue off (it changes
the day shapes).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO))
os.environ["REVUE_ENABLED"] = "true"

import dev_walk_server  # noqa: E402,F401  (sets the walk's environment on import)
import dev_story_engine_server as base  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8010)
    args = parser.parse_args()
    base._guard_environment()

    import uvicorn

    from app.api.v1.endpoints.revue import get_revue_provider
    from app.main import app
    from app.services import living_story as engine
    from app.services.revue import pictogram
    from app.services.revue.encounter import FakeRevueProvider

    story = base.FakeStoryProvider()
    engine._client = lambda: story
    app.dependency_overrides[get_revue_provider] = lambda: FakeRevueProvider()
    pictogram.default_pictogram_provider = lambda: pictogram.FakePictogramProvider()
    print(
        f"[carte-walk] fake story, Revue and pictogram providers; REVUE_ENABLED=true; "
        f"DATABASE_URL={os.environ['DATABASE_URL']}",
        flush=True,
    )
    uvicorn.run(app, host=args.host, port=args.port, timeout_keep_alive=75)


if __name__ == "__main__":
    main()
