"""The password-reset mail: the six-digit code first, the link only when public.

Values: ``code``, ``reset_url`` (or ``None``), ``ttl_minutes``, ``link_ttl_minutes``.
"""

TEMPLATES = {
    "en": {
        "subject": "{code} – your L’Atelier code",
        "body": (
            "Your code to reset your password:\n\n    {code}\n\n"
            "Enter it in the app. It works once, for {ttl_minutes} minutes."
        ),
        "link": "\n\nOr open this link (valid for {link_ttl_minutes} minutes):\n{reset_url}",
        "footer": "\n\nDidn’t ask for this? You can ignore this email.",
    },
    "de": {
        "subject": "{code} – dein Code für L’Atelier",
        "body": (
            "Dein Code zum Zurücksetzen des Passworts:\n\n    {code}\n\n"
            "Gib ihn in der App ein. Er gilt {ttl_minutes} Minuten und nur einmal."
        ),
        "link": "\n\nOder öffne diesen Link ({link_ttl_minutes} Minuten gültig):\n{reset_url}",
        "footer": "\n\nDu hast das nicht angefordert? Dann ignoriere diese E-Mail.",
    },
    "fr": {
        "subject": "{code} – ton code L’Atelier",
        "body": (
            "Ton code pour choisir un nouveau mot de passe :\n\n    {code}\n\n"
            "Saisis-le dans l’application. Valable {ttl_minutes} minutes, une seule fois."
        ),
        "link": "\n\nOu ouvre ce lien (valable {link_ttl_minutes} minutes) :\n{reset_url}",
        "footer": "\n\nTu n’as rien demandé ? Ignore simplement ce message.",
    },
}


def render(table: dict[str, str], values: dict) -> tuple[str, str]:
    body = table["body"].format(**values)
    if values.get("reset_url"):
        body += table["link"].format(**values)
    return table["subject"].format(**values), body + table["footer"]
