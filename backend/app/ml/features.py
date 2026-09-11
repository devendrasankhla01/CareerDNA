"""ML feature schema — the single source of truth for model features.

Identifiers (name, USN, email) and protected attributes are never features.
`derived` features are computed from verified profile state (documented in
docs/methodology.md). Feature order is fixed by FEATURE_ORDER.
"""
from __future__ import annotations

FEATURE_SCHEMA_VERSION = "feature_schema_v1"

FEATURE_ORDER: list[str] = [
    "cgpa",
    "tenth_percentage",
    "twelfth_percentage",
    "backlog_history_count",
    "programming_score",
    "sql_score",
    "dsa_score",
    "web_dev_score",
    "git_score",
    "cloud_score",
    "aptitude_score",
    "logical_score",
    "coding_score",
    "communication_score",
    "interview_score",
    "presentation_score",
    "verified_project_count",
    "project_complexity_score",
    "verified_internship_count",
    "verified_certification_count",
    "open_source_score",
    "hackathon_score",
    "leadership_score",
]

FEATURE_LABELS: dict[str, str] = {
    "cgpa": "CGPA",
    "tenth_percentage": "10th Percentage",
    "twelfth_percentage": "12th Percentage",
    "backlog_history_count": "Backlog History",
    "programming_score": "Programming",
    "sql_score": "SQL Proficiency",
    "dsa_score": "DSA & Problem Solving",
    "web_dev_score": "Web Development",
    "git_score": "Git/GitHub",
    "cloud_score": "Cloud Fundamentals",
    "aptitude_score": "Aptitude",
    "logical_score": "Logical Reasoning",
    "coding_score": "Coding Assessment",
    "communication_score": "Communication",
    "interview_score": "Interview Performance",
    "presentation_score": "Presentation",
    "verified_project_count": "Verified Projects",
    "project_complexity_score": "Project Complexity",
    "verified_internship_count": "Internship Experience",
    "verified_certification_count": "Verified Certifications",
    "open_source_score": "Open-Source Activity",
    "hackathon_score": "Hackathons & Competitions",
    "leadership_score": "Leadership & Activities",
}

FEATURE_GROUPS: dict[str, list[str]] = {
    "Academic": ["cgpa", "tenth_percentage", "twelfth_percentage", "backlog_history_count"],
    "Technical": [
        "programming_score", "sql_score", "dsa_score", "web_dev_score",
        "git_score", "cloud_score", "coding_score",
    ],
    "Practical": [
        "verified_project_count", "project_complexity_score",
        "verified_internship_count", "verified_certification_count",
        "open_source_score",
    ],
    "Aptitude": ["aptitude_score", "logical_score"],
    "Soft Skills": ["communication_score", "interview_score", "presentation_score"],
    "Activities": ["hackathon_score", "leadership_score"],
}

# Features a student may realistically improve in the short term (optimizer /
# what-if simulator). Fixed historical data (10th/12th, CGPA, backlogs) is
# deliberately excluded — it cannot be simulated.
ACTIONABLE_FEATURES: dict[str, dict] = {
    "sql_score": {"target": 70, "label": "Improve SQL Proficiency"},
    "dsa_score": {"target": 65, "label": "Strengthen DSA & Problem Solving"},
    "programming_score": {"target": 70, "label": "Strengthen Programming Fundamentals"},
    "web_dev_score": {"target": 70, "label": "Improve Web Development"},
    "git_score": {"target": 65, "label": "Practise Git/GitHub Workflows"},
    "cloud_score": {"target": 60, "label": "Learn Cloud Fundamentals"},
    "aptitude_score": {"target": 75, "label": "Prepare for Aptitude Assessment"},
    "logical_score": {"target": 70, "label": "Practise Logical Reasoning"},
    "coding_score": {"target": 75, "label": "Improve Coding Assessment"},
    "communication_score": {"target": 70, "label": "Improve Interview Communication"},
    "interview_score": {"target": 70, "label": "Practise Mock Interviews"},
    "presentation_score": {"target": 65, "label": "Practise Presentations"},
    "verified_project_count": {"target": 2, "label": "Complete Verified Projects"},
    "verified_internship_count": {"target": 1, "label": "Gain Practical Industry Exposure"},
}
