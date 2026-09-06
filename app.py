"""
STEP 3: The web server (backend).
Run this with:  uvicorn app:app --reload --port 8000
Then open http://localhost:8000 in a browser (once we add the frontend in step 4).

This file exposes a few simple endpoints:
  GET  /jobs                -> list all jobs
  GET  /shortlist/{job_id}  -> ranked, redacted candidate list for a job
  POST /action              -> recruiter records Shortlist / Hold / Reject
  GET  /history/{job_id}    -> recruiter action log for a job (audit trail)
"""

from fastapi import FastAPI, Form, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
import sqlite3
import uuid
from email_service import send_email

from matcher import score_resumes_for_job, get_redacted_text_for_resume
from resume_parser import build_resume_record
from job_parser import extract_job_requirements
from auth import verify_password
from llm_summary import generate_evidence_summary, generate_improvement_suggestions

app = FastAPI(title="HR Resume Selection Assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = "hr.db"


class LoginRequest(BaseModel):
    employee_id: str
    password: str


class RecruiterAction(BaseModel):
    job_id: str
    resume_id: int
    action: str  # "Shortlist" | "Hold" | "Reject"
    reason: str = ""
    override_score: float | None = None
    user_alias: str = "recruiter_1"


@app.post("/auth/login")
def login(creds: LoginRequest):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    employee = conn.execute(
        "SELECT * FROM employees WHERE employee_id = ?",
        (creds.employee_id.strip(),),
    ).fetchone()
    conn.close()

    # Deliberately vague error message either way, so we don't reveal
    # whether the employee_id exists (basic enumeration protection).
    generic_error = "Invalid employee ID or password."

    if employee is None:
        return JSONResponse(status_code=401, content={"error": generic_error})

    if not verify_password(creds.password, employee["salt"], employee["password_hash"]):
        return JSONResponse(status_code=401, content={"error": generic_error})

    return {
        "status": "ok",
        "employee_id": employee["employee_id"],
        "name": employee["name"],
    }


@app.get("/summary/{job_id}/{resume_id}")
def get_evidence_summary(job_id: str, resume_id: int):
    """
    Returns a short AI-generated summary of a candidate's skill evidence.
    Only the already-redacted text is ever sent to the LLM. Cached in the
    llm_summaries table so we don't re-call the gateway on every view.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    cached = conn.execute(
        "SELECT summary_text FROM llm_summaries WHERE job_id = ? AND resume_id = ?",
        (job_id, resume_id),
    ).fetchone()
    if cached:
        conn.close()
        return {"summary": cached["summary_text"], "cached": True}

    job = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
    if job is None:
        conn.close()
        return JSONResponse(status_code=404, content={"error": "Job not found."})

    redacted_text = get_redacted_text_for_resume(resume_id, DB_PATH)
    if redacted_text is None:
        conn.close()
        return JSONResponse(status_code=404, content={"error": "Candidate not found."})

    required = [s.strip() for s in job["required_skills"].split(",")]
    preferred = [s.strip() for s in job["preferred_skills"].split(",")]

    summary, error = generate_evidence_summary(job["title"], required, preferred, redacted_text)

    if error:
        conn.close()
        return JSONResponse(status_code=502, content={"error": error})

    conn.execute(
        "INSERT INTO llm_summaries (job_id, resume_id, summary_text) VALUES (?, ?, ?)",
        (job_id, resume_id, summary),
    )
    conn.commit()
    conn.close()

    return {"summary": summary, "cached": False}


@app.get("/jobs")
def list_jobs():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM jobs").fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.post("/jobs/create")
def create_job(
    title: str = Form(...),
    description: str = Form(...),
    required_experience: str = Form("Any"),
):
    """Recruiter posts a new job description in plain text. We extract
    required/preferred skills automatically from the description, and take
    the required experience band as an explicit dropdown choice."""
    required, preferred = extract_job_requirements(description)
    job_id = f"JOB-{uuid.uuid4().hex[:6].upper()}"

    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO jobs (job_id, title, required_skills, preferred_skills, required_experience) VALUES (?, ?, ?, ?, ?)",
        (job_id, title, ", ".join(required), ", ".join(preferred), required_experience),
    )
    conn.commit()
    conn.close()

    return {
        "job_id": job_id,
        "title": title,
        "required_skills": required,
        "preferred_skills": preferred,
        "required_experience": required_experience,
    }


@app.post("/resumes/upload")
async def upload_resume(job_id: str = Form(...), file: UploadFile = File(...)):
    """Job seeker uploads a resume for a specific job posting."""
    contents = await file.read()

    try:
        record = build_resume_record(file.filename, contents)
    except ValueError as e:
        return JSONResponse(status_code=400, content={"error": str(e)})

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT COALESCE(MAX(resume_id), 0) + 1 FROM resumes")
    new_id = cur.fetchone()[0]
    alias = f"CAN-{new_id:04d}"

    cur.execute(
    """INSERT INTO resumes
       (resume_id, candidate_alias, email, resume_text, education_level,
        experience_years_band, skills_list, certifications, project_keywords,
        employment_gap_band, location_preference_optional, applied_job_id, source)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
    (
        new_id,
        alias,
        record["email"],
        record["resume_text"],
        record["education_level"],
        record["experience_years_band"],
        record["skills_list"],
        record["certifications"],
        record["project_keywords"],
        record["employment_gap_band"],
        record["location_preference_optional"],
        job_id,
        "applicant",
    ),
)
    conn.commit()
    conn.close()

    # Immediately score this candidate against the job they just applied to,
    # and generate personalized improvement suggestions for them.
    results, job = score_resumes_for_job(job_id, DB_PATH)
    this_result = next((r for r in results if r["resume_id"] == new_id), None)

    feedback = {
        "match_score": None,
        "confidence": None,
        "matched_skills": [],
        "missing_skills": [],
        "suggestions": "Could not compute feedback for this application.",
        "ai_generated": False,
    }

    if this_result:
        required = [s.strip() for s in job["required_skills"].split(",")]
        preferred = [s.strip() for s in job["preferred_skills"].split(",")]

        suggestions, _, used_llm = generate_improvement_suggestions(
            job["title"], required, preferred,
            this_result["matched_skills"], this_result["missing_skills"],
            this_result["match_score"], this_result["redacted_text"],
        )

        feedback = {
            "match_score": this_result["match_score"],
            "confidence": this_result["confidence"],
            "matched_skills": this_result["matched_skills"],
            "missing_skills": this_result["missing_skills"],
            "suggestions": suggestions,
            "ai_generated": used_llm,
            "experience_years_band": this_result["experience_years_band"],
            "required_experience": this_result["required_experience"],
            "meets_experience": this_result["meets_experience"],
        }

    return {
        "status": "submitted",
        "candidate_alias": alias,
        "extracted_skills": record["skills_list"] or "(no known skills detected)",
        "feedback": feedback,
    }


@app.get("/shortlist/{job_id}")
def get_shortlist(job_id: str):
    results, job = score_resumes_for_job(job_id, DB_PATH)

    # Pull any existing recruiter overrides so the UI can show them
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    actions = conn.execute(
        "SELECT * FROM recruiter_actions WHERE job_id = ? ORDER BY timestamp DESC",
        (job_id,),
    ).fetchall()
    conn.close()

    latest_action_by_resume = {}
    for a in actions:
        if a["resume_id"] not in latest_action_by_resume:
            latest_action_by_resume[a["resume_id"]] = dict(a)

    for r in results:
        r["recruiter_action"] = latest_action_by_resume.get(r["resume_id"])

    return {
        "job": job,
        "candidates": results[:50],  # top 50 shown, no auto-reject of the rest
        "total_candidates": len(results),
        "disclaimer": (
            "This tool ranks candidates using transparent skill/text matching. "
            "It does NOT make hiring or rejection decisions. A human recruiter "
            "must review and approve every action."
        ),
    }

@app.post("/action")
def record_action(action: RecruiterAction):

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Save recruiter action
    conn.execute(
        """INSERT INTO recruiter_actions
           (job_id, resume_id, action, reason, override_score, user_alias)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            action.job_id,
            action.resume_id,
            action.action,
            action.reason,
            action.override_score,
            action.user_alias,
        ),
    )

    # Get candidate details
    candidate = conn.execute(
        """
        SELECT candidate_alias, email
        FROM resumes
        WHERE resume_id = ?
        """,
        (action.resume_id,),
    ).fetchone()

    conn.commit()
    conn.close()

    # Debug
    if not candidate:
        print("Candidate not found!")
    elif not candidate["email"]:
        print("Candidate has no email!")
    else:
        print("========== EMAIL DEBUG ==========")
        print("Action:", action.action)
        print("Candidate:", candidate["candidate_alias"])
        print("Email:", candidate["email"])
        print("Reason:", action.reason)

    # Send email only if we have an email address
    if candidate and candidate["email"]:

        if action.action.lower() == "shortlist":

            subject = "Congratulations! Your Application Has Been Shortlisted"

            body = f"""
Dear {candidate['candidate_alias']},

Congratulations!

Your application has been shortlisted.

Recruiter Message:
{action.reason if action.reason else "Your profile matches our current requirements."}

Our HR team will contact you soon.

Regards,
HR Team
"""

            send_email(candidate["email"], subject, body)

        elif action.action.lower() == "reject":

            subject = "Application Update"

            body = f"""
Dear {candidate['candidate_alias']},

Thank you for applying.

After reviewing your profile, we have decided not to move forward.

Recruiter Feedback:
{action.reason if action.reason else "Your profile did not match our current requirements."}

We wish you all the best.

Regards,
HR Team
"""

            send_email(candidate["email"], subject, body)

    return {"status": "recorded"}

@app.get("/history/{job_id}")
def get_history(job_id: str):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM recruiter_actions WHERE job_id = ? ORDER BY timestamp DESC",
        (job_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# Serve the frontend
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def serve_frontend():
    return FileResponse("static/index.html")