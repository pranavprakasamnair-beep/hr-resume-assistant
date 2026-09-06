"""
Shared skill dictionary. Used by:
  - generate_data.py (to build synthetic resumes/jobs)
  - resume_parser.py (to extract skills from an uploaded resume)
  - job_parser.py (to extract required/preferred skills from a pasted job description)

Keeping this in ONE file means a skill only needs to be added here once.
"""

SKILLS = [
    "Python", "SQL", "Excel", "Java", "AWS", "Docker", "React", "Node.js",
    "Machine Learning", "Data Analysis", "Project Management", "Communication",
    "Tableau", "PowerBI", "C++", "Kubernetes", "Git", "Agile", "Scrum",
    "TensorFlow", "PyTorch", "NLP", "Deep Learning", "Linux", "Azure",
]
