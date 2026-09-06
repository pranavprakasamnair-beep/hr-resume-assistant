"""
STEP 2: The matching engine.
This file has two jobs:
  1. redact() - strip out name/age/gender/religion/marital status etc
     BEFORE anything is scored or sent to an AI model.
  2. score_resumes_for_job() - use TF-IDF (a classic, explainable text-similarity
     technique - not a black-box model) to rank resumes against a job.
"""

import re
import sqlite3
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Very simple pattern-based redaction. Good enough for an MVP + synthetic data.
NAME_PATTERN = re.compile(r"[A-Z][a-z]+ [A-Z][a-z]+")
AGE_PATTERN = re.compile(r"\b\d{1,3}\s*years old\b", re.IGNORECASE)
GENDER_WORDS = ["male", "female", "non-binary", "man", "woman"]
RELIGION_WORDS = ["christian", "muslim", "hindu", "buddhist", "atheist", "jewish", "sikh"]
MARITAL_WORDS = ["single", "married", "divorced", "widowed"]

# Ordered so we can compare bands: index N meets any requirement <= index N.
EXPERIENCE_BAND_ORDER = ["0-1", "1-3", "3-5", "5-8", "8+"]


def redact(text: str) -> str:
    """Remove protected attributes from resume text before scoring or LLM use."""
    redacted = text
    redacted = AGE_PATTERN.sub("[AGE REDACTED]", redacted)
    redacted = NAME_PATTERN.sub("[NAME REDACTED]", redacted)

    for word_list, label in [
        (GENDER_WORDS, "[GENDER REDACTED]"),
        (RELIGION_WORDS, "[RELIGION REDACTED]"),
        (MARITAL_WORDS, "[MARITAL STATUS REDACTED]"),
    ]:
        for w in word_list:
            redacted = re.sub(rf"\b{w}\b", label, redacted, flags=re.IGNORECASE)

    return redacted


def get_redacted_text_for_resume(resume_id: int, db_path: str = "hr.db"):
    """Fetch and redact a single resume's text, for on-demand use (e.g. LLM summaries)."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT resume_text FROM resumes WHERE resume_id = ?", (resume_id,)
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return redact(row["resume_text"])


def experience_match_score(candidate_band: str, required_band: str):
    """
    Compares a candidate's experience band against a job's required band.
    Returns (score 0.0-1.0, meets_requirement: bool).
    If there's no requirement ('Any'/blank) or either band is unrecognized,
    we can't meaningfully evaluate it, so we give full credit.
    """
    if (
        not required_band or required_band == "Any"
        or candidate_band not in EXPERIENCE_BAND_ORDER
        or required_band not in EXPERIENCE_BAND_ORDER
    ):
        return 1.0, True

    candidate_idx = EXPERIENCE_BAND_ORDER.index(candidate_band)
    required_idx = EXPERIENCE_BAND_ORDER.index(required_band)

    if candidate_idx >= required_idx:
        return 1.0, True
    if required_idx - candidate_idx == 1:
        return 0.5, False  # one band below -- close, partial credit
    return 0.0, False  # significantly below the requirement


def score_resumes_for_job(job_id: str, db_path: str = "hr.db"):
    """
    Returns a ranked list of dicts:
    [{resume_id, candidate_alias, match_score, matched_skills, missing_skills,
      redacted_text, confidence}, ...]
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    job = c.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
    if job is None:
        conn.close()
        raise ValueError(f"No job found with id {job_id}")

    required_skills = [s.strip() for s in job["required_skills"].split(",")]
    preferred_skills = [s.strip() for s in job["preferred_skills"].split(",")]
    job_text = f"{job['title']} requires {job['required_skills']} preferred {job['preferred_skills']}"

    job_keys = job.keys()
    required_experience = job["required_experience"] if "required_experience" in job_keys and job["required_experience"] else "Any"

    resumes = c.execute("SELECT * FROM resumes").fetchall()

    # Step A: redact every resume BEFORE it touches the vectorizer
    redacted_texts = []
    for r in resumes:
        redacted_texts.append(redact(r["resume_text"]))

    # Step B: TF-IDF similarity between job description and each redacted resume
    corpus = [job_text] + redacted_texts
    vectorizer = TfidfVectorizer(stop_words="english")
    tfidf_matrix = vectorizer.fit_transform(corpus)
    similarities = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:]).flatten()

    results = []
    for r, redacted_text, sim in zip(resumes, redacted_texts, similarities):
        skills_raw = r["skills_list"] or ""
        candidate_skills = [s.strip() for s in skills_raw.split(",") if s.strip()]
        matched = [s for s in required_skills + preferred_skills if s in candidate_skills]
        missing = [s for s in required_skills if s not in candidate_skills]

        skill_overlap_ratio = len(matched) / max(len(required_skills) + len(preferred_skills), 1)

        candidate_experience = r["experience_years_band"] if "experience_years_band" in r.keys() else None
        experience_score, meets_experience = experience_match_score(candidate_experience, required_experience)

        # Transparent weighted score: 50% text similarity, 30% skill overlap,
        # 20% experience match. Weights are visible and adjustable -- not a
        # hidden black box. If the job has no experience requirement ('Any'),
        # experience_score is always 1.0 so it doesn't distort the ranking.
        final_score = round(
            (0.5 * sim + 0.3 * skill_overlap_ratio + 0.2 * experience_score) * 100, 1
        )

        # crude confidence signal: how much of the resume TF-IDF vector had
        # any overlapping vocabulary with the job at all
        confidence = "High" if sim > 0.15 else ("Medium" if sim > 0.05 else "Low")

        row_keys = r.keys()
        is_applicant = (
            "applied_job_id" in row_keys
            and r["applied_job_id"] is not None
            and r["applied_job_id"] == job_id
        )
        source = r["source"] if "source" in row_keys and r["source"] else "synthetic"

        results.append({
            "resume_id": r["resume_id"],
            "candidate_alias": r["candidate_alias"],
            "match_score": final_score,
            "matched_skills": matched,
            "missing_skills": missing,
            "redacted_text": redacted_text,
            "confidence": confidence,
            "is_applicant": is_applicant,
            "source": source,
            "experience_years_band": candidate_experience,
            "required_experience": required_experience,
            "meets_experience": meets_experience,
        })

    conn.close()
    # Real applicants to this job appear first, then ranked by score within each group.
    results.sort(key=lambda x: (not x["is_applicant"], -x["match_score"]))
    return results, dict(job)
