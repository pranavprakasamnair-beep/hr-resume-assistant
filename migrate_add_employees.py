"""
One-time migration: adds the `employees` table (for recruiter login) to an
EXISTING hr.db, without touching your existing jobs/resumes/actions data.

Run this once with:  python3 migrate_add_employees.py

Safe to re-run: if the employees table already exists, it does nothing.
"""

import sqlite3
from auth import hash_password

DB_PATH = "hr.db"

DEFAULT_EMPLOYEES = [
    ("EMP001", "Alex Recruiter", "password123"),
    ("EMP002", "Priya Sharma", "hrpass456"),
    ("EMP003", "Jordan Lee", "changeme789"),
]


def main():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    existing = c.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='employees'"
    ).fetchone()

    if existing:
        print("employees table already exists -- nothing to do.")
        conn.close()
        return

    c.execute("""
        CREATE TABLE employees (
            employee_id TEXT PRIMARY KEY,
            name TEXT,
            password_hash TEXT,
            salt TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    for emp_id, name, plain_password in DEFAULT_EMPLOYEES:
        pw_hash, salt = hash_password(plain_password)
        c.execute(
            "INSERT INTO employees (employee_id, name, password_hash, salt) VALUES (?, ?, ?, ?)",
            (emp_id, name, pw_hash, salt),
        )

    conn.commit()
    conn.close()

    print("Migration complete. Added employees table with 3 demo recruiter logins:")
    for emp_id, name, plain_password in DEFAULT_EMPLOYEES:
        print(f"  {emp_id} / {plain_password}  ({name})")


if __name__ == "__main__":
    main()
