import os
import re
import sqlite3
from pathlib import Path

import psycopg
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.rows import dict_row

BASE_DIR = Path(__file__).resolve().parent
SQLITE_PATH = Path(os.environ.get("PROTOTYPE_DB_PATH", BASE_DIR / "prototype.sqlite3"))
DATABASE_URL = os.environ.get("DATABASE_URL")
DATABASE_SSLMODE = os.environ.get("DATABASE_SSLMODE")
DATABASE_SCHEMA = os.environ.get("DATABASE_SCHEMA", "public")
if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", DATABASE_SCHEMA):
    raise RuntimeError("DATABASE_SCHEMA doit etre un identifiant PostgreSQL simple.")


def require_database_url():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL doit pointer vers la base PostgreSQL cible.")


def database_conninfo():
    params = conninfo_to_dict(DATABASE_URL)
    host = params.get("host", "")
    if "sslmode" not in params:
        params["sslmode"] = DATABASE_SSLMODE or ("require" if "supabase.co" in host else "prefer")
    if "connect_timeout" not in params:
        params["connect_timeout"] = "10"
    if "application_name" not in params:
        params["application_name"] = "synthese-francais-migration"
    if DATABASE_SCHEMA != "public":
        params["options"] = f"-c search_path={DATABASE_SCHEMA},public"
    return make_conninfo(**params)


def sqlite_rows(conn, table, columns):
    column_list = ", ".join(columns)
    return conn.execute(f"SELECT {column_list} FROM {table} ORDER BY 1").fetchall()


def sqlite_table_columns(conn, table):
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def reset_user_sequence(pg_conn):
    pg_conn.execute(
        """
        SELECT setval(
            pg_get_serial_sequence('users', 'id'),
            COALESCE((SELECT MAX(id) FROM users), 1),
            (SELECT MAX(id) FROM users) IS NOT NULL
        )
        """
    )


def reset_evaluation_sequence(pg_conn):
    pg_conn.execute(
        """
        SELECT setval(
            pg_get_serial_sequence('evaluations', 'id'),
            COALESCE((SELECT MAX(id) FROM evaluations), 1),
            (SELECT MAX(id) FROM evaluations) IS NOT NULL
        )
        """
    )


def migrate():
    require_database_url()
    if not SQLITE_PATH.exists():
        raise FileNotFoundError(f"Base SQLite introuvable: {SQLITE_PATH}")

    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_conn.row_factory = sqlite3.Row
    pg_conn = psycopg.connect(database_conninfo(), row_factory=dict_row, autocommit=False, prepare_threshold=None)

    try:
        if DATABASE_SCHEMA != "public":
            pg_conn.execute(f"CREATE SCHEMA IF NOT EXISTS {DATABASE_SCHEMA}")
        user_columns = ["id", "username", "password", "password_hash", "full_name", "role", "created_at"]
        sqlite_evaluation_columns = sqlite_table_columns(sqlite_conn, "evaluations")
        evaluation_columns = [
            "id",
            "student_id",
            "title",
            "evaluation_type",
            *([] if "trimester" not in sqlite_evaluation_columns else ["trimester"]),
            "subject_area",
            "evaluation_date",
            "score",
            "max_score",
            "appreciation",
            "created_at",
        ]
        session_columns = ["token", "user_id", "created_at", "expires_at"]

        for row in sqlite_rows(sqlite_conn, "users", user_columns):
            pg_conn.execute(
                """
                INSERT INTO users (id, username, password, password_hash, full_name, role, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    username = EXCLUDED.username,
                    password = EXCLUDED.password,
                    password_hash = EXCLUDED.password_hash,
                    full_name = EXCLUDED.full_name,
                    role = EXCLUDED.role,
                    created_at = EXCLUDED.created_at
                """,
                tuple(row[column] for column in user_columns),
            )

        for row in sqlite_rows(sqlite_conn, "evaluations", evaluation_columns):
            pg_conn.execute(
                """
                INSERT INTO evaluations (
                    id, student_id, title, evaluation_type, trimester, subject_area,
                    evaluation_date, score, max_score, appreciation, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    student_id = EXCLUDED.student_id,
                    title = EXCLUDED.title,
                    evaluation_type = EXCLUDED.evaluation_type,
                    trimester = EXCLUDED.trimester,
                    subject_area = EXCLUDED.subject_area,
                    evaluation_date = EXCLUDED.evaluation_date,
                    score = EXCLUDED.score,
                    max_score = EXCLUDED.max_score,
                    appreciation = EXCLUDED.appreciation,
                    created_at = EXCLUDED.created_at
                """,
                (
                    row["id"],
                    row["student_id"],
                    row["title"],
                    row["evaluation_type"],
                    row["trimester"] if "trimester" in row.keys() else 1,
                    row["subject_area"],
                    row["evaluation_date"],
                    row["score"],
                    row["max_score"],
                    row["appreciation"],
                    row["created_at"],
                ),
            )

        for row in sqlite_rows(sqlite_conn, "sessions", session_columns):
            pg_conn.execute(
                """
                INSERT INTO sessions (token, user_id, created_at, expires_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (token) DO UPDATE SET
                    user_id = EXCLUDED.user_id,
                    created_at = EXCLUDED.created_at,
                    expires_at = EXCLUDED.expires_at
                """,
                tuple(row[column] for column in session_columns),
            )

        reset_user_sequence(pg_conn)
        reset_evaluation_sequence(pg_conn)
        pg_conn.commit()
    except Exception:
        pg_conn.rollback()
        raise
    finally:
        sqlite_conn.close()
        pg_conn.close()


if __name__ == "__main__":
    migrate()
    print("Migration SQLite vers PostgreSQL terminee.")
