"""
Given a raw job description pasted by a recruiter, extract:
  - required_skills
  - preferred_skills

Heuristic: look for a "required" section and a "preferred" / "nice to have"
section. If those words aren't present, just detect skills anywhere and
split them into required (first ones found) / preferred (rest).
"""

from skills_dictionary import SKILLS


def extract_job_requirements(description_text: str):
    lower = description_text.lower()

    required_idx = lower.find("required")
    preferred_idx = lower.find("preferred")
    if preferred_idx == -1:
        preferred_idx = lower.find("nice to have")

    required_section = description_text
    preferred_section = ""

    if required_idx != -1 and preferred_idx != -1 and preferred_idx > required_idx:
        required_section = description_text[required_idx:preferred_idx]
        preferred_section = description_text[preferred_idx:]
    elif required_idx != -1:
        required_section = description_text[required_idx:]

    required_skills = [s for s in SKILLS if s.lower() in required_section.lower()]
    preferred_skills = [
        s for s in SKILLS
        if s.lower() in preferred_section.lower() and s not in required_skills
    ]

    # Fallback: no explicit "required"/"preferred" wording found at all.
    # Just detect any skills mentioned anywhere in the text.
    if not required_skills:
        all_found = [s for s in SKILLS if s.lower() in lower]
        required_skills = all_found[:4]
        preferred_skills = [s for s in all_found if s not in required_skills][:3]

    return required_skills, preferred_skills
