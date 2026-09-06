# HR Resume Selection Assistant — Beginner Setup Guide

This is a working MVP. Follow these steps exactly, in order.

## What you need first

1. **Install Python** (if you don't have it): go to https://www.python.org/downloads/
   and install Python 3.10 or newer. During install on Windows, check the box
   "Add Python to PATH".
2. **A code editor** (optional but helpful): VS Code, free at https://code.visualstudio.com/

## Step-by-step: run the project

Open a terminal (Command Prompt on Windows, Terminal on Mac) and navigate into
this folder:

```
cd path/to/hr_assistant
```

### 1. Install the required libraries

```
pip install fastapi uvicorn scikit-learn faker python-multipart pypdf python-docx python-dotenv requests
```

(`pypdf` and `python-docx` let job seekers upload .pdf and .docx resumes, not just .txt)

### 2. Generate the synthetic dataset (only run this once)


```
python generate_data.py
```

You should see: `Done. Created hr.db with 20 jobs and 500 resumes.`
This creates a file called `hr.db` — that's your database, don't delete it.

### 2b. (Optional) Set up the AI evidence summary feature

The recruiter view has an "✨ AI summary" button on each candidate that
generates a short natural-language summary of their skill evidence, using
your team's LLM gateway. To enable it:

1. Copy `.env.example` to a new file called `.env` in this folder.
2. Fill in your real `GATEWAY_URL` and `TEAM_TOKEN` in `.env`.
3. Never share or commit the real `.env` file -- it holds a live credential.

If you skip this step, the app still works fine; clicking "AI summary" will
just show a friendly error saying the LLM isn't configured.

Only the already-redacted candidate text is ever sent to the LLM -- never
raw resume text -- and summaries are cached in the database after the first
generation so you're not re-calling the gateway every time.

### 2c. Apply database migrations (if you already have an hr.db from before)

If you generated `hr.db` before this feature existed, run these once to add
the new tables without losing your existing jobs/resumes/actions:

```
python3 migrate_add_employees.py
python3 migrate_add_llm_summaries.py
```

Both are safe to re-run -- they do nothing if the table already exists.

### 3. Start the server

```
uvicorn app:app --reload --port 8000
```

Leave this terminal window open — it's your running app.

### 4. Open the app in your browser

Go to: **http://localhost:8000**

You'll land on a screen asking: **"Who's using this today?"**

**If you click "I'm looking for a job":**
- Pick the job title you want to apply for from the dropdown
- See that job's required/preferred skills
- Upload your resume (.txt, .pdf, or .docx)
- Click "Submit application" — you'll get a candidate ID and see which skills were detected

**If you click "I'm hiring":**
- **"Post a job" tab**: type a job title and paste a job description. Mention
  the words "required skills:" and "preferred skills:" in your description
  for the most accurate skill detection.
- **"Review candidates" tab**: pick any job (including ones you just posted)
  and see a ranked candidate list with match scores, matched/missing skills,
  a redacted evidence snippet, and Shortlist/Hold/Reject buttons.
  Real applicants are marked with a green "Applicant" badge; the synthetic
  demo resumes are marked "Sample pool" for comparison/context.

Click "Switch role" (top right) any time to go back to the role screen.

## How the project is organized

| File | What it does |
|---|---|
| `generate_data.py` | Creates 500 synthetic resumes + 20 job descriptions in `hr.db` |
| `skills_dictionary.py` | Master list of known skills, shared by data generation, resume parsing, and job parsing |
| `resume_parser.py` | Reads an uploaded .txt/.pdf/.docx resume and extracts skills/education/experience |
| `job_parser.py` | Reads a recruiter's pasted job description and extracts required/preferred skills |
| `matcher.py` | Redacts protected info, then scores/ranks resumes using TF-IDF similarity + skill overlap |
| `llm_summary.py` | Calls the LLM gateway to generate a short skill-evidence summary (redacted text only) |
| `auth.py` | Password hashing/verification for recruiter login |
| `.env.example` | Template for the LLM gateway credentials (copy to `.env` and fill in) |
| `app.py` | The web server (API) that connects the database, the matcher, and the frontend |
| `static/index.html` | The webpage — login screen + job seeker view + recruiter view |
| `hr.db` | The SQLite database (created after step 2) |

## How to demo this for judges

1. Land on the role screen — explain this separates the job-seeker experience
   from the recruiter experience.
2. **As a recruiter**: post a new job (title + description mentioning
   "required skills:" / "preferred skills:") — show the skills get
   auto-detected.
3. **Switch role** to job seeker: pick that same job from the dropdown,
   upload a short .txt resume, submit it.
4. **Switch role** back to recruiter → Review candidates → pick that job →
   point out your just-submitted resume appears with a green "Applicant"
   badge, ranked alongside the "Sample pool" demo data.
5. Point out the disclaimer banner (required guardrail) and the confidence
   badge (High/Medium/Low) next to each candidate.
6. Open the "evidence" box — show that it's plain, factual text (no
   personality judgments), and any protected info (name/age/gender/religion)
   appears as `[REDACTED]`.
7. Click Shortlist on one candidate, Reject on another (type a reason when
   asked). Refresh the page — show the action persisted ("Last action: ..."
   label). This proves the audit trail.
8. To prove prompt-injection safety: open a terminal and run the redaction
   test command below.

## Things you can extend if you have more time

- Add a real LLM call in `app.py` to generate a 2-3 sentence natural-language
  evidence summary (only pass it `redacted_text`, never raw resume text).
- Add simple login (recruiter username) instead of the hardcoded `recruiter_1`.
- Add a `/history/{job_id}` page in the frontend to show the full audit trail.
- Add file upload (.txt/.pdf) instead of only using the pre-generated dataset.

## Troubleshooting

- **"command not found: python"** → try `python3` instead of `python`.
- **"port already in use"** → change `--port 8000` to `--port 8001` and open
  http://localhost:8001 instead.
- **Blank page in browser** → make sure the terminal running `uvicorn` is still
  open and didn't show an error.


Final score = round((0.5*sim + 0.3*skill_overlap + 0.2*experience_score) * 100, 1)+