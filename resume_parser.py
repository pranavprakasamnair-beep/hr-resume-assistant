"""
Turns an uploaded resume file into the same structured fields we use
for the synthetic dataset, so scoring works identically for both.
"""

import io
import re
from skills_dictionary import SKILLS


def extract_text_from_upload(filename: str, file_bytes: bytes) -> str:
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""

    if ext == "txt":
        return file_bytes.decode("utf-8", errors="ignore")

    if ext == "pdf":
        try:
            from pypdf import PdfReader
        except ImportError:
            raise ValueError(
                "PDF support isn't installed. Run: pip install pypdf"
            )
        reader = PdfReader(io.BytesIO(file_bytes))
        text = "\n".join((page.extract_text() or "") for page in reader.pages)
        if not text.strip():
            raise ValueError("Could not read any text from this PDF.")
        return text

    if ext == "docx":
        try:
            import docx
        except ImportError:
            raise ValueError(
                "DOCX support isn't installed. Run: pip install python-docx"
            )
        doc = docx.Document(io.BytesIO(file_bytes))
        return "\n".join(p.text for p in doc.paragraphs)

    raise ValueError("Unsupported file type. Please upload a .txt, .pdf, or .docx file.")


def extract_skills(text: str):
    text_lower = text.lower()
    return [s for s in SKILLS if s.lower() in text_lower]


def guess_education(text: str) -> str:
    t = text.lower()
    if "phd" in t or "doctorate" in t:
        return "PhD"
    if "master" in t:
        return "Masters"
    if "bachelor" in t:
        return "Bachelors"
    if "diploma" in t:
        return "Diploma"
    return "Not specified"


def guess_experience_years(text: str) -> str:
    match = re.search(r"(\d+)\+?\s*years?", text, re.IGNORECASE)
    if not match:
        return "Not specified"
    years = int(match.group(1))
    if years <= 1:
        return "0-1"
    if years <= 3:
        return "1-3"
    if years <= 5:
        return "3-5"
    if years <= 8:
        return "5-8"
    return "8+"

def extract_email(text: str) -> str:
    """
    Extracts the first email address found in the resume.
    """
    match = re.search(
        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
        text
    )

    if match:
        return match.group()

    return ""

def build_resume_record(filename: str, file_bytes: bytes):
    """Returns a dict matching our resumes table columns (minus id/alias)."""
    text = extract_text_from_upload(filename, file_bytes)
    skills = extract_skills(text)
    email = extract_email(text)

    return {
        "email": email,
        "resume_text": text,
        "education_level": guess_education(text),
        "experience_years_band": guess_experience_years(text),
        "skills_list": ", ".join(skills),
        "certifications": "",
        "project_keywords": "",
        "employment_gap_band": "Not specified",
        "location_preference_optional": "",
    }
