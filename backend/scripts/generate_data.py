"""Deterministic synthetic data generator (fixed seed).

Produces:
  datasets/synthetic_historical.csv   — training rows (latent-process based,
                                        probabilistic placement outcome)
  datasets/institution_master_demo.csv — institutional master CSV (import demo)

Latent factors: academic, technical, practical, problem_solving, communication.
Observed features = f(latents) + noise; placement = Bernoulli(sigmoid(z + noise))
so outcomes overlap realistically (no deterministic CGPA cutoffs).
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 20260910
MASTER_SEED = SEED + 1  # master CSV and DB seed must share this for import consistency
DATASETS_DIR = Path(__file__).resolve().parents[2] / "datasets"
FEATURES = [
    "cgpa", "tenth_percentage", "twelfth_percentage", "backlog_history_count",
    "programming_score", "sql_score", "dsa_score", "web_dev_score", "git_score",
    "cloud_score", "aptitude_score", "logical_score", "coding_score",
    "communication_score", "interview_score", "presentation_score",
    "verified_project_count", "project_complexity_score", "verified_internship_count",
    "verified_certification_count", "open_source_score", "hackathon_score", "leadership_score",
]

BRANCHES = [
    ("CSE", 180), ("ISE", 130), ("ECE", 130), ("ME", 100), ("CE", 60),
]
BRANCH_CODES = {"CSE": "CS", "ISE": "IS", "ECE": "EC", "ME": "ME", "CE": "CE"}
SEMESTERS = [4, 6, 8]
SEMESTER_WEIGHTS = [0.30, 0.35, 0.35]

ARCHETYPES = {
    # weights: (academic, technical, practical, problem_solving, communication, sql_bias)
    "fullstack":      (0.0, 0.55, 0.45, 0.15, -0.25, -0.15),
    "data":           (0.1, 0.30, 0.10, 0.45, -0.10, 0.55),
    "tech_strong":    (0.0, 0.80, -0.35, 0.30, -0.60, -0.10),
    "academic_heavy": (0.90, -0.35, -0.65, -0.15, -0.25, -0.35),
    "comm_strong":    (-0.1, -0.35, 0.05, -0.10, 0.90, -0.20),
    "balanced":       (0.15, 0.15, 0.15, 0.10, 0.10, -0.15),
    "struggling":     (-0.70, -0.75, -0.70, -0.75, -0.70, -0.30),
}
ARCHETYPE_WEIGHTS = [0.22, 0.18, 0.15, 0.15, 0.12, 0.10, 0.08]


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def latent_profile(rng: np.random.Generator, archetype: str | None = None) -> dict:
    if archetype is None:
        archetype = rng.choice(list(ARCHETYPES), p=ARCHETYPE_WEIGHTS)
    shift = ARCHETYPES[archetype]
    # institution-level mean lift (a real cohort includes support systems)
    a = shift[0] + 0.30 + rng.normal(0, 0.75)
    t = shift[1] + 0.30 + rng.normal(0, 0.75)
    p = shift[2] + 0.30 + rng.normal(0, 0.75)
    ps = shift[3] + 0.30 + rng.normal(0, 0.75)
    c = shift[4] + 0.30 + rng.normal(0, 0.75)
    return {
        "archetype": archetype,
        "academic": a, "technical": t, "practical": p,
        "problem_solving": ps, "communication": c, "sql_bias": shift[5],
    }


def observed_features(rng: np.random.Generator, L: dict) -> dict:
    a, t, p, ps, c = L["academic"], L["technical"], L["practical"], L["problem_solving"], L["communication"]
    f = {}
    f["cgpa"] = round(_clamp(7.0 + 0.9 * a + rng.normal(0, 0.35), 4.5, 9.9), 2)
    f["tenth_percentage"] = round(_clamp(78 + 7 * a + rng.normal(0, 4), 45, 99), 1)
    f["twelfth_percentage"] = round(_clamp(75 + 7 * a + rng.normal(0, 4.5), 45, 98), 1)
    p_back = _sigmoid(-0.8 * a - 0.4 * ps)
    raw = [0.62 - 0.2 * p_back, 0.22 + 0.15 * p_back, 0.09 + 0.1 * p_back, 0.07]
    p_back_dist = np.asarray(raw, dtype=float)
    p_back_dist = p_back_dist / p_back_dist.sum()
    f["backlog_history_count"] = int(rng.choice([0, 1, 2, 3], p=p_back_dist))
    f["programming_score"] = int(_clamp(62 + 9 * t + rng.normal(0, 4), 15, 98))
    f["sql_score"] = int(_clamp(52 + 9 * (t + 0.35 * L["sql_bias"]) + rng.normal(0, 6), 15, 98))
    f["dsa_score"] = int(_clamp(58 + 9 * (0.7 * t + 0.5 * ps) + rng.normal(0, 5), 15, 98))
    f["web_dev_score"] = int(_clamp(55 + 9 * t + rng.normal(0, 5), 15, 98))
    f["git_score"] = int(_clamp(58 + 8 * t + rng.normal(0, 6), 15, 98))
    f["cloud_score"] = int(_clamp(48 + 8 * t + rng.normal(0, 7), 10, 95))
    f["aptitude_score"] = int(_clamp(62 + 9 * ps + rng.normal(0, 4), 20, 98))
    f["logical_score"] = int(_clamp(60 + 8 * (0.8 * ps + 0.3 * t) + rng.normal(0, 5), 20, 98))
    f["coding_score"] = int(_clamp(60 + 8 * (0.7 * t + 0.5 * ps) + rng.normal(0, 5), 15, 98))
    f["communication_score"] = int(_clamp(60 + 9 * c + rng.normal(0, 5), 15, 98))
    f["interview_score"] = int(_clamp(58 + 8 * (0.6 * c + 0.3 * t) + rng.normal(0, 5), 15, 98))
    f["presentation_score"] = int(_clamp(56 + 8 * (0.8 * c) + rng.normal(0, 6), 15, 98))

    proj_p = _clamp(0.30 + 0.16 * p, 0.08, 0.75)
    n_proj = int(rng.choice([0, 1, 2, 3, 4], p=[1 - proj_p, proj_p * 0.45, proj_p * 0.30, proj_p * 0.17, proj_p * 0.08]))
    f["verified_project_count"] = n_proj
    f["project_complexity_score"] = int(_clamp(55 + 10 * p + 4 * t + rng.normal(0, 8), 30, 95)) if n_proj else 0
    int_p = _clamp(0.35 + 0.2 * p, 0.08, 0.75)
    f["verified_internship_count"] = int(rng.choice([0, 1, 2], p=[1 - int_p, int_p * 0.8, int_p * 0.2]))
    f["verified_certification_count"] = int(rng.choice([0, 1, 2, 3], p=[0.42, 0.31, 0.19, 0.08]))
    f["open_source_score"] = int(_clamp(30 + 25 * p + rng.normal(0, 10), 10, 90)) if rng.random() < _clamp(0.35 + 0.2 * p, 0.05, 0.8) else 0
    f["hackathon_score"] = int(_clamp(25 + 25 * p + rng.normal(0, 12), 10, 90)) if rng.random() < _clamp(0.4 + 0.2 * p, 0.05, 0.85) else 0
    f["leadership_score"] = int(_clamp(30 + 20 * c + rng.normal(0, 12), 10, 85)) if rng.random() < _clamp(0.25 + 0.2 * c, 0.03, 0.8) else 0
    return f


def placement_outcome(rng: np.random.Generator, L: dict, f: dict) -> int:
    # Placement outcome: latent capability + a direct effect of shipped,
    # verified projects (employers weight demonstrated work). Documented in
    # docs/methodology.md as part of the synthetic process design.
    z = (
        1.15 * L["technical"] + 1.0 * L["practical"] + 0.85 * L["problem_solving"]
        + 0.8 * L["communication"] + 0.55 * L["academic"]
        + 0.30 * f["verified_project_count"]
        + 0.12 * (f["project_complexity_score"] / 100.0)
        - 0.45 * min(f["backlog_history_count"], 3)
        + rng.normal(0, 0.75) - 0.25
    )
    return int(rng.random() < _sigmoid(z))


def generate_historical(n: int = 4000, seed: int = SEED) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n):
        L = latent_profile(rng)
        f = observed_features(rng, L)
        rows.append({**f, "id": i, "placed": placement_outcome(rng, L, f)})
    df = pd.DataFrame(rows)
    df = df[["id"] + FEATURES + ["placed"]]
    return df


def usn_for(branch: str, semester: int, serial: int) -> str:
    return f"{int(semester / 2)}PM24{BRANCH_CODES[branch]}{serial:03d}"


FIRST_NAMES = [
    "Aarav", "Vivaan", "Aditya", "Arjun", "Sai", "Ishaan", "Aryan", "Kabir", "Rohan", "Dev",
    "Ananya", "Diya", "Ishita", "Sanya", "Prisha", "Aisha", "Navya", "Riya", "Meera", "Tara",
    "Kavya", "Anaya", "Sneha", "Pooja", "Rahul", "Vikram", "Nikhil", "Karan", "Siddharth", "Amit",
    "Priya", "Divya", "Shreya", "Nandini", "Varun", "Harsh", "Yash", "Manish", "Ritika", "Tanvi",
    "Shruti", "Lakshmi", "Gauri", "Aditi", "Nidhi", "Isha",
]
LAST_NAMES = [
    "Sharma", "Verma", "Patel", "Reddy", "Nair", "Iyer", "Menon", "Kulkarni", "Deshmukh", "Raghavan",
    "Chopra", "Gupta", "Mehta", "Joshi", "Bhat", "Rao", "Shetty", "Nambiar", "Pillai", "Sethi",
    "Kapoor", "Malhotra", "Singh", "Chauhan", "Bhardwaj", "Taneja", "Arora", "Ghosh", "Banerjee", "Bose",
]


def name_for(index: int) -> str:
    return f"{FIRST_NAMES[index % len(FIRST_NAMES)]} {LAST_NAMES[(index * 7) % len(LAST_NAMES)]}"


def generate_master(n: int = 600, seed: int = MASTER_SEED) -> tuple[pd.DataFrame, list[dict]]:
    """Institutional master rows + parallel latent profiles for DB seeding."""
    rng = np.random.default_rng(seed)
    branches = np.concatenate([[b] * w for b, w in BRANCHES]).tolist()
    sems = np.array(SEMESTERS)
    rows, profiles = [], []
    serials = {v: 0 for v in BRANCH_CODES.values()}
    for i in range(n):
        branch = str(rng.choice(branches))
        sem = int(rng.choice(sems, p=SEMESTER_WEIGHTS))
        L = latent_profile(rng)
        f = observed_features(rng, L)
        serials[BRANCH_CODES[branch]] += 1
        usn = usn_for(branch, sem, serials[BRANCH_CODES[branch]])
        name = name_for(i)
        rows.append({
            "usn": usn,
            "name": name,
            "email": f"{usn.lower()}@northfielddemo.edu",
            "branch": branch,
            "semester": sem,
            "cgpa": f["cgpa"],
            "tenth_percentage": f["tenth_percentage"],
            "twelfth_percentage": f["twelfth_percentage"],
            "backlog_history_count": f["backlog_history_count"],
        })
        profiles.append({"usn": usn, "name": name, "branch": branch, "semester": sem,
                         **L, "features": f})
    return pd.DataFrame(rows), profiles


def main() -> None:
    DATASETS_DIR.mkdir(parents=True, exist_ok=True)
    hist = generate_historical()
    hist.to_csv(DATASETS_DIR / "synthetic_historical.csv", index=False)
    print(f"historical rows: {len(hist)}  placed rate: {hist['placed'].mean():.3f}")
    master, _ = generate_master()
    master.to_csv(DATASETS_DIR / "institution_master_demo.csv", index=False)
    print(f"master rows: {len(master)}")
    print("wrote datasets/synthetic_historical.csv and datasets/institution_master_demo.csv")


if __name__ == "__main__":
    main()
