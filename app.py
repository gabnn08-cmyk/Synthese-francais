import hashlib
import hmac
import html
import json
import os
import re
import secrets
import threading
import unicodedata
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.rows import dict_row

BASE_DIR = Path(__file__).resolve().parent
DATABASE_URL = os.environ.get("DATABASE_URL")
DATABASE_SSLMODE = os.environ.get("DATABASE_SSLMODE")
DATABASE_SCHEMA = os.environ.get("DATABASE_SCHEMA", "public")
if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", DATABASE_SCHEMA):
    raise RuntimeError("DATABASE_SCHEMA doit etre un identifiant PostgreSQL simple.")
STATIC_DIR = BASE_DIR / "static"
SESSION_DAYS = int(os.environ.get("SESSION_DAYS", "14"))
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "auto").lower()
DEMO_MODE = os.environ.get("DEMO_MODE", "false").lower() in {"1", "true", "yes"}
SITE_NAME = os.environ.get("SITE_NAME", "Synthese de francais")
SITE_URL = os.environ.get("SITE_URL", "")
LEGAL_ENTITY_NAME = os.environ.get("LEGAL_ENTITY_NAME", "Etablissement responsable du service")
LEGAL_ENTITY_STATUS = os.environ.get("LEGAL_ENTITY_STATUS", "Etablissement scolaire")
LEGAL_ENTITY_ADDRESS = os.environ.get("LEGAL_ENTITY_ADDRESS", "Adresse a completer")
LEGAL_CONTACT_EMAIL = os.environ.get("LEGAL_CONTACT_EMAIL", "contact@example.fr")
LEGAL_CONTACT_PHONE = os.environ.get("LEGAL_CONTACT_PHONE", "Telephone a completer")
LEGAL_PUBLICATION_DIRECTOR = os.environ.get("LEGAL_PUBLICATION_DIRECTOR", "Responsable de publication a completer")
LEGAL_DPO_CONTACT = os.environ.get("LEGAL_DPO_CONTACT", LEGAL_CONTACT_EMAIL)
HOSTING_PROVIDER_NAME = os.environ.get("HOSTING_PROVIDER_NAME", "Hebergeur a completer")
HOSTING_PROVIDER_ADDRESS = os.environ.get("HOSTING_PROVIDER_ADDRESS", "Adresse de l'hebergeur a completer")
HOSTING_PROVIDER_PHONE = os.environ.get("HOSTING_PROVIDER_PHONE", "Telephone de l'hebergeur a completer")
PRIVACY_ACCOUNT_RETENTION = os.environ.get("PRIVACY_ACCOUNT_RETENTION", "jusqu'a 12 mois apres la derniere activite du compte")
PRIVACY_EVALUATION_RETENTION = os.environ.get("PRIVACY_EVALUATION_RETENTION", "pendant l'annee scolaire en cours puis selon la politique de l'etablissement")
PRIVACY_SESSION_RETENTION = os.environ.get("PRIVACY_SESSION_RETENTION", f"{SESSION_DAYS} jours maximum")
ACCESSIBILITY_CONTACT = os.environ.get("ACCESSIBILITY_CONTACT", LEGAL_CONTACT_EMAIL)
ACCESSIBILITY_MULTIYEAR_PLAN_URL = os.environ.get("ACCESSIBILITY_MULTIYEAR_PLAN_URL", "")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]
ADMIN_FULL_NAME = os.environ.get("ADMIN_FULL_NAME", "Administrateur")
TEACHER_USERNAME = os.environ.get("TEACHER_USERNAME", "prof.francais")
TEACHER_PASSWORD = os.environ.get("TEACHER_PASSWORD", ADMIN_PASSWORD)
TEACHER_FULL_NAME = os.environ.get("TEACHER_FULL_NAME", "Professeur de francais")
STAFF_ROLES = {"admin", "teacher"}
WRITE_LOCK = threading.Lock()


def utc_now():
    return datetime.now(timezone.utc)


def iso_now():
    return utc_now().isoformat()


def escape_html(value):
    return html.escape(str(value or ""), quote=True)


def format_contact_link(value):
    safe_value = escape_html(value)
    if "@" in value:
        return f'<a href="mailto:{safe_value}">{safe_value}</a>'
    return safe_value


def compliance_navigation():
    return (
        '<nav class="compliance-nav" aria-label="Informations legales">'
        '<a href="/">Accueil</a>'
        '<a href="/mentions-legales">Mentions legales</a>'
        '<a href="/confidentialite">Confidentialite</a>'
        '<a href="/cookies">Cookies</a>'
        '<a href="/accessibilite">Accessibilite : non conforme</a>'
        "</nav>"
    )


def render_information_page(title, intro, sections):
    rendered_sections = []
    for heading, paragraphs in sections:
        content = "".join(f"<p>{paragraph}</p>" for paragraph in paragraphs)
        rendered_sections.append(f'<section class="legal-section"><h2>{heading}</h2>{content}</section>')
    body = "".join(rendered_sections)
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{escape_html(title)} | {escape_html(SITE_NAME)}</title>
  <meta name="robots" content="noindex">
  <link rel="stylesheet" href="/styles.css">
</head>
<body>
  <a class="skip-link" href="#content">Aller au contenu principal</a>
  <div class="page-shell">
    <header class="hero hero-compact">
      <p class="eyebrow">Information reglementaire</p>
      <h1>{escape_html(title)}</h1>
      <p class="hero-copy">{intro}</p>
      {compliance_navigation()}
    </header>
    <main id="content" class="legal-layout" tabindex="-1">
      {body}
    </main>
  </div>
</body>
</html>"""


def render_mentions_legales():
    site_reference = escape_html(SITE_URL) if SITE_URL else "Adresse du site a completer"
    return render_information_page(
        "Mentions legales",
        "Cette page regroupe les informations d'identification de l'editeur du service, du responsable de publication et de son hebergeur.",
        [
            (
                "Editeur du service",
                [
                    f"<strong>Nom de l'organisme :</strong> {escape_html(LEGAL_ENTITY_NAME)}",
                    f"<strong>Statut :</strong> {escape_html(LEGAL_ENTITY_STATUS)}",
                    f"<strong>Adresse :</strong> {escape_html(LEGAL_ENTITY_ADDRESS)}",
                    f"<strong>Courriel :</strong> {format_contact_link(LEGAL_CONTACT_EMAIL)}",
                    f"<strong>Telephone :</strong> {escape_html(LEGAL_CONTACT_PHONE)}",
                    f"<strong>Adresse du site :</strong> {site_reference}",
                ],
            ),
            (
                "Direction de la publication",
                [f"<strong>Responsable de publication :</strong> {escape_html(LEGAL_PUBLICATION_DIRECTOR)}"],
            ),
            (
                "Hebergement",
                [
                    f"<strong>Hebergeur :</strong> {escape_html(HOSTING_PROVIDER_NAME)}",
                    f"<strong>Adresse :</strong> {escape_html(HOSTING_PROVIDER_ADDRESS)}",
                    f"<strong>Telephone :</strong> {escape_html(HOSTING_PROVIDER_PHONE)}",
                ],
            ),
            (
                "Propriete intellectuelle",
                [
                    "Les contenus fournis dans ce service sont reserves a un usage pedagogique interne, sauf mention contraire.",
                    "Toute reutilisation externe des textes, evaluations ou donnees nominatives doit etre autorisee par l'organisme responsable du service.",
                ],
            ),
        ],
    )


def render_confidentialite():
    return render_information_page(
        "Politique de confidentialite",
        "Le service traite des donnees personnelles d'eleves et de membres de l'equipe pedagogique pour permettre l'authentification, la saisie d'evaluations et la consultation de syntheses.",
        [
            (
                "Responsable du traitement",
                [
                    f"Le responsable du traitement est <strong>{escape_html(LEGAL_ENTITY_NAME)}</strong>, joignable a l'adresse {format_contact_link(LEGAL_CONTACT_EMAIL)}.",
                    f"Pour toute question relative a la protection des donnees, vous pouvez contacter le point de contact RGPD a l'adresse {format_contact_link(LEGAL_DPO_CONTACT)}.",
                ],
            ),
            (
                "Donnees traitees",
                [
                    "Le service traite les donnees d'identification du compte, les mots de passe sous forme hachee, les donnees de session techniques, ainsi que les evaluations pedagogiques saisies dans l'application.",
                ],
            ),
            (
                "Finalites et bases legales",
                [
                    "Les donnees sont traitees pour creer les comptes, authentifier les utilisateurs, permettre la saisie et la consultation des evaluations, ainsi que produire des syntheses pedagogiques.",
                    "La base legale est l'execution d'une mission d'interet public ou l'interet legitime de l'organisme gestionnaire, selon le cadre d'utilisation effectif du service dans l'etablissement.",
                ],
            ),
            (
                "Caractere obligatoire des donnees",
                [
                    "Les informations demandees lors de la creation d'un compte sont necessaires pour ouvrir l'acces au service et rattacher les evaluations au bon eleve.",
                    "En l'absence de ces informations, le compte ne peut pas etre cree.",
                ],
            ),
            (
                "Destinataires",
                [
                    "Les donnees sont accessibles aux eleves pour leur propre espace, ainsi qu'aux personnels autorises disposant d'un role administrateur ou professeure dans l'application.",
                    "L'hebergeur et les prestataires techniques agissent, le cas echeant, en qualite de sous-traitants pour la mise a disposition du service.",
                ],
            ),
            (
                "Durees de conservation",
                [
                    f"Les comptes utilisateurs sont conserves {escape_html(PRIVACY_ACCOUNT_RETENTION)}.",
                    f"Les evaluations sont conservees {escape_html(PRIVACY_EVALUATION_RETENTION)}.",
                    f"Les sessions d'authentification sont conservees {escape_html(PRIVACY_SESSION_RETENTION)}.",
                ],
            ),
            (
                "Droits des personnes",
                [
                    "Vous disposez d'un droit d'acces, de rectification, d'effacement, de limitation et, selon la base legale applicable, d'un droit d'opposition.",
                    f"Ces droits peuvent etre exerces en ecrivant a {format_contact_link(LEGAL_DPO_CONTACT)}.",
                    'Vous pouvez egalement introduire une reclamation aupres de la <a href="https://www.cnil.fr/fr/plaintes" rel="noreferrer" target="_blank">CNIL</a>.',
                ],
            ),
            (
                "Transferts hors Union europeenne",
                [
                    "Le service est concu pour limiter les transferts hors Union europeenne. En cas d'utilisation d'un prestataire impliquant un transfert, l'information correspondante et les garanties applicables devront etre communiquees sur cette page.",
                ],
            ),
        ],
    )


def render_cookies():
    return render_information_page(
        "Politique cookies",
        "Le site utilise uniquement les traceurs strictement necessaires a son fonctionnement, sauf ajout ulterieur d'outils necessitant un consentement prealable.",
        [
            (
                "Cookie necessaire",
                [
                    f"Un cookie de session d'authentification nomme <code>session_token</code> est depose pour maintenir la connexion pendant une duree maximale de {SESSION_DAYS} jours.",
                    "Ce cookie est utilise exclusivement pour l'authentification et la securite du service. Il ne sert ni a la publicite ni a la mesure d'audience.",
                ],
            ),
            (
                "Absence de traceurs marketing",
                [
                    "Aucun cookie publicitaire, aucun traceur de reseau social et aucun outil de mesure d'audience soumis au consentement n'est depose par defaut.",
                    "Si de nouveaux traceurs non strictement necessaires sont ajoutes, un mecanisme de recueil du consentement devra etre mis en place avant leur depot.",
                ],
            ),
            (
                "Gestion des preferences",
                [
                    "Comme seuls des traceurs strictement necessaires sont utilises a ce jour, aucune banniere de consentement n'est affichee.",
                    f"Pour toute question, vous pouvez ecrire a {format_contact_link(LEGAL_CONTACT_EMAIL)}.",
                ],
            ),
        ],
    )


def render_accessibilite():
    action_plan = (
        f'Le schema pluriannuel de mise en accessibilite est consultable a l\'adresse <a href="{escape_html(ACCESSIBILITY_MULTIYEAR_PLAN_URL)}">{escape_html(ACCESSIBILITY_MULTIYEAR_PLAN_URL)}</a>.'
        if ACCESSIBILITY_MULTIYEAR_PLAN_URL
        else "Le schema pluriannuel de mise en accessibilite n'est pas encore publie sur ce service."
    )
    return render_information_page(
        "Accessibilite numerique",
        "Etat de conformite au RGAA au 27 mai 2026 : non conforme. Aucun audit complet n'a encore permis d'etablir un taux de conformite opposable.",
        [
            (
                "Declaration de conformite",
                [
                    "Cette declaration s'applique au service web de synthese des evaluations de francais.",
                    "Faute d'audit complet, le service est actuellement declare non conforme au Referentiel general d'amelioration de l'accessibilite.",
                ],
            ),
            (
                "Contenus non accessibles identifies a ce stade",
                [
                    "Certaines restitutions dynamiques JavaScript n'ont pas encore fait l'objet d'une validation complete avec technologies d'assistance.",
                    "Les parcours de tableau et certains messages de statut doivent encore etre testes et, si necessaire, ajustes apres audit.",
                ],
            ),
            (
                "Ameliorations deja mises en place",
                [
                    "Le site est en francais, dispose d'un lien d'evitement, d'une navigation visible vers les pages reglementaires et de messages d'erreur prevus pour etre annonces aux technologies d'assistance.",
                ],
            ),
            (
                "Retour d'information et contact",
                [
                    f"Si vous ne parvenez pas a acceder a un contenu ou a un service, vous pouvez contacter {format_contact_link(ACCESSIBILITY_CONTACT)} pour etre oriente vers une alternative accessible ou obtenir le contenu sous une autre forme.",
                ],
            ),
            (
                "Voies de recours",
                [
                    "Si vous constatez un defaut d'accessibilite vous empechant d'acceder a un contenu et que vous ne recevez pas de reponse satisfaisante, vous pouvez saisir le Defenseur des droits.",
                    action_plan,
                ],
            ),
        ],
    )


def get_db():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL doit pointer vers une base PostgreSQL.")
    conninfo = database_conninfo()
    return psycopg.connect(conninfo, row_factory=dict_row, autocommit=True, prepare_threshold=None)


def database_conninfo():
    params = conninfo_to_dict(DATABASE_URL)
    host = params.get("host", "")
    if "sslmode" not in params:
        sslmode = DATABASE_SSLMODE or ("require" if "supabase.co" in host else "prefer")
        params["sslmode"] = sslmode
    if "connect_timeout" not in params:
        params["connect_timeout"] = "10"
    if "application_name" not in params:
        params["application_name"] = "synthese-francais"
    if DATABASE_SCHEMA != "public":
        params["options"] = f"-c search_path={DATABASE_SCHEMA},public"
    return make_conninfo(**params)


def hash_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 260_000)
    return f"pbkdf2_sha256${salt}${digest.hex()}"


def verify_password(password, stored):
    if not stored:
        return False
    if not stored.startswith("pbkdf2_sha256$"):
        return hmac.compare_digest(password, stored)
    _, salt, digest = stored.split("$", 2)
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 260_000)
    return hmac.compare_digest(candidate.hex(), digest)


def add_column_if_missing(conn, table, column, definition):
    exists = conn.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s AND column_name = %s
        """,
        (DATABASE_SCHEMA, table, column),
    ).fetchone()
    if not exists:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def ensure_user_role_constraint(conn):
    constraints = conn.execute(
        """
        SELECT conname
        FROM pg_constraint
        WHERE conrelid = %s::regclass AND contype = 'c' AND pg_get_constraintdef(oid) LIKE %s
        """,
        ("users", "%role%teacher%student%"),
    ).fetchall()
    for constraint in constraints:
        conn.execute(sql.SQL("ALTER TABLE users DROP CONSTRAINT {}").format(sql.Identifier(constraint["conname"])))
    conn.execute("ALTER TABLE users ADD CONSTRAINT users_role_check CHECK(role IN ('admin', 'teacher', 'student'))")


def init_db():
    with WRITE_LOCK:
        conn = get_db()
        try:
            conn.execute("BEGIN")
            if DATABASE_SCHEMA != "public":
                conn.execute(f"CREATE SCHEMA IF NOT EXISTS {DATABASE_SCHEMA}")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL DEFAULT '',
                    password_hash TEXT,
                    full_name TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('admin', 'teacher', 'student')),
                    created_at TEXT NOT NULL DEFAULT ''
                )
                """
            )
            add_column_if_missing(conn, "users", "password_hash", "TEXT")
            add_column_if_missing(conn, "users", "created_at", "TEXT NOT NULL DEFAULT ''")
            ensure_user_role_constraint(conn)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS evaluations (
                    id SERIAL PRIMARY KEY,
                    student_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    evaluation_type TEXT NOT NULL CHECK(evaluation_type IN ('ecrit', 'oral')),
                    trimester INTEGER NOT NULL DEFAULT 1 CHECK(trimester IN (1, 2, 3)),
                    subject_area TEXT NOT NULL,
                    evaluation_date TEXT NOT NULL,
                    score DOUBLE PRECISION NOT NULL CHECK(score >= 0),
                    max_score DOUBLE PRECISION NOT NULL CHECK(max_score > 0),
                    appreciation TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE
                )
                """
            )
            add_column_if_missing(conn, "evaluations", "trimester", "INTEGER NOT NULL DEFAULT 1 CHECK(trimester IN (1, 2, 3))")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    token TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                )
                """
            )
            migrate_plain_passwords(conn)
            ensure_staff_accounts(conn)
            if DEMO_MODE:
                ensure_demo_students(conn)
            conn.execute("DELETE FROM sessions WHERE expires_at < %s", (iso_now(),))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def migrate_plain_passwords(conn):
    rows = conn.execute("SELECT id, password, password_hash FROM users").fetchall()
    for row in rows:
        if row["password"] and not row["password_hash"]:
            conn.execute(
                "UPDATE users SET password_hash = %s, password = '' WHERE id = %s",
                (hash_password(row["password"]), row["id"]),
            )


def ensure_account(conn, username, password, full_name, role):
    row = conn.execute("SELECT id, password_hash, role FROM users WHERE username = %s", (username,)).fetchone()
    if row:
        if not row["password_hash"] and password:
            conn.execute("UPDATE users SET password_hash = %s WHERE id = %s", (hash_password(password), row["id"]))
        if row["role"] != role:
            conn.execute("UPDATE users SET role = %s WHERE id = %s", (role, row["id"]))
        return
    conn.execute(
        "INSERT INTO users (username, password, password_hash, full_name, role, created_at) VALUES (%s, '', %s, %s, %s, %s)",
        (username, hash_password(password), full_name, role, iso_now()),
    )


def ensure_staff_accounts(conn):
    if ADMIN_USERNAME == TEACHER_USERNAME:
        raise RuntimeError("ADMIN_USERNAME et TEACHER_USERNAME doivent etre differents.")
    ensure_account(conn, ADMIN_USERNAME, ADMIN_PASSWORD, ADMIN_FULL_NAME, "admin")
    ensure_account(conn, TEACHER_USERNAME, TEACHER_PASSWORD, TEACHER_FULL_NAME, "teacher")


def ensure_demo_students(conn):
    demo_students = [
        ("emma.dupont", "eleve123", "Emma Dupont"),
        ("leo.bernard", "eleve123", "Leo Bernard"),
        ("jade.moreau", "eleve123", "Jade Moreau"),
    ]
    for username, password, full_name in demo_students:
        exists = conn.execute("SELECT id FROM users WHERE username = %s", (username,)).fetchone()
        if not exists:
            conn.execute(
                "INSERT INTO users (username, password, password_hash, full_name, role, created_at) VALUES (%s, '', %s, %s, 'student', %s)",
                (username, hash_password(password), full_name, iso_now()),
            )


def row_to_dict(row):
    data = dict(row)
    data.pop("password", None)
    data.pop("password_hash", None)
    return data


def get_user_by_id(user_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE id = %s", (user_id,)).fetchone()
    conn.close()
    return row_to_dict(row) if row else None


def get_login_user(username):
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE username = %s", (username,)).fetchone()
    conn.close()
    return row


def list_students():
    conn = get_db()
    rows = conn.execute(
        "SELECT id, username, full_name, created_at FROM users WHERE role = 'student' ORDER BY full_name"
    ).fetchall()
    conn.close()
    return [row_to_dict(row) for row in rows]


def list_evaluations(student_id=None):
    conn = get_db()
    query = """
        SELECT e.*, u.full_name AS student_name
        FROM evaluations e
        JOIN users u ON u.id = e.student_id
    """
    params = []
    if student_id is not None:
        query += " WHERE e.student_id = %s"
        params.append(student_id)
    query += " ORDER BY e.evaluation_date DESC, e.created_at DESC"
    rows = conn.execute(query, tuple(params)).fetchall()
    conn.close()
    return [row_to_dict(row) for row in rows]


def get_evaluation_by_id(evaluation_id):
    conn = get_db()
    row = conn.execute(
        """
        SELECT e.*, u.full_name AS student_name
        FROM evaluations e
        JOIN users u ON u.id = e.student_id
        WHERE e.id = %s
        """,
        (evaluation_id,),
    ).fetchone()
    conn.close()
    return row_to_dict(row) if row else None


def mean(values):
    return round(sum(values) / len(values), 2) if values else None


def score_percent(evaluation):
    return (evaluation["score"] / evaluation["max_score"]) * 20 if evaluation["max_score"] else 0


NO_EXPLICIT_STRENGTH = "Les appreciations saisies ne formulent pas encore de point fort explicite."
NO_EXPLICIT_VIGILANCE = "Les appreciations saisies ne formulent pas encore de point de vigilance explicite."
NO_EXPLICIT_ADVICE = "Aucun conseil concret ne peut etre deduit sans indication explicite dans les appreciations."
NO_CLASS_STRENGTH_TREND = "Aucune tendance positive explicite ne ressort encore des appreciations."
NO_CLASS_ADVICE_TREND = "Aucun axe de conseil recurrent ne ressort encore des appreciations."

POSITIVE_MARKERS = [
    "bon",
    "bonne",
    "solide",
    "convaincant",
    "reussi",
    "maitrise",
    "aisance",
    "rigoureux",
    "serieux",
    "pertinent",
    "clair",
    "efficace",
    "precis",
]

NEGATIVE_MARKERS = [
    "pas",
    "pas assez",
    "peu",
    "manque",
    "fragile",
    "difficil",
    "insuffisant",
    "a revoir",
    "a travailler",
    "attention",
]

IMPROVEMENT_MARKERS = [
    "approfond",
    "amelior",
    "renforc",
    "consolid",
    "retravaill",
    "travaill",
    "manque",
    "fragile",
    "difficil",
    "insuffisant",
    "attention",
    "pas assez",
    "peu",
    "revoir",
    "a revoir",
    "a travailler",
    "gagner",
    "developp",
    "preciser",
    "structurer",
    "justifier",
    "faut",
]

POSITIVE_RULES = [
    {
        "keywords": ["analyse", "commentaire", "interpretation"],
        "label": "Une capacite d'analyse est explicitement soulignee.",
    },
    {
        "keywords": ["argument", "argumentation"],
        "label": "Une argumentation solide est signalee.",
    },
    {
        "keywords": ["oral", "prise de parole"],
        "label": "Une aisance a l'oral est mentionnee.",
    },
    {
        "keywords": ["ecrit", "redaction", "expression", "style"],
        "label": "Une expression ecrite convaincante est relevee.",
    },
    {
        "keywords": ["lecture", "comprehension"],
        "label": "Une bonne comprehension des textes est relevee.",
    },
    {
        "keywords": ["rigueur", "serieux", "regularite", "autonomie"],
        "label": "La rigueur et le serieux du travail sont valorises.",
    },
    {
        "keywords": ["orthographe", "accord"],
        "label": "La maitrise orthographique est valorisee.",
    },
    {
        "keywords": ["syntaxe", "phrase"],
        "label": "La qualite de la syntaxe est relevee.",
    },
    {
        "keywords": ["methode", "consigne"],
        "label": "La methode est valorisee.",
    },
    {
        "keywords": ["vocabulaire", "lexique"],
        "label": "Le vocabulaire est valorise.",
    },
]

IMPROVEMENT_RULES = [
    {
        "keywords": ["analyse", "commentaire", "interpretation", "approfond"],
        "point": "Un approfondissement de l'analyse est demande.",
        "advice": "Pour approfondir l'analyse, partir d'une idee precise, l'appuyer sur un exemple du texte, puis expliquer l'effet produit.",
    },
    {
        "keywords": ["precision", "precis"],
        "point": "Le besoin de precision est mentionne dans les appreciations.",
        "advice": "Pour gagner en precision, relire chaque reponse en verifiant que les notions, les citations et les termes litteraires sont exacts.",
    },
    {
        "keywords": ["syntaxe", "phrase"],
        "point": "La syntaxe est indiquee comme un point a travailler.",
        "advice": "Pour ameliorer la syntaxe, privilegier des phrases plus courtes, verifier le verbe principal et relire a voix basse.",
    },
    {
        "keywords": ["orthographe", "accord"],
        "point": "L'orthographe est signalee comme un axe de vigilance.",
        "advice": "Pour renforcer l'orthographe, consacrer une relecture distincte aux accords, aux terminaisons verbales et aux accents.",
    },
    {
        "keywords": ["structure", "organiser", "organisation", "plan"],
        "point": "Une structuration plus nette des idees est attendue.",
        "advice": "Pour structurer le devoir, annoncer clairement l'idee du paragraphe, developper un seul argument, puis conclure avant de passer au suivant.",
    },
    {
        "keywords": ["justifier", "justification", "citation", "preuve"],
        "point": "La justification des arguments est explicitement attendue.",
        "advice": "Pour mieux justifier, associer chaque affirmation a une citation courte ou a un exemple precis, puis commenter ce choix.",
    },
    {
        "keywords": ["oral", "confiance", "voix", "prise de parole"],
        "point": "Un travail sur l'oral est signale.",
        "advice": "Pour l'oral, preparer un plan tres bref, s'entrainer a formuler la premiere phrase et travailler une diction posee.",
    },
    {
        "keywords": ["methode", "consigne"],
        "point": "La methode ou le respect de la consigne est mentionne comme point de vigilance.",
        "advice": "Pour consolider la methode, commencer par reformuler la consigne, reperer l'exercice attendu et verifier que chaque partie y repond.",
    },
    {
        "keywords": ["rigueur", "serieux", "regularite"],
        "point": "La rigueur ou la regularite est mentionnee comme point de vigilance.",
        "advice": "Pour gagner en rigueur, prevoir une relecture methodique: consigne, plan, exemples, puis correction de la langue.",
    },
    {
        "keywords": ["vocabulaire", "lexique"],
        "point": "Le vocabulaire est indique comme un axe de progression.",
        "advice": "Pour enrichir le vocabulaire, tenir une courte liste de termes litteraires et les reutiliser dans les analyses.",
    },
]


def normalize_text(value):
    normalized = unicodedata.normalize("NFKD", str(value or "").lower())
    return "".join(character for character in normalized if not unicodedata.combining(character))


def contains_any(text, terms):
    return any(term in text for term in terms)


def text_segments(text):
    normalized = normalize_text(text)
    return [
        segment.strip()
        for segment in re.split(r"[,.;:!?]|\bmais\b|\bcependant\b|\btoutefois\b|\ben revanche\b", normalized)
        if segment.strip()
    ]


def rule_matches(text, keywords, markers, forbidden_markers=None):
    forbidden_markers = forbidden_markers or []
    return any(
        contains_any(segment, keywords)
        and contains_any(segment, markers)
        and not contains_any(segment, forbidden_markers)
        for segment in text_segments(text)
    )


def unique_items(items):
    return list(dict.fromkeys(items))


def detect_positive_points(text):
    return [
        rule["label"]
        for rule in POSITIVE_RULES
        if rule_matches(text, rule["keywords"], POSITIVE_MARKERS, NEGATIVE_MARKERS)
    ]


def matching_improvement_rules(text):
    return [
        rule
        for rule in IMPROVEMENT_RULES
        if rule_matches(text, rule["keywords"], IMPROVEMENT_MARKERS)
    ]


def detect_improvement_points(text):
    return [rule["point"] for rule in matching_improvement_rules(text)]


def detect_concrete_advice(text):
    return [rule["advice"] for rule in matching_improvement_rules(text)]


def build_grounded_opinion(strengths, vigilance_points, advice):
    has_strengths = strengths and strengths != [NO_EXPLICIT_STRENGTH]
    has_vigilance = vigilance_points and vigilance_points != [NO_EXPLICIT_VIGILANCE]
    has_advice = advice and advice != [NO_EXPLICIT_ADVICE]

    if has_strengths and has_vigilance:
        return (
            f"Les appreciations saisies font ressortir un point d'appui: {strengths[0]} "
            f"Elles indiquent aussi un axe de travail: {vigilance_points[0]} "
            f"Le conseil prioritaire est le suivant: {advice[0] if has_advice else NO_EXPLICIT_ADVICE}"
        )
    if has_strengths:
        return (
            f"Les appreciations saisies soulignent clairement ce point d'appui: {strengths[0]} "
            "Aucun point de vigilance explicite n'y est formule."
        )
    if has_vigilance:
        return (
            f"Les appreciations saisies indiquent un axe de travail: {vigilance_points[0]} "
            f"Le conseil prioritaire est le suivant: {advice[0] if has_advice else NO_EXPLICIT_ADVICE}"
        )
    return "Les appreciations saisies ne contiennent pas encore d'indications qualitatives assez explicites pour etablir une synthese fiable."


def summarize_student(student, evaluations):
    empty_trimester_averages = {str(trimester): None for trimester in range(1, 4)}
    if not evaluations:
        return {
            "student": student,
            "stats": {
                "evaluations_count": 0,
                "average": None,
                "written_average": None,
                "oral_average": None,
                "trimester_averages": empty_trimester_averages,
            },
            "strengths": [NO_EXPLICIT_STRENGTH],
            "weaknesses": [NO_EXPLICIT_VIGILANCE],
            "improvements": [NO_EXPLICIT_ADVICE],
            "general_opinion": "Synthese indisponible tant qu'aucune evaluation n'a ete ajoutee.",
        }

    normalized_scores = [score_percent(item) for item in evaluations]
    written_scores = [score_percent(item) for item in evaluations if item["evaluation_type"] == "ecrit"]
    oral_scores = [score_percent(item) for item in evaluations if item["evaluation_type"] == "oral"]
    strengths = []
    weaknesses = []
    improvements = []
    global_average = mean(normalized_scores)
    written_average = mean(written_scores)
    oral_average = mean(oral_scores)
    trimester_averages = {
        str(trimester): mean([score_percent(item) for item in evaluations if int(item.get("trimester") or 1) == trimester])
        for trimester in range(1, 4)
    }

    for evaluation in evaluations:
        strengths.extend(detect_positive_points(evaluation["appreciation"]))
        weaknesses.extend(detect_improvement_points(evaluation["appreciation"]))
        improvements.extend(detect_concrete_advice(evaluation["appreciation"]))

    if not strengths:
        strengths.append(NO_EXPLICIT_STRENGTH)
    if not weaknesses:
        weaknesses.append(NO_EXPLICIT_VIGILANCE)
    if not improvements:
        improvements.append(NO_EXPLICIT_ADVICE)

    strengths = unique_items(strengths)[:4]
    weaknesses = unique_items(weaknesses)[:4]
    improvements = unique_items(improvements)[:4]

    opinion = build_grounded_opinion(strengths, weaknesses, improvements)

    return {
        "student": student,
        "stats": {
            "evaluations_count": len(evaluations),
            "average": global_average,
            "written_average": written_average,
            "oral_average": oral_average,
            "trimester_averages": trimester_averages,
        },
        "strengths": strengths,
        "weaknesses": weaknesses,
        "improvements": improvements,
        "general_opinion": opinion,
    }


def summarize_class():
    students = list_students()
    evaluations = list_evaluations()
    by_student = {}
    for evaluation in evaluations:
        by_student.setdefault(evaluation["student_id"], []).append(evaluation)
    student_summaries = [summarize_student(student, by_student.get(student["id"], [])) for student in students]
    averages = [summary["stats"]["average"] for summary in student_summaries if summary["stats"]["average"] is not None]
    class_average = mean(averages)
    trimester_averages = {
        str(trimester): mean([
            summary["stats"]["trimester_averages"][str(trimester)]
            for summary in student_summaries
            if summary["stats"]["trimester_averages"][str(trimester)] is not None
        ])
        for trimester in range(1, 4)
    }
    strengths_counter = {}
    improvements_counter = {}
    for summary in student_summaries:
        for item in summary["strengths"]:
            if item != NO_EXPLICIT_STRENGTH:
                strengths_counter[item] = strengths_counter.get(item, 0) + 1
        for item in summary["improvements"]:
            if item != NO_EXPLICIT_ADVICE:
                improvements_counter[item] = improvements_counter.get(item, 0) + 1
    top_strengths = sorted(strengths_counter, key=strengths_counter.get, reverse=True)[:5]
    top_improvements = sorted(improvements_counter, key=improvements_counter.get, reverse=True)[:5]
    return {
        "students_count": len(students),
        "evaluations_count": len(evaluations),
        "class_average": class_average,
        "trimester_averages": trimester_averages,
        "top_strengths": top_strengths or [NO_CLASS_STRENGTH_TREND],
        "top_improvements": top_improvements or [NO_CLASS_ADVICE_TREND],
        "student_summaries": student_summaries,
    }


def public_class_summary():
    summary = summarize_class()
    top_strengths = [item for item in summary["top_strengths"] if item != NO_CLASS_STRENGTH_TREND]
    top_improvements = [item for item in summary["top_improvements"] if item != NO_CLASS_ADVICE_TREND]
    if summary["evaluations_count"] == 0:
        general_opinion = "La synthese de classe sera plus parlante apres quelques evaluations supplementaires."
    elif top_strengths and top_improvements:
        general_opinion = (
            f"Les appreciations de la classe font ressortir ce point d'appui: {top_strengths[0]} "
            f"Elles orientent le travail vers ce conseil prioritaire: {top_improvements[0]}"
        )
    elif top_strengths:
        general_opinion = (
            f"Les appreciations de la classe font ressortir ce point d'appui: {top_strengths[0]} "
            "Aucun axe de conseil recurrent n'est formule explicitement."
        )
    elif top_improvements:
        general_opinion = (
            "Les appreciations de la classe ne font pas encore ressortir de point d'appui recurrent explicite. "
            f"Elles orientent cependant le travail vers ce conseil prioritaire: {top_improvements[0]}"
        )
    else:
        general_opinion = "Les appreciations saisies ne contiennent pas encore de tendance qualitative assez explicite pour etablir une synthese de classe fiable."

    return {
        "students_count": summary["students_count"],
        "evaluations_count": summary["evaluations_count"],
        "class_average": summary["class_average"],
        "trimester_averages": summary["trimester_averages"],
        "top_strengths": summary["top_strengths"],
        "top_improvements": summary["top_improvements"],
        "general_opinion": general_opinion,
    }


def parse_body(handler):
    length = int(handler.headers.get("Content-Length", "0"))
    raw = handler.rfile.read(length) if length > 0 else b""
    try:
        return json.loads(raw.decode("utf-8")) if raw else {}
    except json.JSONDecodeError:
        raise ValueError("JSON invalide.")


def clean_text(value, max_length):
    text = str(value or "").strip()
    return text[:max_length]


def validate_evaluation_payload(payload):
    required_fields = [
        "title",
        "evaluation_type",
        "trimester",
        "subject_area",
        "evaluation_date",
        "score",
        "max_score",
        "appreciation",
    ]
    missing = [field for field in required_fields if payload.get(field) in (None, "")]
    if missing:
        raise ValueError(f"Champs manquants: {', '.join(missing)}.")
    evaluation_type = payload["evaluation_type"]
    if evaluation_type not in {"ecrit", "oral"}:
        raise ValueError("Type d'evaluation invalide.")
    trimester = int(payload["trimester"])
    if trimester not in {1, 2, 3}:
        raise ValueError("Trimestre invalide.")
    score = float(payload["score"])
    max_score = float(payload["max_score"])
    if score < 0 or max_score <= 0 or score > max_score:
        raise ValueError("La note doit etre comprise entre 0 et le bareme.")
    return {
        "title": clean_text(payload["title"], 160),
        "evaluation_type": evaluation_type,
        "trimester": trimester,
        "subject_area": clean_text(payload["subject_area"], 120),
        "evaluation_date": clean_text(payload["evaluation_date"], 20),
        "score": score,
        "max_score": max_score,
        "appreciation": clean_text(payload["appreciation"], 1200),
    }


def is_secure_request(handler):
    if COOKIE_SECURE in {"1", "true", "yes"}:
        return True
    if COOKIE_SECURE in {"0", "false", "no"}:
        return False
    return handler.headers.get("X-Forwarded-Proto", "http") == "https"


def session_cookie(token, handler, expires=True):
    secure = "; Secure" if is_secure_request(handler) else ""
    max_age = SESSION_DAYS * 24 * 60 * 60 if expires else 0
    value = token if expires else "deleted"
    return f"session_token={value}; HttpOnly; Path=/; Max-Age={max_age}; SameSite=Lax{secure}"


class PrototypeHandler(BaseHTTPRequestHandler):
    def _send_json(self, payload, status=HTTPStatus.OK, headers=None):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        if headers:
            for key, value in headers.items():
                self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path, content_type="text/html; charset=utf-8"):
        if not path.exists():
            return self.send_error(HTTPStatus.NOT_FOUND)
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "public, max-age=300")
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, markup, status=HTTPStatus.OK):
        body = markup.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "public, max-age=300")
        self.end_headers()
        self.wfile.write(body)

    def _get_session_user(self):
        cookie_header = self.headers.get("Cookie")
        if not cookie_header:
            return None
        cookie = SimpleCookie()
        cookie.load(cookie_header)
        token = cookie.get("session_token")
        if not token:
            return None
        conn = get_db()
        row = conn.execute(
            """
            SELECT u.*
            FROM sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.token = %s AND s.expires_at > %s
            """,
            (token.value, iso_now()),
        ).fetchone()
        conn.close()
        return row_to_dict(row) if row else None

    def _require_auth(self, role=None):
        user = self._get_session_user()
        if not user:
            self._send_json({"error": "Authentification requise."}, HTTPStatus.UNAUTHORIZED)
            return None
        allowed_roles = {role} if isinstance(role, str) else set(role or [])
        if allowed_roles and user["role"] not in allowed_roles:
            self._send_json({"error": "Acces non autorise."}, HTTPStatus.FORBIDDEN)
            return None
        return user

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/healthz":
            return self._send_json({"status": "ok"})
        if parsed.path == "/":
            return self._send_file(STATIC_DIR / "index.html")
        if parsed.path == "/mentions-legales":
            return self._send_html(render_mentions_legales())
        if parsed.path == "/confidentialite":
            return self._send_html(render_confidentialite())
        if parsed.path == "/cookies":
            return self._send_html(render_cookies())
        if parsed.path == "/accessibilite":
            return self._send_html(render_accessibilite())
        if parsed.path == "/styles.css":
            return self._send_file(STATIC_DIR / "styles.css", "text/css; charset=utf-8")
        if parsed.path == "/app.js":
            return self._send_file(STATIC_DIR / "app.js", "application/javascript; charset=utf-8")
        if parsed.path == "/api/session":
            user = self._get_session_user()
            return self._send_json({"authenticated": bool(user), "user": user})
        if parsed.path == "/api/students":
            user = self._require_auth(STAFF_ROLES)
            if not user:
                return
            return self._send_json({"students": list_students()})
        if parsed.path == "/api/evaluations":
            user = self._require_auth()
            if not user:
                return
            params = parse_qs(parsed.query)
            student_id = user["id"]
            if user["role"] in STAFF_ROLES and "student_id" in params:
                student_id = int(params["student_id"][0])
            return self._send_json({"evaluations": list_evaluations(student_id)})
        if parsed.path.startswith("/api/student-summary/"):
            user = self._require_auth()
            if not user:
                return
            student_id = int(parsed.path.rsplit("/", 1)[-1])
            if user["role"] not in STAFF_ROLES and user["id"] != student_id:
                return self._send_json({"error": "Acces non autorise."}, HTTPStatus.FORBIDDEN)
            student = get_user_by_id(student_id)
            if not student or student["role"] != "student":
                return self._send_json({"error": "Eleve introuvable."}, HTTPStatus.NOT_FOUND)
            return self._send_json({"summary": summarize_student(student, list_evaluations(student_id))})
        if parsed.path == "/api/class-summary":
            user = self._require_auth()
            if not user:
                return
            if user["role"] in STAFF_ROLES:
                return self._send_json({"summary": summarize_class()})
            return self._send_json({"summary": public_class_summary()})
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_HEAD(self):
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/healthz", "/mentions-legales", "/confidentialite", "/cookies", "/accessibilite"}:
            self.send_response(HTTPStatus.OK)
            self.end_headers()
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self):
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/register":
                return self.handle_register()
            if parsed.path == "/api/login":
                return self.handle_login()
            if parsed.path == "/api/logout":
                return self.handle_logout()
            if parsed.path == "/api/evaluations":
                return self.handle_create_evaluation()
        except ValueError as exc:
            return self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except psycopg.IntegrityError:
            return self._send_json({"error": "Identifiant deja utilise."}, HTTPStatus.CONFLICT)
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_PUT(self):
        parsed = urlparse(self.path)
        try:
            if parsed.path.startswith("/api/evaluations/"):
                evaluation_id = int(parsed.path.rsplit("/", 1)[-1])
                return self.handle_update_evaluation(evaluation_id)
        except ValueError as exc:
            return self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        try:
            if parsed.path.startswith("/api/evaluations/"):
                evaluation_id = int(parsed.path.rsplit("/", 1)[-1])
                return self.handle_delete_evaluation(evaluation_id)
        except ValueError as exc:
            return self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        self.send_error(HTTPStatus.NOT_FOUND)

    def handle_register(self):
        payload = parse_body(self)
        username = clean_text(payload.get("username"), 80).lower()
        full_name = clean_text(payload.get("full_name"), 120)
        password = str(payload.get("password") or "")
        if len(username) < 3 or len(password) < 8 or len(full_name) < 2:
            raise ValueError("Nom, identifiant ou mot de passe trop court.")
        with WRITE_LOCK:
            conn = get_db()
            try:
                conn.execute("BEGIN")
                conn.execute(
                    "INSERT INTO users (username, password, password_hash, full_name, role, created_at) VALUES (%s, '', %s, %s, 'student', %s)",
                    (username, hash_password(password), full_name, iso_now()),
                )
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()
        user = get_login_user(username)
        return self.create_session_response(row_to_dict(user), HTTPStatus.CREATED)

    def handle_login(self):
        payload = parse_body(self)
        username = clean_text(payload.get("username"), 80).lower()
        password = str(payload.get("password") or "")
        row = get_login_user(username)
        if not row or not verify_password(password, row["password_hash"] or row["password"]):
            return self._send_json({"error": "Identifiants invalides."}, HTTPStatus.UNAUTHORIZED)
        if row["password"] and not row["password_hash"]:
            with WRITE_LOCK:
                conn = get_db()
                conn.execute("UPDATE users SET password_hash = %s, password = '' WHERE id = %s", (hash_password(password), row["id"]))
                conn.close()
        return self.create_session_response(row_to_dict(row))

    def create_session_response(self, user, status=HTTPStatus.OK):
        token = secrets.token_urlsafe(32)
        expires_at = (utc_now() + timedelta(days=SESSION_DAYS)).isoformat()
        with WRITE_LOCK:
            conn = get_db()
            conn.execute(
                "INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (%s, %s, %s, %s)",
                (token, user["id"], iso_now(), expires_at),
            )
            conn.close()
        return self._send_json({"user": user}, status, headers={"Set-Cookie": session_cookie(token, self)})

    def handle_logout(self):
        cookie_header = self.headers.get("Cookie")
        if cookie_header:
            cookie = SimpleCookie()
            cookie.load(cookie_header)
            token = cookie.get("session_token")
            if token:
                with WRITE_LOCK:
                    conn = get_db()
                    conn.execute("DELETE FROM sessions WHERE token = %s", (token.value,))
                    conn.close()
        return self._send_json({"success": True}, headers={"Set-Cookie": session_cookie("", self, expires=False)})

    def handle_create_evaluation(self):
        user = self._require_auth()
        if not user:
            return
        payload = parse_body(self)
        student_id = int(payload.get("student_id")) if user["role"] in STAFF_ROLES else user["id"]
        data = validate_evaluation_payload(payload)
        student = get_user_by_id(student_id)
        if not student or student["role"] != "student":
            raise ValueError("Eleve introuvable.")
        with WRITE_LOCK:
            conn = get_db()
            try:
                conn.execute("BEGIN")
                conn.execute(
                    """
                    INSERT INTO evaluations (
                        student_id, title, evaluation_type, trimester, subject_area,
                        evaluation_date, score, max_score, appreciation, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        student_id,
                        data["title"],
                        data["evaluation_type"],
                        data["trimester"],
                        data["subject_area"],
                        data["evaluation_date"],
                        data["score"],
                        data["max_score"],
                        data["appreciation"],
                        iso_now()
                    ),
                )
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()
        return self._send_json({"success": True}, HTTPStatus.CREATED)

    def handle_update_evaluation(self, evaluation_id):
        user = self._require_auth()
        if not user:
            return
        evaluation = get_evaluation_by_id(evaluation_id)
        if not evaluation:
            return self._send_json({"error": "Evaluation introuvable."}, HTTPStatus.NOT_FOUND)
        if user["role"] not in STAFF_ROLES and evaluation["student_id"] != user["id"]:
            return self._send_json({"error": "Acces non autorise."}, HTTPStatus.FORBIDDEN)
        data = validate_evaluation_payload(parse_body(self))
        with WRITE_LOCK:
            conn = get_db()
            try:
                conn.execute("BEGIN")
                conn.execute(
                    """
                    UPDATE evaluations
                    SET title = %s,
                        evaluation_type = %s,
                        trimester = %s,
                        subject_area = %s,
                        evaluation_date = %s,
                        score = %s,
                        max_score = %s,
                        appreciation = %s
                    WHERE id = %s
                    """,
                    (
                        data["title"],
                        data["evaluation_type"],
                        data["trimester"],
                        data["subject_area"],
                        data["evaluation_date"],
                        data["score"],
                        data["max_score"],
                        data["appreciation"],
                        evaluation_id,
                    ),
                )
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()
        return self._send_json({"success": True})

    def handle_delete_evaluation(self, evaluation_id):
        user = self._require_auth()
        if not user:
            return
        evaluation = get_evaluation_by_id(evaluation_id)
        if not evaluation:
            return self._send_json({"error": "Evaluation introuvable."}, HTTPStatus.NOT_FOUND)
        if user["role"] not in STAFF_ROLES and evaluation["student_id"] != user["id"]:
            return self._send_json({"error": "Acces non autorise."}, HTTPStatus.FORBIDDEN)
        with WRITE_LOCK:
            conn = get_db()
            conn.execute("DELETE FROM evaluations WHERE id = %s", (evaluation_id,))
            conn.close()
        return self._send_json({"success": True})


if __name__ == "__main__":
    init_db()
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer((host, port), PrototypeHandler)
    print(f"Application disponible sur http://{host}:{port}")
    server.serve_forever()
