"""The verification mail: a six-digit code for this address.

``purpose`` is ``signup`` (a new account), ``change`` (this is the new address
of an existing account; the change waits for this code) or ``reset`` (a password
reset was asked for an address not yet confirmed: this code works on the reset
screen and confirms the address at the same time).
Values: ``code``, ``purpose``, ``ttl_hours``.
"""

TEMPLATES = {
    "en": {
        "subject": "{code} – confirm your address for L’Atelier",
        "signup": "Welcome to L’Atelier. To confirm this is your address, enter this code in the app:",
        "change": "You asked to sign in to L’Atelier with this address from now on. To confirm it, enter this code in the app:",
        "reset": "You asked to reset your L’Atelier password. Your address is not confirmed yet, so this code does both: enter it on the reset screen with your new password.",
        "body": "\n\n    {code}\n\nIt is valid for {ttl_hours} hours.",
        "footer": "\n\nDidn’t ask for this? You can ignore this email; nothing changes.",
    },
    "de": {
        "subject": "{code} – bestätige deine Adresse für L’Atelier",
        "signup": "Willkommen bei L’Atelier. Damit wir wissen, dass das deine Adresse ist, gib diesen Code in der App ein:",
        "change": "Du möchtest dich bei L’Atelier ab jetzt mit dieser Adresse anmelden. Zur Bestätigung gib diesen Code in der App ein:",
        "reset": "Du möchtest dein Passwort bei L’Atelier zurücksetzen. Deine Adresse ist noch nicht bestätigt, darum macht dieser Code beides: Gib ihn mit deinem neuen Passwort auf der Seite zum Zurücksetzen ein.",
        "body": "\n\n    {code}\n\nEr gilt {ttl_hours} Stunden.",
        "footer": "\n\nDu hast das nicht angefordert? Dann ignoriere diese E-Mail; es ändert sich nichts.",
    },
    "fr": {
        "subject": "{code} – confirme ton adresse pour L’Atelier",
        "signup": "Bienvenue dans L’Atelier. Pour confirmer que cette adresse est bien la tienne, saisis ce code dans l’application :",
        "change": "Tu as demandé à te connecter à L’Atelier avec cette adresse désormais. Pour la confirmer, saisis ce code dans l’application :",
        "reset": "Tu as demandé un nouveau mot de passe pour L’Atelier. Ton adresse n’est pas encore confirmée, alors ce code fait les deux : saisis-le avec ton nouveau mot de passe sur l’écran de réinitialisation.",
        "body": "\n\n    {code}\n\nIl est valable {ttl_hours} heures.",
        "footer": "\n\nTu n’as rien demandé ? Ignore simplement ce message ; rien ne change.",
    },
}


def render(table: dict[str, str], values: dict) -> tuple[str, str]:
    intro = table.get(values.get("purpose") or "signup") or table["signup"]
    return table["subject"].format(**values), intro + table["body"].format(**values) + table["footer"]
