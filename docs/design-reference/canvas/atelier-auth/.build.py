exec(open(".gen.py").read())

DATE = "Mercredi 9 septembre 2026"

# ---------- 1 · La une (landing) ----------
def landing(t):
    return col([
        col([
            f'<div style="display: flex; justify-content: center">{mark(t, 26)}</div>',
            f'<div style="text-align: center; font-family: \'EB Garamond\', Georgia, serif; '
            f'font-size: 34px; font-weight: 500; line-height: 1.05; color: {t["ink"]}">L’Atelier</div>',
            f'<div style="text-align: center; font-size: 12px; font-weight: 700; color: {t["muted"]}; '
            f'line-height: 1.4">Quotidien de français · {DATE}</div>',
            rule(t, 6, 0),
        ], gap=8),
        spacer(),
        col([
            headline(t, "« Chaque jour, une édition de français dont vous êtes un personnage. »"),
            body(t, "Un épisode de feuilleton où vous tenez votre rôle, une courte séance d’exercices, "
                    "des progrès consignés noir sur blanc."),
        ], gap=14),
        spacer(),
        col([primary(t, "Se connecter"), secondary(t, "Créer un compte")], gap=10),
    ], gap=18, grow=True)

# ---------- 2 · Se connecter ----------
def signin(t, state="idle"):
    kids = [eyebrow(t, "L’Atelier · Quotidien de français"), headline(t, "Se connecter")]
    if state == "error":
        kids.append(notice(t, "Identifiants incorrects. Vérifiez l’adresse et le mot de passe."))
    kids.append(col([
        field(t, "Adresse e-mail", value="vous@exemple.fr" if state != "idle" else None,
              placeholder="vous@exemple.fr", invalid=(state == "error")),
        field(t, "Mot de passe", value="••••••••••" if state != "idle" else None,
              placeholder="Votre mot de passe", reveal=True, invalid=(state == "error")),
        quiet(t, "Mot de passe oublié ?", align="flex-end"),
    ], gap=12))
    kids += [
        spacer(),
        primary(t, "Se connecter", pending=(state == "pending")),
        quiet(t, f'Nouveau ici ? <span style="color: {t["ink"]}; text-decoration: underline; '
                 f'text-underline-offset: 3px; margin-left: 6px">Créer un compte</span>'),
    ]
    return col(kids, gap=16, grow=True)

# ---------- 3 · Créer un compte ----------
def signup1(t):
    return col([
        col([eyebrow(t, "L’Atelier"), steps(t, 1, 2)], gap=12),
        headline(t, "Créer un compte"),
        body(t, "L’essentiel d’abord. La suite façonne votre première édition.", 14),
        col([
            field(t, "Nom complet", placeholder="Votre nom"),
            field(t, "Adresse e-mail", placeholder="vous@exemple.fr"),
            field(t, "Mot de passe", placeholder="Au moins 8 caractères", reveal=True),
            seg_group(t, "Langue de l’interface", ["English", "Français"], "Français"),
        ], gap=12),
        spacer(),
        primary(t, "Continuer"),
        quiet(t, f'Déjà inscrit ? <span style="color: {t["ink"]}; text-decoration: underline; '
                 f'text-underline-offset: 3px; margin-left: 6px">Se connecter</span>'),
    ], gap=14, grow=True)

def signup2(t):
    return col([
        col([eyebrow(t, "L’Atelier"), steps(t, 2, 2)], gap=12),
        headline(t, "Votre première édition", 30),
        body(t, "Ces réponses composent la séance de demain. Tout se change ensuite dans Réglages.", 14),
        choice_rows(t, "Pourquoi le français ?", [
            "Voyager et me débrouiller",
            "Travailler en français",
            "Parler avec mes proches",
            "Lire, regarder, écouter",
        ], "Parler avec mes proches"),
        seg_group(t, "Minutes par jour", ["5", "10", "15", "20"], "10"),
        seg_group(t, "Corrections", ["Légère", "Équilibrée", "Complète"], "Équilibrée"),
        spacer(),
        primary(t, "Ouvrir ma première édition"),
    ], gap=14, grow=True)

# ---------- 4 · Mot de passe ----------
def reset(t, state):
    if state == "request":
        mid = [
            headline(t, "Mot de passe oublié"),
            body(t, "Indiquez votre adresse : nous envoyons un lien pour en choisir un nouveau."),
            field(t, "Adresse e-mail", placeholder="vous@exemple.fr"),
        ]
        action = primary(t, "Envoyer le lien")
    elif state == "sent":
        mid = [
            headline(t, "Vérifiez votre boîte"),
            notice(t, "Si un compte existe pour cette adresse, le lien vient d’y partir. "
                      "Il expire dans une heure.", tone="done"),
            body(t, "Rien reçu au bout de quelques minutes ? Regardez les indésirables, "
                    "puis redemandez un lien.", 14),
        ]
        action = secondary(t, "Renvoyer le lien")
    elif state == "new":
        mid = [
            headline(t, "Nouveau mot de passe"),
            body(t, "Choisissez-en un que vous n’utilisez pas ailleurs."),
            col([
                field(t, "Nouveau mot de passe", placeholder="Au moins 8 caractères", reveal=True),
                field(t, "Confirmer", placeholder="Le même, une seconde fois", reveal=True),
            ], gap=12),
        ]
        action = primary(t, "Enregistrer")
    else:  # expired
        mid = [
            headline(t, "Ce lien a expiré"),
            notice(t, "Les liens durent une heure, puis ils cessent de fonctionner. "
                      "Votre mot de passe actuel n’a pas changé."),
            body(t, "Demandez-en un nouveau : il arrivera à la même adresse.", 14),
        ]
        action = primary(t, "Demander un nouveau lien")
    return col([
        eyebrow(t, "L’Atelier · Quotidien de français"),
        col(mid, gap=14),
        spacer(),
        action,
        quiet(t, "Retour à la connexion"),
    ], gap=16, grow=True)

write("Main.dc.html",         LIGHT, landing(LIGHT))
write("LaUneSombre.dc.html",  DARK,  landing(DARK))
write("Connexion.dc.html",       LIGHT, signin(LIGHT, "idle"))
write("ConnexionErreur.dc.html", LIGHT, signin(LIGHT, "error"))
write("ConnexionSombre.dc.html", DARK,  signin(DARK, "pending"))
write("CompteEtape1.dc.html",    LIGHT, signup1(LIGHT))
write("CompteEtape2.dc.html",    LIGHT, signup2(LIGHT))
write("CompteSombre.dc.html",    DARK,  signup2(DARK))
write("MotDePasseDemande.dc.html", LIGHT, reset(LIGHT, "request"))
write("MotDePasseEnvoye.dc.html",  LIGHT, reset(LIGHT, "sent"))
write("MotDePasseNouveau.dc.html", LIGHT, reset(LIGHT, "new"))
write("MotDePasseExpire.dc.html",  DARK,  reset(DARK, "expired"))
