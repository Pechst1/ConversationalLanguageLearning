"""The one table of short ids a scene uses for the same person (#147).

A leaf module (it imports nothing) so that :mod:`app.services.cast_registry` and
:mod:`app.services.cast_voices` can both read it; before, each kept a copy and a nickname
added to one was unknown to the other.
"""
from __future__ import annotations

#: ``{alias: registry id}``.
ALIASES: dict[str, str] = {
    "odile": "odile_ferrand",
    "marchand": "landlord_marchand",
    "landlord": "landlord_marchand",
    "gus": "augustin_de_roncourt",
    "augustin": "augustin_de_roncourt",
    "marin": "marin_leveque",
    "lila": "lila_bonnet",
    "margaux": "margaux_barman",
    "romy": "romy_tremblay",
    "camille": "camille_marchand",
}
