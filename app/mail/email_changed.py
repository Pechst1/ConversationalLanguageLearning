"""The notice sent to the *old* address once an email change is confirmed.

Values: ``new_email`` (already masked: the old inbox never learns the full new
address) and ``contact`` (``LEGAL_CONTACT_EMAIL``, the address on the legal pages).
"""

TEMPLATES = {
    "en": {
        "subject": "Your L’Atelier address has changed",
        "body": (
            "From now on you sign in to L’Atelier with {new_email}.\n\n"
            "If you did not make this change, write to us at once: {contact}"
        ),
    },
    "de": {
        "subject": "Deine Adresse bei L’Atelier wurde geändert",
        "body": (
            "Ab jetzt meldest du dich bei L’Atelier mit {new_email} an.\n\n"
            "Warst du das nicht? Dann schreib uns sofort: {contact}"
        ),
    },
    "fr": {
        "subject": "Ton adresse L’Atelier a changé",
        "body": (
            "Désormais, tu te connectes à L’Atelier avec {new_email}.\n\n"
            "Ce n’est pas toi ? Écris-nous tout de suite : {contact}"
        ),
    },
}


def render(table: dict[str, str], values: dict) -> tuple[str, str]:
    return table["subject"].format(**values), table["body"].format(**values)
