import os
import re
import sys
import json
import time
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from bs4 import BeautifulSoup

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

SEEN_JOBS_FILE = os.path.join(os.path.dirname(__file__), "seen_jobs.json")
SEEN_JOBS_TTL_DAYS = 7
TOP_N = 10


# ══════════════════════════════════════════════════════════════════════════════
# LINKEDIN SEARCHES — BIOMEDICAL ENGINEERING
# ══════════════════════════════════════════════════════════════════════════════

LINKEDIN_SEARCHES = [

    # 🇪🇬 Egypt
    {"keywords": "Biomedical Engineer", "location": "Egypt"},
    {"keywords": "Clinical Engineer", "location": "Egypt"},
    {"keywords": "Medical Device Engineer", "location": "Egypt"},
    {"keywords": "Biomedical Equipment Engineer", "location": "Egypt"},
    {"keywords": "Medical Imaging Engineer", "location": "Egypt"},

    # 🇦🇪 UAE
    {"keywords": "Biomedical Engineer", "location": "United Arab Emirates"},
    {"keywords": "Clinical Engineer", "location": "United Arab Emirates"},
    {"keywords": "Medical Device Engineer", "location": "United Arab Emirates"},
    {"keywords": "Medical Imaging Engineer", "location": "United Arab Emirates"},

    # 🇸🇦 Saudi Arabia
    {"keywords": "Biomedical Engineer", "location": "Saudi Arabia"},
    {"keywords": "Clinical Engineer", "location": "Saudi Arabia"},
    {"keywords": "Medical Device Engineer", "location": "Saudi Arabia"},
    {"keywords": "Biomedical Equipment Engineer", "location": "Saudi Arabia"},

    # 🌍 Remote / Worldwide
    {
        "keywords": "Biomedical Engineer",
        "location": "Worldwide",
        "remote_only": True,
    },
    {
        "keywords": "Medical Device Engineer",
        "location": "Worldwide",
        "remote_only": True,
    },
    {
        "keywords": "Medical Imaging Engineer",
        "location": "Worldwide",
        "remote_only": True,
    },
    {
        "keywords": "Healthcare AI",
        "location": "Worldwide",
        "remote_only": True,
    },
]


# ══════════════════════════════════════════════════════════════════════════════
# TARGET COMPANIES
# ══════════════════════════════════════════════════════════════════════════════

TARGET_COMPANIES = [
    "Siemens Healthineers",
    "GE HealthCare",
    "Philips",
    "Medtronic",
    "B. Braun",
    "Baxter",
    "Fresenius Medical Care",
    "Abbott",
    "Boston Scientific",
    "Stryker",
    "Roche",
    "Elekta",
    "Olympus",
    "Canon Medical Systems",
    "Samsung Medison",
]


# ══════════════════════════════════════════════════════════════════════════════
# BIOMEDICAL KEYWORDS
# ══════════════════════════════════════════════════════════════════════════════

BIOMEDICAL_KEYWORDS = [
    "biomedical",
    "clinical engineering",
    "clinical engineer",
    "medical device",
    "medical devices",
    "medical equipment",
    "medical imaging",
    "healthcare technology",
    "healthcare engineering",
    "medical instrumentation",
    "biosensor",
    "biosensors",
    "patient monitoring",
    "diagnostic equipment",
    "radiology equipment",
    "ultrasound",
    "mri",
    "ct scanner",
    "x-ray",
    "mammography",
    "hospital equipment",
]


# ══════════════════════════════════════════════════════════════════════════════
# ROLE SCORING
# ══════════════════════════════════════════════════════════════════════════════

ROLE_SCORES = {
    "biomedical engineer": 30,
    "biomedical engineering": 25,
    "clinical engineer": 28,
    "medical device engineer": 30,
    "medical devices engineer": 28,
    "biomedical equipment engineer": 28,
    "medical imaging engineer": 30,
    "medical ai engineer": 28,
    "healthcare ai": 25,
    "r&d biomedical": 28,
    "research and development": 15,
    "field service engineer": 15,
}


# ══════════════════════════════════════════════════════════════════════════════
# SKILL SCORING
# ══════════════════════════════════════════════════════════════════════════════

SKILL_SCORES = {
    "biomedical engineering": 20,
    "medical devices": 18,
    "medical device": 18,
    "medical imaging": 18,
    "matlab": 15,
    "python": 15,
    "signal processing": 15,
    "machine learning": 15,
    "deep learning": 15,
    "image processing": 15,
    "medical instrumentation": 15,
    "instrumentation": 12,
    "biosensors": 12,
    "embedded systems": 12,
    "labview": 10,
    "tissue engineering": 10,
    "bioprinting": 10,
    "data analysis": 10,
    "artificial intelligence": 12,
}


# ══════════════════════════════════════════════════════════════════════════════
# LOCATION SCORING
# ══════════════════════════════════════════════════════════════════════════════

LOCATION_SCORES = {
    "egypt": 20,
    "cairo": 20,

    "united arab emirates": 20,
    "uae": 20,
    "dubai": 20,
    "abu dhabi": 20,

    "saudi arabia": 18,
    "saudi": 18,
    "riyadh": 18,
    "jeddah": 18,

    "worldwide": 15,
    "global": 15,
    "remote": 14,
}


# ══════════════════════════════════════════════════════════════════════════════
# LOCATION CODE MAP
# ══════════════════════════════════════════════════════════════════════════════

LOCATION_CODE_MAP = {
    "united arab emirates": "ae",
    "uae": "ae",
    "dubai": "ae",
    "abu dhabi": "ae",

    "saudi arabia": "sa",
    "riyadh": "sa",
    "jeddah": "sa",

    "egypt": "eg",
    "cairo": "eg",

    "worldwide": "global",
}


def infer_country_code(location: str) -> str:
    loc = location.lower()

    for key, value in LOCATION_CODE_MAP.items():
        if key in loc:
            return value

    return "global"


# ══════════════════════════════════════════════════════════════════════════════
# LINKEDIN HEADERS
# ══════════════════════════════════════════════════════════════════════════════

LINKEDIN_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}


# ══════════════════════════════════════════════════════════════════════════════
# SCORE JOB
# ══════════════════════════════════════════════════════════════════════════════

def score_job(job: dict) -> int:

    title = (job.get("job_title") or "").lower()
    desc = (job.get("job_description") or "")[:1000].lower()
    city = (job.get("job_city") or "").lower()
    country = (job.get("job_country") or "").lower()
    company = (job.get("employer_name") or "").lower()
    is_remote = job.get("job_is_remote", False)

    full_text = title + " " + desc

    score = 0

    # ── Biomedical relevance ─────────────────────────────
    biomedical_matches = [
        kw for kw in BIOMEDICAL_KEYWORDS
        if kw in full_text
    ]

    if biomedical_matches:
        score += min(len(biomedical_matches) * 8, 30)

    # ── Role match ───────────────────────────────────────
    for kw, pts in ROLE_SCORES.items():
        if kw in title:
            score += pts
            break

    # ── Skills match ────────────────────────────────────
    skill_pts = sum(
        pts
        for kw, pts in SKILL_SCORES.items()
        if kw in full_text
    )

    score += min(skill_pts, 35)

    # ── Location ─────────────────────────────────────────
    loc_hay = f"{city} {country}"

    if is_remote:
        loc_hay += " remote"

    for loc, pts in LOCATION_SCORES.items():
        if loc in loc_hay:
            score += pts
            break

    # ── Target company ──────────────────────────────────
    if any(
        name.lower() in company
        for name in TARGET_COMPANIES
    ):
        score += 15

    # ── Remote / Hybrid ─────────────────────────────────
    if is_remote:
        score += 8

    elif any(
        word in title
        for word in ("hybrid", "remote")
    ):
        score += 5

    return score


def score_label(score: int) -> str:

    if score >= 60:
        return "Excellent match"

    if score >= 45:
        return "Strong match"

    if score >= 30:
        return "Good match"

    return "Possible match"


# ══════════════════════════════════════════════════════════════════════════════
# APPLICANT COMPETITION
# ══════════════════════════════════════════════════════════════════════════════

APPLICANT_FETCH_LIMIT = 15


def fetch_applicant_count(url: str) -> int | None:

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
            r'([\d,]+)\+?\s*(?:applicants|people clicked apply)',
            resp.text,
            re.I
        )

        if match:
            return int(
                match.group(1).replace(",", "")
            )

    except requests.RequestException:
        pass

    return None


def applicant_bonus(count: int | None) -> int:

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


def enrich_with_competition(jobs: list) -> list:

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


# ══════════════════════════════════════════════════════════════════════════════
# PARSE LINKEDIN JOB CARD
# ══════════════════════════════════════════════════════════════════════════════

def parse_card(card, search_location: str) -> dict | None:

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

    match = re.search(
        r"-(\d{8,})$",
        apply_url
    )

    job_id = (
        f"li_{match.group(1)}"
        if match
        else None
    )

    if not job_id:
        return None

    title_tag = card.find(
        "h3",
        class_="base-search-card__title"
    )

    company_tag = card.find(
        "h4",
        class_="base-search-card__subtitle"
    )

    loc_tag = card.find(
        "span",
        class_="job-search-card__location"
    )

    title = (
        title_tag.get_text(strip=True)
        if title_tag
        else ""
    ).strip()

    company = (
        company_tag.get_text(strip=True)
        if company_tag
        else ""
    ).strip()

    location = (
        loc_tag.get_text(strip=True)
        if loc_tag
        else search_location
    ).strip()

    is_remote = True

    return {
        "job_id": job_id,
        "job_title": title,
        "employer_name": company,
        "job_city": location,
        "job_country": search_location,
        "_search_country": infer_country_code(
            search_location
        ),
        "job_is_remote": is_remote,
        "job_apply_link": apply_url,
        "job_description": "",
        "apply_options": [
            {
                "apply_link": apply_url,
                "is_direct": False,
                "publisher": "LinkedIn",
            }
        ],
    }


# ══════════════════════════════════════════════════════════════════════════════
# LINKEDIN SEARCH
# ══════════════════════════════════════════════════════════════════════════════

def search_linkedin(
    keywords: str,
    location: str,
    remote_only: bool = False
) -> list:

    url = (
        "https://www.linkedin.com/jobs-guest/"
        "jobs/api/seeMoreJobPostings/search"
    )

    params = {
        "keywords": keywords,
        "f_TPR": "r259200",
        "start": 0,
        "f_WT": "2",
    }

    if remote_only:
        params["location"] = ""
    else:
        params["location"] = location

    try:

        resp = requests.get(
            url,
            headers=LINKEDIN_HEADERS,
            params=params,
            timeout=15
        )

        if resp.status_code != 200:

            print(
                f"Warning: LinkedIn returned "
                f"{resp.status_code} for "
                f"'{keywords}' / {location}"
            )

            return []

        soup = BeautifulSoup(
            resp.text,
            "html.parser"
        )

        jobs = []

        for card in soup.find_all("li"):

            job = parse_card(
                card,
                location
            )

            if job:
                jobs.append(job)

        return jobs

    except requests.RequestException as e:

        print(
            f"Warning: LinkedIn search failed "
            f"for '{keywords}': {e}"
        )

        return []


# ══════════════════════════════════════════════════════════════════════════════
# TELEGRAM
# ══════════════════════════════════════════════════════════════════════════════

def esc(text: str) -> str:

    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def format_job(
    rank: int,
    job: dict
) -> str:

    title = esc(
        job.get("job_title") or "N/A"
    )

    company = esc(
        job.get("employer_name") or "N/A"
    )

    location = esc(
        job.get("job_city")
        or job.get("job_country")
        or "Unknown"
    )

    is_remote = job.get(
        "job_is_remote",
        False
    )

    is_target = job.get(
        "_company_match",
        False
    )

    score = job.get(
        "_score",
        score_job(job)
    )

    applicants = job.get(
        "_applicants"
    )

    title_lower = (
        job.get("job_title") or ""
    ).lower()

    if (
        "hybrid" in title_lower
        or "hybrid" in location.lower()
    ):
        work_mode = "Hybrid"

    elif (
        is_remote
        or "remote" in title_lower
    ):
        work_mode = "Remote"

    else:
        work_mode = location

    apply_url = (
        job.get("job_apply_link")
        or ""
    )

    safe_url = apply_url.replace(
        "&",
        "&amp;"
    )

    apply_part = (
        f' | <a href="{safe_url}">'
        f'Apply on LinkedIn</a>'
        if safe_url
        else ""
    )

    badge = (
        " [TARGET CO.]"
        if is_target
        else ""
    )

    if applicants is None:
        competition = ""

    elif applicants <= 25:
        competition = (
            f" | {applicants} applicants "
            f"(low competition)"
        )

    else:
        competition = (
            f" | {applicants} applicants"
        )

    return (
        f"<b>#{rank} {title}</b>{badge}\n"
        f"{company} | {work_mode}\n"
        f"<i>{score_label(score)} "
        f"({score} pts)</i>"
        f"{competition}"
        f"{apply_part}"
    )


def send_telegram(text: str):

    url = (
        f"https://api.telegram.org/"
        f"bot{TELEGRAM_TOKEN}/sendMessage"
    )

    lines = text.split("\n")

    chunks = []
    current = ""

    for line in lines:

        candidate = (
            current
            + line
            + "\n"
        )

        if len(candidate) > 4000:

            if current:
                chunks.append(
                    current.rstrip()
                )

            current = line + "\n"

        else:
            current = candidate

    if current.strip():
        chunks.append(
            current.rstrip()
        )

    for chunk in chunks:

        try:

            resp = requests.post(
                url,
                json={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": chunk,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
                timeout=15,
            )

            resp.raise_for_status()

        except requests.RequestException as e:

            print(
                f"Error sending Telegram message: {e}"
            )


# ══════════════════════════════════════════════════════════════════════════════
# SEEN JOBS
# ══════════════════════════════════════════════════════════════════════════════

def check_config():

    missing = [
        key
        for key in (
            "TELEGRAM_TOKEN",
            "TELEGRAM_CHAT_ID"
        )
        if not os.getenv(key)
        or "your_" in os.getenv(key)
    ]

    if missing:

        print(
            "ERROR: Missing values in .env: "
            + ", ".join(missing)
        )

        sys.exit(1)


def load_seen_jobs() -> dict:

    if not os.path.exists(
        SEEN_JOBS_FILE
    ):
        return {}

    with open(
        SEEN_JOBS_FILE,
        "r"
    ) as f:

        data = json.load(f)

    cutoff = (
        datetime.now()
        - timedelta(
            days=SEEN_JOBS_TTL_DAYS
        )
    ).isoformat()

    return {
        jid: ts
        for jid, ts in data.items()
        if ts >= cutoff
    }


def save_seen_jobs(seen: dict):

    with open(
        SEEN_JOBS_FILE,
        "w"
    ) as f:

        json.dump(
            seen,
            f
        )


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():

    # ── Cairo time check ─────────────────────────────────
    cairo_time = datetime.now(
        ZoneInfo("Africa/Cairo")
    )

    if cairo_time.hour != 14:

        print(
            "Not 2 PM Cairo time. "
            f"Current Cairo time: {cairo_time}"
        )

        return

    check_config()

    print(
        f"[{cairo_time.strftime('%H:%M:%S')}] "
        "Starting Biomedical Engineering job search..."
    )

    seen = load_seen_jobs()

    this_run_ids: set = set()

    general_jobs: list = []

    company_jobs: list = []


    # ══════════════════════════════════════════════════════════════════════════
    # GENERAL BIOMEDICAL SEARCHES
    # ══════════════════════════════════════════════════════════════════════════

    print(
        "--- Biomedical Engineering searches ---"
    )

    for search in LINKEDIN_SEARCHES:

        jobs = search_linkedin(
            search["keywords"],
            search["location"],
            search.get(
                "remote_only",
                False
            )
        )

        kept = 0

        for job in jobs:

            job_id = job.get(
                "job_id"
            )

            if (
                not job_id
                or job_id in seen
                or job_id in this_run_ids
            ):
                continue

            # ── Biomedical relevance filter ──────────────
            title = (
                job.get("job_title")
                or ""
            ).lower()

            desc = (
                job.get("job_description")
                or ""
            ).lower()

            full_text = (
                title
                + " "
                + desc
            )

            if not any(
                keyword in full_text
                for keyword in BIOMEDICAL_KEYWORDS
            ):
                continue

            this_run_ids.add(job_id)

            general_jobs.append(job)

            kept += 1

        print(
            f"  '{search['keywords']}' / "
            f"{search['location']} -> "
            f"{kept} new"
        )


    # ══════════════════════════════════════════════════════════════════════════
    # TARGET COMPANY SEARCHES
    # ══════════════════════════════════════════════════════════════════════════

    print(
        "--- Target company searches ---"
    )

    # Search for jobs at target companies.
    # LinkedIn guest search may return company-related results
    # that we then verify using the company name.

    for company in TARGET_COMPANIES:

        jobs = search_linkedin(
            company,
            "Worldwide",
            True
        )

        kept = 0

        for job in jobs:

            job_id = job.get(
                "job_id"
            )

            if (
                not job_id
                or job_id in seen
                or job_id in this_run_ids
            ):
                continue

            title = (
                job.get("job_title")
                or ""
            ).lower()

            desc = (
                job.get("job_description")
                or ""
            ).lower()

            employer = (
                job.get("employer_name")
                or ""
            ).lower()

            full_text = (
                title
                + " "
                + desc
                + " "
                + employer
            )

            # Job must be Biomedical-related
            biomedical_match = any(
                keyword in full_text
                for keyword in BIOMEDICAL_KEYWORDS
            )

            # Company must match one of our target companies
            company_match = any(
                company_name.lower()
                in employer
                for company_name in TARGET_COMPANIES
            )

            if not biomedical_match:
                continue

            if not company_match:
                continue

            job["_company_match"] = True

            this_run_ids.add(job_id)

            company_jobs.append(job)

            kept += 1

        print(
            f"  '{company}' -> "
            f"{kept} relevant"
        )


    print(
        f"Biomedical jobs: "
        f"{len(general_jobs)} | "
        f"Target company jobs: "
        f"{len(company_jobs)}"
    )


    # ══════════════════════════════════════════════════════════════════════════
    # TELEGRAM REPORT
    # ══════════════════════════════════════════════════════════════════════════

    all_new = (
        general_jobs
        + company_jobs
    )

    if not all_new:

        send_telegram(
            "<b>🧬 Biomedical Engineering "
            "Job Report - "
            + cairo_time.strftime(
                "%b %d, %Y"
            )
            + "</b>\n\n"
            "No new Biomedical Engineering "
            "jobs found today."
        )

    else:

        general_jobs = (
            enrich_with_competition(
                general_jobs
            )
        )

        company_jobs = (
            enrich_with_competition(
                company_jobs
            )
        )

        top_general = (
            general_jobs[:5]
        )

        top_company = (
            company_jobs[:5]
        )

        date_str = cairo_time.strftime(
            "%b %d, %Y"
        )

        lines = [

            f"<b>🧬 Biomedical Engineering "
            f"Job Report - {date_str}</b>\n",

            "Egypt + UAE + Saudi Arabia "
            "+ Remote | LinkedIn\n",
        ]


        # ── General Biomedical jobs ──────────────────────

        if top_general:

            lines.append(
                "<b>-- Best Biomedical "
                "Role Matches --</b>"
            )

            lines.append("")

            for i, job in enumerate(
                top_general,
                1
            ):

                lines.append(
                    format_job(
                        i,
                        job
                    )
                )

                lines.append("")


        # ── Target companies ─────────────────────────────

        if top_company:

            lines.append(
                "<b>-- Target Medical "
                "Companies --</b>"
            )

            lines.append("")

            for i, job in enumerate(
                top_company,
                1
            ):

                lines.append(
                    format_job(
                        i,
                        job
                    )
                )

                lines.append("")


        send_telegram(
            "\n".join(lines)
        )

        print(
            "Telegram sent: "
            f"{len(top_general)} biomedical "
            "role matches + "
            f"{len(top_company)} target company matches."
        )


    # ══════════════════════════════════════════════════════════════════════════
    # SAVE SEEN JOBS
    # ══════════════════════════════════════════════════════════════════════════

    now_iso = datetime.now().isoformat()

    for job_id in this_run_ids:

        seen[job_id] = now_iso

    save_seen_jobs(seen)


# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    main()
```
