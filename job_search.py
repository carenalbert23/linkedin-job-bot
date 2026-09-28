import os
import re
import sys
import json
import time
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
from bs4 import BeautifulSoup

load_dotenv()

# ============================================================
# CONFIG
# ============================================================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

SEEN_JOBS_FILE = os.path.join(
    os.path.dirname(__file__),
    "seen_jobs.json"
)

SEEN_JOBS_TTL_DAYS = 7
TOP_N = 10
APPLICANT_FETCH_LIMIT = 15


# ============================================================
# LINKEDIN SEARCHES
# ============================================================

LINKEDIN_SEARCHES = [

    # =========================
    # EGYPT
    # On-site + Hybrid + Remote
    # =========================

    {"keywords": "Biomedical Engineer", "location": "Egypt"},
    {"keywords": "Biomedical Equipment Engineer", "location": "Egypt"},
    {"keywords": "Medical Device Engineer", "location": "Egypt"},
    {"keywords": "Clinical Engineer", "location": "Egypt"},
    {"keywords": "Medical Equipment Engineer", "location": "Egypt"},
    {"keywords": "Biomedical Service Engineer", "location": "Egypt"},
    {
        "keywords": "Field Service Engineer Medical Devices",
        "location": "Egypt"
    },

    # =========================
    # NORTH EUROPE
    # Remote only
    # =========================

    {"keywords": "Biomedical Engineer", "location": "Switzerland"},
    {"keywords": "Medical Device Engineer", "location": "Switzerland"},
    {"keywords": "Biomedical Engineer", "location": "Denmark"},
    {"keywords": "Medical Device Engineer", "location": "Denmark"},
    {"keywords": "Biomedical Engineer", "location": "Sweden"},
    {"keywords": "Medical Device Engineer", "location": "Sweden"},
    {"keywords": "Biomedical Engineer", "location": "Norway"},
    {"keywords": "Medical Device Engineer", "location": "Norway"},
    {"keywords": "Biomedical Engineer", "location": "Finland"},
    {"keywords": "Medical Device Engineer", "location": "Finland"},

    # =========================
    # OTHER EUROPE
    # Remote only
    # =========================

    {"keywords": "Biomedical Engineer", "location": "Germany"},
    {"keywords": "Medical Device Engineer", "location": "Germany"},
    {"keywords": "Biomedical Engineer", "location": "Netherlands"},
    {"keywords": "Medical Device Engineer", "location": "Netherlands"},
    {"keywords": "Biomedical Engineer", "location": "United Kingdom"},
    {"keywords": "Medical Device Engineer", "location": "United Kingdom"},
    {"keywords": "Biomedical Engineer", "location": "Ireland"},
    {"keywords": "Medical Device Engineer", "location": "Ireland"},

    # =========================
    # GULF
    # Remote only
    # =========================

    {
        "keywords": "Biomedical Engineer",
        "location": "United Arab Emirates"
    },
    {
        "keywords": "Medical Device Engineer",
        "location": "United Arab Emirates"
    },
    {
        "keywords": "Biomedical Engineer",
        "location": "Saudi Arabia"
    },
    {
        "keywords": "Medical Device Engineer",
        "location": "Saudi Arabia"
    },

    # =========================
    # WORLDWIDE
    # Remote only
    # =========================

    {
        "keywords": "Biomedical Engineer",
        "location": "Worldwide",
        "remote_only": True
    },
    {
        "keywords": "Medical Device Engineer",
        "location": "Worldwide",
        "remote_only": True
    },
    {
        "keywords": "Clinical Engineer",
        "location": "Worldwide",
        "remote_only": True
    },
]


# Company searches intentionally disabled.
COMPANY_SEARCHES = []
TARGET_COMPANIES = []


# ============================================================
# LINKEDIN HEADERS
# ============================================================

LINKEDIN_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}


# ============================================================
# ROLE SCORES
# ============================================================

ROLE_SCORES = {
    "biomedical engineer": 50,
    "biomedical equipment engineer": 48,
    "medical device engineer": 47,
    "clinical engineer": 46,
    "medical equipment engineer": 45,
    "biomedical service engineer": 44,
    "field service engineer": 42,
    "medical imaging engineer": 42,
    "imaging engineer": 40,
    "equipment engineer": 40,
    "medical device": 38,
    "medical devices": 38,
    "healthcare technology": 34,
    "health technology": 34,
    "medical technology": 34,
    "medical equipment": 34,
    "clinical": 35,
    "healthcare engineer": 30,
    "healthcare": 25,
    "field service": 32,
    "service engineer": 30,
    "technical service engineer": 30,
    "maintenance engineer": 26,
    "medical imaging": 32,
    "imaging": 28,
    "radiology": 25,
    "ultrasound": 25,
    "mri": 25,
    "x-ray": 25,
    "xray": 25,
    "research engineer": 24,
    "r&d engineer": 24,
    "research and development": 24,
    "development engineer": 22,
    "quality engineer": 22,
    "quality assurance": 20,
    "regulatory affairs": 20,
    "regulatory": 18,
    "electrical engineer": 15,
    "electronics engineer": 15,
    "systems engineer": 15,
    "test engineer": 14,
    "application engineer": 14,
}


# ============================================================
# SKILL SCORES
# ============================================================

SKILL_SCORES = {
    "biomedical": 20,
    "medical device": 20,
    "medical devices": 20,
    "medical equipment": 18,
    "clinical engineering": 18,
    "clinical engineer": 18,
    "healthcare": 12,
    "medical technology": 15,
    "medical imaging": 18,
    "imaging": 12,
    "mri": 12,
    "ultrasound": 12,
    "x-ray": 12,
    "xray": 12,
    "ct scan": 12,
    "computed tomography": 12,
    "radiology": 10,
    "medical instrumentation": 15,
    "instrumentation": 10,
    "patient monitoring": 12,
    "ventilator": 10,
    "dialysis": 10,
    "infusion pump": 10,
    "anesthesia": 10,
    "electronics": 8,
    "electrical": 8,
    "embedded": 8,
    "embedded systems": 10,
    "control systems": 8,
    "signal processing": 10,
    "python": 6,
    "matlab": 8,
    "machine learning": 8,
    "deep learning": 8,
    "artificial intelligence": 6,
    "data analysis": 6,
    "field service": 10,
    "maintenance": 8,
    "troubleshooting": 8,
    "installation": 6,
    "calibration": 8,
    "quality": 6,
    "quality assurance": 8,
    "regulatory": 8,
    "regulatory affairs": 10,
    "iso 13485": 12,
    "medical device regulation": 12,
}


# ============================================================
# LOCATION SCORES
# ============================================================

LOCATION_SCORES = {
    "egypt": 16,
    "switzerland": 14,
    "denmark": 14,
    "sweden": 14,
    "norway": 14,
    "finland": 14,
    "germany": 12,
    "netherlands": 12,
    "united kingdom": 12,
    "uk": 12,
    "ireland": 12,
    "united arab emirates": 10,
    "uae": 10,
    "saudi arabia": 10,
    "worldwide": 8,
}


# ============================================================
# CONFIG CHECK
# ============================================================

def check_config():

    missing = []

    if not TELEGRAM_TOKEN:
        missing.append("TELEGRAM_TOKEN")

    if not TELEGRAM_CHAT_ID:
        missing.append("TELEGRAM_CHAT_ID")

    if missing:
        print(
            "ERROR: Missing values in .env: "
            + ", ".join(missing)
        )
        sys.exit(1)


# ============================================================
# JOB SCORING
# ============================================================

def score_job(job: dict) -> int:

    title = (
        job.get("job_title") or ""
    ).lower()

    desc = (
        job.get("job_description") or ""
    )[:1000].lower()

    city = (
        job.get("job_city") or ""
    ).lower()

    country = (
        job.get("job_country") or ""
    ).lower()

    is_remote = job.get(
        "job_is_remote",
        False
    )

    score = 0

    for kw, pts in ROLE_SCORES.items():

        if kw in title:
            score += pts
            break

    text = title + " " + desc

    skill_pts = sum(
        pts
        for kw, pts in SKILL_SCORES.items()
        if kw in text
    )

    score += min(skill_pts, 35)

    loc_hay = (
        f"{city} {country}"
        + (
            " remote"
            if is_remote
            else ""
        )
    )

    for loc, pts in LOCATION_SCORES.items():

        if loc in loc_hay:
            score += min(pts, 16)
            break

    if is_remote:
        score += 8

    elif "hybrid" in title:
        score += 4

    return score


def score_label(score: int) -> str:

    if score >= 60:
        return "Excellent match"

    if score >= 45:
        return "Strong match"

    if score >= 30:
        return "Good match"

    return "Possible match"


# ============================================================
# APPLICANT COUNT
# ============================================================

def fetch_applicant_count(
    url: str
) -> int | None:

    if not url:
        return None

    try:

        resp = requests.get(
            url,
            headers=LINKEDIN_HEADERS,
            timeout=10
        )

        if resp.status_code != 200:
            return None

        match = re.search(
            r'(\d[\d,]*)\+?\s*'
            r'(?:applicants|people clicked apply)',
            resp.text,
            re.I
        )

        if not match:
            return None

        raw_count = (
            match.group(1)
            .replace(",", "")
            .strip()
        )

        if not raw_count.isdigit():
            return None

        return int(raw_count)

    except (
        requests.RequestException,
        ValueError,
        TypeError
    ):
        return None


def applicant_bonus(
    count: int | None
) -> int:

    if count is None:
        return 0

    if count <= 10:
        return 20

    if count <= 25:
        return 14

    if count <= 50:
        return 8

    if count <= 100:
        return 2

    return -8


def enrich_with_competition(
    jobs: list
) -> list:

    ranked = sorted(
        jobs,
        key=score_job,
        reverse=True
    )

    top = ranked[:APPLICANT_FETCH_LIMIT]
    rest = ranked[APPLICANT_FETCH_LIMIT:]

    for job in top:

        count = fetch_applicant_count(
            job.get("job_apply_link")
        )

        job["_applicants"] = count

        job["_score"] = (
            score_job(job)
            + applicant_bonus(count)
        )

        time.sleep(0.3)

    for job in rest:

        job["_applicants"] = None
        job["_score"] = score_job(job)

    return sorted(
        top + rest,
        key=lambda j: j["_score"],
        reverse=True
    )


# ============================================================
# LINKEDIN JOB PARSER
# ============================================================

def parse_card(
    card,
    search_location: str,
    remote_only: bool = False
) -> dict | None:

    link_tag = card.find(
        "a",
        class_="base-card__full-link"
    )

    if not link_tag:
        return None

    raw_url = link_tag.get("href", "")

    apply_url = (
        raw_url.split("?")[0]
        if raw_url
        else ""
    )

    
