"""
STEP 1: Generate synthetic data.
Run this once with:  python3 generate_data.py
It creates a file called hr.db (a SQLite database) with:
  - 20 fake job descriptions
  - 500 fake resumes (some with protected info inserted, on purpose,
    to prove later that we redact it correctly)
"""

import sqlite3
import random
from faker import Faker
from skills_dictionary import SKILLS
from auth import hash_password

fake = Faker()
random.seed(42)

CERTS = ["PMP", "AWS Certified", "Scrum Master", "Google Data Analytics", "None"]

RELIGIONS = ["Christian", "Muslim", "Hindu", "Buddhist", "Atheist"]
GENDERS = ["Male", "Female", "Non-binary"]

JOB_TITLES = [
    "Data Analyst", "Backend Developer", "ML Engineer", "Project Manager",
    "Frontend Developer", "DevOps Engineer", "Business Analyst",
    "Data Scientist", "Full Stack Developer", "QA Engineer",
    "Product Manager", "Cloud Engineer", "AI Researcher", "UX Designer",
    "Database Administrator", "Marketing Analyst", "HR Coordinator",
    "Systems Engineer", "Security Analyst", "Technical Writer",
]


EXPERIENCE_BANDS = ["Any", "0-1", "1-3", "3-5", "5-8", "8+"]


def make_job(job_id, title):
    required = random.sample(SKILLS, k=4)
    preferred = random.sample([s for s in SKILLS if s not in required], k=3)
    return {
        "job_id": job_id,
        "title": title,
        "required_skills": ", ".join(required),
        "preferred_skills": ", ".join(preferred),
        "required_experience": random.choice(EXPERIENCE_BANDS),
    }


def make_resume(resume_id, insert_protected_info):
    name = fake.name()
    email = fake.email()
    skills = random.sample(SKILLS, k=random.randint(3, 7))
    education = random.choice(["Bachelors", "Masters", "PhD", "Diploma"])
    exp_years = random.choice(["0-1", "1-3", "3-5", "5-8", "8+"])
    gap = random.choice(["None", "3-6 months", "1 year", "2+ years"])
    cert = random.choice(CERTS)
    project_keywords = ", ".join(random.sample(SKILLS, k=2))
    location = random.choice(["Remote", "Onsite", "Hybrid", ""])

    resume_text = (
        f"Candidate has experience in {', '.join(skills)}. "
        f"Education: {education}. Certifications: {cert}. "
        f"Worked on projects involving {project_keywords}."
    )

    # Deliberately insert protected attributes into ~15% of resumes,
    # written the way a real person might casually include them.
    # This is ONLY for testing that our redaction step removes them.
    if insert_protected_info:
        extra = (
            f" My name is {name}, I am {random.randint(22, 55)} years old, "
            f"{random.choice(GENDERS)}, and I am {random.choice(RELIGIONS)}."
        )
        resume_text += extra

    return {
        "resume_id": resume_id,
        "candidate_alias": f"CAN-{resume_id:04d}",
         "email": email,
        "resume_text": resume_text,
        "education_level": education,
        "experience_years_band": exp_years,
        "skills_list": ", ".join(skills),
        "certifications": cert,
        "project_keywords": project_keywords,
        "employment_gap_band": gap,
        "location_preference_optional": location,
    }


def main():
    conn = sqlite3.connect("hr.db")
    c = conn.cursor()

    c.execute("DROP TABLE IF EXISTS jobs")
    c.execute("DROP TABLE IF EXISTS resumes")
    c.execute("DROP TABLE IF EXISTS match_results")
    c.execute("DROP TABLE IF EXISTS recruiter_actions")
    c.execute("DROP TABLE IF EXISTS employees")

    c.execute("""
        CREATE TABLE jobs (
            job_id TEXT PRIMARY KEY,
            title TEXT,
            required_skills TEXT,
            preferred_skills TEXT,
            required_experience TEXT DEFAULT 'Any'
        )
    """)

    c.execute("""
        CREATE TABLE resumes (
    resume_id INTEGER PRIMARY KEY,
    candidate_alias TEXT,
    email TEXT,
    resume_text TEXT,
    education_level TEXT,
    experience_years_band TEXT,
    skills_list TEXT,
    certifications TEXT,
    project_keywords TEXT,
    employment_gap_band TEXT,
    location_preference_optional TEXT,
    applied_job_id TEXT,
    source TEXT DEFAULT 'synthetic'
)
    """)

    c.execute("""
        CREATE TABLE match_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT,
            resume_id INTEGER,
            match_score REAL,
            missing_skills TEXT,
            matched_skills TEXT
        )
    """)

    c.execute("""
        CREATE TABLE employees (
            employee_id TEXT PRIMARY KEY,
            name TEXT,
            password_hash TEXT,
            salt TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE recruiter_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT,
            resume_id INTEGER,
            action TEXT,
            reason TEXT,
            override_score REAL,
            user_alias TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Seed a few default recruiter accounts. Passwords are hashed (PBKDF2),
    # never stored in plaintext. These are demo credentials -- change them
    # before using this anywhere real.
    default_employees = [
        ("EMP001", "Sreeshant Nair", "Sreeshant123"),
        ("EMP002", "Pranav Nair", "Pranav123"),
        ("EMP003", "Vishagh Nambiar", "Vishag123"),
        ("EMP004", "Tejas Achari", "Tejas123")
    ]
    for emp_id, name, plain_password in default_employees:
        pw_hash, salt = hash_password(plain_password)
        c.execute(
            "INSERT INTO employees (employee_id, name, password_hash, salt) VALUES (?, ?, ?, ?)",
            (emp_id, name, pw_hash, salt),
        )

    for i, title in enumerate(JOB_TITLES, start=1):
        job = make_job(f"JOB-DATA-{i:02d}", title)
        c.execute(
            "INSERT INTO jobs VALUES (?, ?, ?, ?, ?)",
            (job["job_id"], job["title"], job["required_skills"], job["preferred_skills"], job["required_experience"]),
        )

    for i in range(1, 501):
        insert_protected = random.random() < 0.15  # 15% of resumes
        r = make_resume(i, insert_protected)
        c.execute(
    "INSERT INTO resumes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                r["resume_id"], r["candidate_alias"], r["resume_text"],r["email"],
                r["education_level"], r["experience_years_band"], r["skills_list"],
                r["certifications"], r["project_keywords"], r["employment_gap_band"],
                r["location_preference_optional"], None, "synthetic",
            ),
        )

    conn.commit()
    conn.close()
    print("Done. Created hr.db with 20 jobs, 500 resumes, and 3 demo recruiter logins.")
    print("Demo recruiter logins (employee_id / password):")
    for emp_id, name, plain_password in default_employees:
        print(f"  {emp_id} / {plain_password}  ({name})")


if __name__ == "__main__":
    main()
