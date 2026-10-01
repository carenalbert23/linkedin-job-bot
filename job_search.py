import os
import re
import sys
import json
import time
import requests
from datetime import datetime
from dotenv import load_dotenv
from bs4 import BeautifulSoup

load_dotenv()

print("JOB SEARCH SCRIPT STARTED", flush=True)

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

print("CONFIG LOADED", flush=True)

# ============================================================
# LINKEDIN SEARCHES
# EGYPT ONLY
# ============================================================

LINKEDIN_SEARCHES = [

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

]

print(
    f"SEARCHES LOADED: {len(LINKEDIN_SEARCHES)}",
    flush=True
)

# Company searches disabled
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
    "medical devices": 38,
    "medical device": 38,
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
# EGYPT ONLY
# ============================================================

LOCATION_SCORES = {
    "egypt": 20,
    "cairo": 16,
    "giza": 16,
    "alexandria": 14,
    "6th of october": 14,
    "new cairo": 14,
    "nasr city": 14,
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
            "ERROR: Missing values: "
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

    # Role score
    for kw, pts in ROLE_SCORES.items():

        if kw in title:
            score += pts
            break

    # Skill score
    text = title + " " + desc

    skill_pts = sum(
        pts
        for kw, pts in SKILL_SCORES.items()
        if kw in text
    )

    score += min(skill_pts, 35)

    # Location score
    loc_hay = (
        f"{city} {country}"
    )

    for loc, pts in LOCATION_SCORES.items():

        if loc in loc_hay:
            score += min(pts, 20)
            break

    # Remote is NOT a priority anymore
    # because all searches are Egypt-only.

    if "hybrid" in title:
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

    title_tag = card.find(
        "h3",
        class_="base-search-card__title"
    )

    company_tag = card.find(
        "h4",
        class_="base-search-card__subtitle"
    )

    location_tag = card.find(
        "span",
        class_="job-search-card__location"
    )

    title = (
        title_tag.get_text(" ", strip=True)
        if title_tag
        else ""
    )

    company = (
        company_tag.get_text(" ", strip=True)
        if company_tag
        else ""
    )

    location = (
        location_tag.get_text(" ", strip=True)
        if location_tag
        else search_location
    )

    # Egypt-only:
    # remote_only is always False now.
    job_is_remote = (
        "remote" in location.lower()
        or "remote" in title.lower()
    )

    city = location
    country = search_location

    # ========================================================
    # GET LINKEDIN JOB ID
    # ========================================================

    job_id = ""

    data_entity_urn = card.get(
        "data-entity-urn"
    )

    if data_entity_urn:

        match = re.search(
            r'(\d+)$',
            data_entity_urn
        )

        if match:
            job_id = match.group(1)

    if not job_id:

        href_match = re.search(
            r'-(\d+)(?:\?|$)',
            raw_url
        )

        if href_match:
            job_id = href_match.group(1)

    if not job_id:
        return None

    description = ""

    description_tag = card.find(
        "p",
        class_="base-search-card__snippet"
    )

    if description_tag:

        description = description_tag.get_text(
            " ",
            strip=True
        )

    return {
        "job_id": job_id,
        "job_title": title,
        "job_company": company,
        "job_city": city,
        "job_country": country,
        "job_description": description,
        "job_apply_link": apply_url,
        "job_is_remote": job_is_remote,
        "search_location": search_location,
    }

# ============================================================
# LINKEDIN SEARCH
# ============================================================

def search_linkedin(
    keywords: str,
    location: str,
    remote_only: bool = False
) -> list:

    url = (
        "https://www.linkedin.com/jobs-guest/jobs/api/"
        "seeMoreJobPostings/search"
    )

    params = {
        "keywords": keywords,
        "location": location,
        "f_TPR": "r259200",
        "start": 0,
    }

    # IMPORTANT:
    # No f_WT=2.
    # We want Egypt jobs regardless of work mode.

    try:

        response = requests.get(
            url,
            params=params,
            headers=LINKEDIN_HEADERS,
            timeout=15
        )

        response.raise_for_status()

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        cards = soup.find_all(
            "div",
            class_="base-card"
        )

        jobs = []

        for card in cards:

            job = parse_card(
                card,
                location,
                False
            )

            if job:
                jobs.append(job)

        return jobs

    except requests.RequestException as e:

        print(
            f"Search error for '{keywords}' / "
            f"{location}: {e}"
        )

        return []

# ============================================================
# SEEN JOBS
# ============================================================

def load_seen_jobs() -> dict:

    if not os.path.exists(
        SEEN_JOBS_FILE
    ):
        return {}

    try:

        with open(
            SEEN_JOBS_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        if not isinstance(data, dict):
            return {}

        now = datetime.utcnow()
        cleaned = {}

        for job_id, timestamp in data.items():

            try:

                dt = datetime.fromisoformat(
                    timestamp
                )

                if (
                    now - dt
                ).days < SEEN_JOBS_TTL_DAYS:

                    cleaned[job_id] = timestamp

            except (
                ValueError,
                TypeError
            ):
                continue

        return cleaned

    except (
        OSError,
        json.JSONDecodeError
    ):

        return {}


def save_seen_jobs(seen: dict):

    with open(
        SEEN_JOBS_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            seen,
            f,
            indent=2,
            ensure_ascii=False
        )

# ============================================================
# TELEGRAM
# ============================================================

def send_telegram(message: str) -> bool:

    url = (
        f"https://api.telegram.org/bot"
        f"{TELEGRAM_TOKEN}/sendMessage"
    )

    chunks = []

    while len(message) > 4000:

        split_at = message.rfind(
            "\n",
            0,
            4000
        )

        if split_at <= 0:
            split_at = 4000

        chunks.append(
            message[:split_at]
        )

        message = message[
            split_at:
        ].lstrip()

    chunks.append(message)

    for chunk in chunks:

        try:

            response = requests.post(
                url,
                json={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": chunk,
                    "disable_web_page_preview": True,
                },
                timeout=20
            )

            response.raise_for_status()

        except requests.RequestException as e:

            print(
                f"Error sending Telegram message: {e}"
            )

            return False

    return True

# ============================================================
# FORMAT TELEGRAM MESSAGE
# ============================================================

def format_job(
    job: dict,
    rank: int
) -> str:

    title = job.get(
        "job_title",
        "Unknown title"
    )

    company = job.get(
        "job_company",
        "Unknown company"
    )

    city = job.get(
        "job_city",
        ""
    )

    country = job.get(
        "job_country",
        ""
    )

    link = job.get(
        "job_apply_link",
        ""
    )

    score = job.get(
        "_score",
        score_job(job)
    )

    applicants = job.get(
        "_applicants"
    )

    location_text = (
        f"{city}, {country}"
    ).strip(", ")

    if job.get("job_is_remote"):

        work_mode = "Remote"

    elif "hybrid" in (
        job.get(
            "job_title",
            ""
        ).lower()
    ):

        work_mode = "Hybrid"

    else:

        work_mode = "On-site"

    if applicants is None:

        applicant_text = "Applicants: N/A"

    else:

        applicant_text = (
            f"Applicants: {applicants}"
        )

    return (
        f"{rank}. {title}\n"
        f"Company: {company}\n"
        f"Location: {location_text}\n"
        f"Work mode: {work_mode}\n"
        f"Match: {score_label(score)} ({score})\n"
        f"{applicant_text}\n"
        f"{link}"
    )

# ============================================================
# MAIN
# ============================================================

def main():

    check_config()

    seen = load_seen_jobs()

    now_iso = datetime.utcnow().isoformat()

    all_jobs = []

    print(
        "\n--- Egypt Biomedical Job Searches ---"
    )

    # ========================================================
    # SEARCH
    # ========================================================

    for search in LINKEDIN_SEARCHES:

        keywords = search["keywords"]
        location = search["location"]

        print(
            f"Searching: '{keywords}' / "
            f"{location}"
        )

        jobs = search_linkedin(
            keywords,
            location,
            False
        )

        new_jobs = [
            job
            for job in jobs
            if job["job_id"] not in seen
        ]

        print(
            f"Found {len(jobs)} jobs, "
            f"{len(new_jobs)} new"
        )

        all_jobs.extend(new_jobs)

        time.sleep(1)

    print(
        f"\nTotal new jobs: {len(all_jobs)}"
    )

    if not all_jobs:

        message = (
            "No new biomedical jobs "
            "in Egypt since last run."
        )

        if send_telegram(message):

            print(
                "Telegram sent: No new jobs."
            )

        else:

            print(
                "Telegram failed."
            )

        return

    # ========================================================
    # DEDUPLICATION BY LINKEDIN JOB ID
    # ========================================================

    unique_jobs = {}

    for job in all_jobs:

        job_id = job.get("job_id")

        if not job_id:
            continue

        # Keep only ONE copy of every LinkedIn job.
        if job_id not in unique_jobs:

            unique_jobs[job_id] = job

    all_jobs = list(
        unique_jobs.values()
    )

    print(
        f"Job ID deduplication: "
        f"{len(all_jobs)} unique jobs"
    )

    # ========================================================
    # SECONDARY DEDUPLICATION
    # ========================================================

    unique_secondary = {}

    for job in all_jobs:

        key = (
            job.get(
                "job_title",
                ""
            ).strip().lower(),

            job.get(
                "job_company",
                ""
            ).strip().lower(),

            job.get(
                "job_city",
                ""
            ).strip().lower(),
        )

        if key not in unique_secondary:

            unique_secondary[key] = job

    all_jobs = list(
        unique_secondary.values()
    )

    print(
        f"Final deduplication: "
        f"{len(all_jobs)} unique jobs"
    )

    # ========================================================
    # SCORE + APPLICANT COUNT
    # ========================================================

    ranked = enrich_with_competition(
        all_jobs
    )

    # ========================================================
    # TOP 10
    # ========================================================

    top_jobs = ranked[:TOP_N]

    # Extra safety:
    # Make absolutely sure Telegram contains
    # no duplicate LinkedIn Job IDs.

    final_jobs = []
    final_ids = set()

    for job in top_jobs:

        job_id = job.get("job_id")

        if job_id in final_ids:
            continue

        final_ids.add(job_id)
        final_jobs.append(job)

    top_jobs = final_jobs

    print(
        f"Final Telegram jobs: "
        f"{len(top_jobs)}"
    )

    # ========================================================
    # BUILD TELEGRAM MESSAGE
    # ========================================================

    message_parts = [
        "🇪🇬 🧬 Top Biomedical Engineering Jobs in Egypt",
        "",
    ]

    for index, job in enumerate(
        top_jobs,
        start=1
    ):

        message_parts.append(
            format_job(
                job,
                index
            )
        )

        message_parts.append(
            "\n" + ("-" * 30) + "\n"
        )

    message = "\n".join(
        message_parts
    )

    # ========================================================
    # SEND TELEGRAM
    # ========================================================

    telegram_success = send_telegram(
        message
    )

    if telegram_success:

        print(
            f"Telegram sent: "
            f"{len(top_jobs)} top Egypt Biomedical jobs."
        )

        # Only jobs actually sent are marked as seen.

        for job in top_jobs:

            job_id = job.get(
                "job_id"
            )

            if job_id:

                seen[job_id] = now_iso

        save_seen_jobs(seen)

        print(
            f"Saved {len(top_jobs)} jobs "
            f"to seen_jobs.json"
        )

    else:

        print(
            "Telegram failed. "
            "Top jobs were NOT marked as seen."
        )


if __name__ == "__main__":
    main()
