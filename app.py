import json
import os
import secrets
import sqlite3
from datetime import datetime
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("DATA_DIR", BASE_DIR))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = Path(os.environ.get("PROTOTYPE_DB_PATH", DATA_DIR / "prototype.sqlite3"))
STATIC_DIR = BASE_DIR / "static"
SESSIONS = {}


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('teacher', 'student'))
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS evaluations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            evaluation_type TEXT NOT NULL CHECK(evaluation_type IN ('ecrit', 'oral')),
            subject_area TEXT NOT NULL,
            evaluation_date TEXT NOT NULL,
            score REAL NOT NULL,
            max_score REAL NOT NULL,
            appreciation TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(student_id) REFERENCES users(id)
        )
        """
    )
    cur.execute("SELECT COUNT(*) FROM users")
    if cur.fetchone()[0] == 0:
        cur.executemany(
            "INSERT INTO users (username, password, full_name, role) VALUES (?, ?, ?, ?)",
            [
                ("prof.francais", "demo123", "Mme Martin", "teacher"),
                ("emma.dupont", "eleve123", "Emma Dupont", "student"),
                ("leo.bernard", "eleve123", "Leo Bernard", "student"),
                ("jade.moreau", "eleve123", "Jade Moreau", "student"),
            ],
        )
    conn.commit()
    conn.close()


def row_to_dict(row):
    return {key: row[key] for key in row.keys()}


def get_user_by_id(user_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row_to_dict(row) if row else None


def list_students():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, username, full_name FROM users WHERE role = 'student' ORDER BY full_name")
    rows = [row_to_dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


def list_evaluations(student_id=None):
    conn = get_db()
    cur = conn.cursor()
    query = """
        SELECT e.*, u.full_name AS student_name
        FROM evaluations e
        JOIN users u ON u.id = e.student_id
    """
    params = []
    if student_id is not None:
        query += " WHERE e.student_id = ?"
        params.append(student_id)
    query += " ORDER BY e.evaluation_date DESC, e.created_at DESC"
    cur.execute(query, params)
    rows = [row_to_dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


def mean(values):
    return round(sum(values) / len(values), 2) if values else None


def score_percent(evaluation):
    return (evaluation["score"] / evaluation["max_score"]) * 20 if evaluation["max_score"] else 0


def detect_positive_points(text):
    lowered = text.lower()
    mapping = {
        "analyse": "bonne capacite d'analyse",
        "argument": "argumentation solide",
        "oral": "aisance a l'oral",
        "ecrit": "maitrise de l'ecrit",
        "lecture": "bonne comprehension des textes",
        "style": "expression ecrite convaincante",
        "rigueur": "travail rigoureux",
    }
    return [label for keyword, label in mapping.items() if keyword in lowered]


def detect_improvement_points(text):
    lowered = text.lower()
    mapping = {
        "approfond": "approfondir les analyses",
        "precision": "gagner en precision",
        "syntaxe": "ameliorer la syntaxe",
        "orthographe": "renforcer l'orthographe",
        "structure": "mieux structurer les idees",
        "justifier": "mieux justifier les arguments",
        "confiance": "prendre davantage confiance a l'oral",
    }
    return [label for keyword, label in mapping.items() if keyword in lowered]


def summarize_student(student, evaluations):
    if not evaluations:
        return {
            "student": student,
            "stats": {"evaluations_count": 0, "average": None, "written_average": None, "oral_average": None},
            "strengths": ["Aucune donnee pour le moment."],
            "weaknesses": ["Aucune faiblesse detectee sans evaluations."],
            "improvements": ["Saisir les premieres evaluations pour obtenir une synthese."],
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

    if global_average is not None and global_average >= 13:
        strengths.append("Resultats globalement solides en francais.")
    elif global_average is not None and global_average < 10:
        weaknesses.append("Moyenne generale fragile sur les evaluations saisies.")

    if written_average is not None:
        if written_average >= 12:
            strengths.append("Bonne maitrise des evaluations ecrites.")
        elif written_average < 10:
            weaknesses.append("Des difficultes apparaissent a l'ecrit.")
            improvements.append("Travailler la methode de redaction et l'organisation des idees.")

    if oral_average is not None:
        if oral_average >= 14:
            strengths.append("Aisance remarquable lors des prises de parole.")
        elif oral_average < 10:
            weaknesses.append("Les performances orales restent a consolider.")
            improvements.append("S'entrainer a l'oral avec des prises de parole plus regulieres.")

    for evaluation in evaluations:
        strengths.extend(detect_positive_points(evaluation["appreciation"]))
        improvements.extend(detect_improvement_points(evaluation["appreciation"]))

    if not strengths:
        strengths.append("Des points positifs existent mais demandent encore a se confirmer.")
    if not weaknesses:
        weaknesses.append("Pas de faiblesse majeure recurrente sur les donnees actuelles.")
    if not improvements:
        improvements.append("Poursuivre les efforts de regularite et de precision.")

    strengths = list(dict.fromkeys(strengths))[:4]
    weaknesses = list(dict.fromkeys(weaknesses))[:4]
    improvements = list(dict.fromkeys(improvements))[:4]

    if global_average is None:
        opinion = "Les donnees sont encore insuffisantes pour une tendance generale."
    elif global_average >= 15:
        opinion = "Avis general tres positif: eleve autonome, regulier et convaincant."
    elif global_average >= 12:
        opinion = "Avis general positif: ensemble serieux avec une progression encourageante."
    elif global_average >= 10:
        opinion = "Avis general nuance: bases presentes, mais une progression reste attendue."
    else:
        opinion = "Avis general reserve: un accompagnement plus soutenu semble necessaire."

    return {
        "student": student,
        "stats": {
            "evaluations_count": len(evaluations),
            "average": global_average,
            "written_average": written_average,
            "oral_average": oral_average,
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
    strengths_counter = {}
    improvements_counter = {}
    for summary in student_summaries:
        for item in summary["strengths"]:
            strengths_counter[item] = strengths_counter.get(item, 0) + 1
        for item in summary["improvements"]:
            improvements_counter[item] = improvements_counter.get(item, 0) + 1
    top_strengths = sorted(strengths_counter, key=strengths_counter.get, reverse=True)[:5]
    top_improvements = sorted(improvements_counter, key=improvements_counter.get, reverse=True)[:5]
    return {
        "students_count": len(students),
        "evaluations_count": len(evaluations),
        "class_average": class_average,
        "top_strengths": top_strengths or ["Aucune tendance forte pour le moment."],
        "top_improvements": top_improvements or ["Aucune tendance forte pour le moment."],
        "student_summaries": student_summaries,
    }


def public_class_summary():
    summary = summarize_class()
    class_average = summary["class_average"]
    if class_average is None:
        general_opinion = "La synthese de classe sera plus parlante apres quelques evaluations supplementaires."
    elif class_average >= 14:
        general_opinion = "La dynamique de classe est tres positive avec un niveau d'ensemble solide."
    elif class_average >= 12:
        general_opinion = "La classe montre des acquis encourageants et une base de travail serieuse."
    elif class_average >= 10:
        general_opinion = "Le niveau de classe reste heterogene, avec une marge de progression identifiable."
    else:
        general_opinion = "La classe semble avoir besoin d'un accompagnement plus soutenu sur plusieurs competences."

    return {
        "students_count": summary["students_count"],
        "evaluations_count": summary["evaluations_count"],
        "class_average": summary["class_average"],
        "top_strengths": summary["top_strengths"],
        "top_improvements": summary["top_improvements"],
        "general_opinion": general_opinion,
    }


def parse_body(handler):
    length = int(handler.headers.get("Content-Length", "0"))
    raw = handler.rfile.read(length) if length > 0 else b""
    return json.loads(raw.decode("utf-8")) if raw else {}


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
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
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
        session = SESSIONS.get(token.value)
        return get_user_by_id(session["user_id"]) if session else None

    def _require_auth(self, role=None):
        user = self._get_session_user()
        if not user:
            self._send_json({"error": "Authentification requise."}, HTTPStatus.UNAUTHORIZED)
            return None
        if role and user["role"] != role:
            self._send_json({"error": "Accès non autorisé."}, HTTPStatus.FORBIDDEN)
            return None
        return user

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/healthz":
            return self._send_json({"status": "ok"})
        if parsed.path == "/":
            return self._send_file(STATIC_DIR / "index.html")
        if parsed.path == "/styles.css":
            return self._send_file(STATIC_DIR / "styles.css", "text/css; charset=utf-8")
        if parsed.path == "/app.js":
            return self._send_file(STATIC_DIR / "app.js", "application/javascript; charset=utf-8")
        if parsed.path == "/api/session":
            user = self._get_session_user()
            return self._send_json({"authenticated": bool(user), "user": user})
        if parsed.path == "/api/students":
            user = self._require_auth("teacher")
            if not user:
                return
            return self._send_json({"students": list_students()})
        if parsed.path == "/api/evaluations":
            user = self._require_auth()
            if not user:
                return
            params = parse_qs(parsed.query)
            student_id = user["id"]
            if user["role"] == "teacher" and "student_id" in params:
                student_id = int(params["student_id"][0])
            return self._send_json({"evaluations": list_evaluations(student_id)})
        if parsed.path.startswith("/api/student-summary/"):
            user = self._require_auth()
            if not user:
                return
            student_id = int(parsed.path.rsplit("/", 1)[-1])
            if user["role"] != "teacher" and user["id"] != student_id:
                return self._send_json({"error": "Accès non autorisé."}, HTTPStatus.FORBIDDEN)
            student = get_user_by_id(student_id)
            if not student or student["role"] != "student":
                return self._send_json({"error": "Élève introuvable."}, HTTPStatus.NOT_FOUND)
            return self._send_json({"summary": summarize_student(student, list_evaluations(student_id))})
        if parsed.path == "/api/class-summary":
            user = self._require_auth()
            if not user:
                return
            if user["role"] == "teacher":
                return self._send_json({"summary": summarize_class()})
            return self._send_json({"summary": public_class_summary()})
        self.send_error(HTTPStatus.NOT_FOUND)
    def do_HEAD(self):
        parsed = urlparse(self.path)

        if parsed.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            return

        if parsed.path == "/healthz":
            self.send_response(200)
            self.end_headers()
            return

        self.send_error(HTTPStatus.NOT_FOUND)
    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/login":
            payload = parse_body(self)
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT * FROM users WHERE username = ? AND password = ?", (payload.get("username", "").strip(), payload.get("password", "").strip()))
            row = cur.fetchone()
            conn.close()
            if not row:
                return self._send_json({"error": "Identifiants invalides."}, HTTPStatus.UNAUTHORIZED)
            user = row_to_dict(row)
            token = secrets.token_hex(16)
            SESSIONS[token] = {"user_id": user["id"], "created_at": datetime.utcnow().isoformat()}
            return self._send_json({"user": user}, headers={"Set-Cookie": f"session_token={token}; HttpOnly; Path=/; SameSite=Lax"})
        if parsed.path == "/api/logout":
            cookie_header = self.headers.get("Cookie")
            if cookie_header:
                cookie = SimpleCookie()
                cookie.load(cookie_header)
                token = cookie.get("session_token")
                if token:
                    SESSIONS.pop(token.value, None)
            return self._send_json({"success": True}, headers={"Set-Cookie": "session_token=deleted; HttpOnly; Path=/; Max-Age=0; SameSite=Lax"})
        if parsed.path == "/api/evaluations":
            user = self._require_auth()
            if not user:
                return
            payload = parse_body(self)
            student_id = int(payload.get("student_id")) if user["role"] == "teacher" else user["id"]
            required_fields = ["title", "evaluation_type", "subject_area", "evaluation_date", "score", "max_score", "appreciation"]
            missing = [field for field in required_fields if payload.get(field) in (None, "")]
            if missing:
                return self._send_json({"error": f"Champs manquants: {', '.join(missing)}."}, HTTPStatus.BAD_REQUEST)
            conn = get_db()
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO evaluations (
                    student_id, title, evaluation_type, subject_area,
                    evaluation_date, score, max_score, appreciation, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    student_id,
                    payload["title"].strip(),
                    payload["evaluation_type"],
                    payload["subject_area"].strip(),
                    payload["evaluation_date"],
                    float(payload["score"]),
                    float(payload["max_score"]),
                    payload["appreciation"].strip(),
                    datetime.utcnow().isoformat(),
                ),
            )
            conn.commit()
            conn.close()
            return self._send_json({"success": True}, HTTPStatus.CREATED)
        self.send_error(HTTPStatus.NOT_FOUND)


if __name__ == "__main__":
    init_db()
    host = "0.0.0.0"
    port = int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer((host, port), PrototypeHandler)
    print(f"Prototype disponible sur http://{host}:{port}")
    server.serve_forever()
