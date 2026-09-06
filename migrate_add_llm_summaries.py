"""
One-time migration: adds the `llm_summaries` table to an EXISTING hr.db,
without touching any other data. This table caches generated AI evidence
summaries per (job_id, resume_id) pair so we don't re-call the LLM gateway
every time a recruiter reopens the shortlist.

Run this once with:  python3 migrate_add_llm_summaries.py
Safe to re-run: if the table already exists, it does nothing.
"""

import sqlite3

DB_PATH = "hr.db"


def main():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    existing = c.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='llm_summaries'"
    ).fetchone()

    if existing:
        print("llm_summaries table already exists -- nothing to do.")
        conn.close()
        return

    c.execute("""
        CREATE TABLE llm_summaries (
            job_id TEXT,
            resume_id INTEGER,
            summary_text TEXT,
            generated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (job_id, resume_id)
        )
    """)

    conn.commit()
    conn.close()
    print("Migration complete. Added llm_summaries table.")


if __name__ == "__main__":
    main()
