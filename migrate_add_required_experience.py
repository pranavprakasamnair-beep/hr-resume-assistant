"""
One-time migration: adds a `required_experience` column to the EXISTING
jobs table, without touching any other data. Existing jobs get 'Any'
(meaning no experience requirement), so nothing breaks for jobs posted
before this feature existed.

Run this once with:  python3 migrate_add_required_experience.py
Safe to re-run: if the column already exists, it does nothing.
"""

import sqlite3

DB_PATH = "hr.db"


def main():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    existing_cols = [row[1] for row in c.execute("PRAGMA table_info(jobs)").fetchall()]

    if "required_experience" in existing_cols:
        print("required_experience column already exists -- nothing to do.")
        conn.close()
        return

    c.execute("ALTER TABLE jobs ADD COLUMN required_experience TEXT DEFAULT 'Any'")
    c.execute("UPDATE jobs SET required_experience = 'Any' WHERE required_experience IS NULL")

    conn.commit()
    conn.close()
    print("Migration complete. Added required_experience column (existing jobs set to 'Any').")


if __name__ == "__main__":
    main()
