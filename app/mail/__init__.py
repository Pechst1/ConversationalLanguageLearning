"""S4 stage 3 — every mail the app sends, one template per kind and language.

``render_mail(kind, language, **values)`` returns ``(subject, body)``. The
outbox (``app/services/mail_outbox.py``) builds and sends; nothing else writes
mail text. Each kind has en, de and fr, and addresses the learner with tu / du.

The language is the learner's own (``mail_language``), not the level-dependent
chrome language: a code or a security notice must be read, whatever the level.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.mail import email_changed, password_reset, verify_email
from app.services.chrome_language import user_mother_tongue

MailKind = str

_KINDS: dict[str, Any] = {
    "password_reset": password_reset,
    "verify_email": verify_email,
    "email_changed": email_changed,
}
MAIL_KINDS: tuple[str, ...] = tuple(_KINDS)
MAIL_LANGUAGES = ("en", "de", "fr")


def mail_language(user: Any) -> str:
    """The learner's mother tongue when the app speaks it; English otherwise."""
    language = user_mother_tongue(user)
    return language if language in MAIL_LANGUAGES else "en"


def render_mail(kind: str, language: str, **values: Any) -> tuple[str, str]:
    module = _KINDS[kind]
    table = module.TEMPLATES.get(language) or module.TEMPLATES["en"]
    renderer: Callable[[dict[str, str], dict], tuple[str, str]] = module.render
    return renderer(table, values)


def mask_email(email: str) -> str:
    """``name@example.com`` → ``n***@example.com``."""
    local, _, domain = (email or "").partition("@")
    return f"{local[:1]}***@{domain}" if domain else "***"
