import sqlite3

DB_NAME = "app.db"


def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def create_tables():
    conn = get_db_connection()
    cursor = conn.cursor()

    # ---------------- RESPONSIBLE ADULT ----------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS responsible_adult (
            adult_id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            failed_attempts INTEGER DEFAULT 0,
            lock_until DATETIME
        )
    """)

    # ---------------- CHILD ----------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS child (
            child_id INTEGER PRIMARY KEY AUTOINCREMENT,
            adult_id INTEGER NOT NULL,
            child_name TEXT NOT NULL,
            gender TEXT NOT NULL,
            age INTEGER NOT NULL,
            grade INTEGER NOT NULL,

            FOREIGN KEY (adult_id)
                REFERENCES responsible_adult (adult_id)
                ON DELETE CASCADE,

            UNIQUE (adult_id, child_name)
        )
    """)

    # ---------------- ACTIVITY RESULTS ----------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS activity_results (
            result_id INTEGER PRIMARY KEY AUTOINCREMENT,
            child_id INTEGER NOT NULL,
            activity_id INTEGER NOT NULL,
            given_answer TEXT,
            is_correct INTEGER NOT NULL,
            score INTEGER NOT NULL,
            is_completed INTEGER NOT NULL,
            time_taken_seconds INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (child_id)
                REFERENCES child (child_id)
                ON DELETE CASCADE
        )
    """)

    # ---------------- FINAL REPORT ----------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS final_report (
            report_id INTEGER PRIMARY KEY AUTOINCREMENT,
            adult_id INTEGER NOT NULL,
            child_id INTEGER NOT NULL,
            report_description TEXT,
            report_date DATETIME DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (adult_id)
                REFERENCES responsible_adult (adult_id)
                ON DELETE CASCADE,

            FOREIGN KEY (child_id)
                REFERENCES child (child_id)
                ON DELETE CASCADE
        )
    """)

    # ---------------- ML MODEL ----------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ml_model (
            model_id TEXT PRIMARY KEY,
            model_name TEXT NOT NULL
        )
    """)

    # ---------------- ML PREDICTION RESULT ----------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ml_prediction_result (
            prediction_id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id INTEGER,
            model_id TEXT NOT NULL,
            child_id INTEGER NOT NULL,
            prediction_score REAL,
            risk_level TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (child_id)
                REFERENCES child (child_id)
                ON DELETE CASCADE,

            FOREIGN KEY (model_id)
                REFERENCES ml_model (model_id)
        )
    """)

    # ---------------- INSERT DUMMY ML MODEL ----------------
    cursor.execute("""
        INSERT OR IGNORE INTO ml_model (model_id, model_name)
        VALUES ('ML1', 'ActivityAnalysisModel')
    """)

    conn.commit()
    conn.close()


def save_activity_result(
    child_id,
    activity_id,
    given_answer,
    is_correct,
    score,
    is_completed,
    time_taken_seconds
):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO activity_results (
            child_id,
            activity_id,
            given_answer,
            is_correct,
            score,
            is_completed,
            time_taken_seconds
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        child_id,
        activity_id,
        given_answer,
        is_correct,
        score,
        is_completed,
        time_taken_seconds
    ))

    conn.commit()
    conn.close()


# 🔥 CREATE TABLES ON APP START
create_tables()