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
    {"keywords": "Field Service Engineer Medical Devices", "location": "Egypt"},
    {"keywords": "Medical Imaging Engineer", "location": "Egypt"},
    {"keywords": "Imaging Engineer Medical", "location": "Egypt"},
    {"keywords": "Healthcare Technology Engineer", "location": "Egypt"},
    {"keywords": "Medical Instrumentation Engineer", "location": "Egypt"},
]

print(
    f"SEARCHES LOADED: {len(LINKEDIN_SEARCHES)}",
    flush=True
)

# ============================================================
# COMPANY SEARCHES DISABLED
# ============================================================

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
# BIOMEDICAL TITLE KEYWORDS
# ============================================================

STRONG_BIOMEDICAL_TITLE_KEYWORDS = [

    "biomedical engineer",
    "biomedical equipment engineer",
    "biomedical service engineer",

    "medical device engineer",
    "medical devices engineer",

    "clinical engineer",

    "medical equipment engineer",
    "medical equipment service engineer",

    "medical imaging engineer",
    "medical imaging",
    "imaging engineer",

    "medical instrumentation engineer",
    "clinical engineering",

]

# ============================================================
# CONDITIONAL BIOMEDICAL TITLE KEYWORDS
# These require medical/biomedical context.
# ============================================================

CONDITIONAL_ENGINEER_KEYWORDS = [

    "field service engineer",
    "service engineer",
    "equipment engineer",
    "application engineer",
    "technical service engineer",
    "maintenance engineer",
    "quality engineer",
    "r&d engineer",
    "research engineer",
]

# ============================================================
# MEDICAL CONTEXT KEYWORDS
# ============================================================

MEDICAL_CONTEXT_KEYWORDS = [

    "biomedical",
    "medical device",
    "medical devices",
    "medical equipment",
    "medical imaging",
    "medical instrumentation",
    "clinical engineering",
    "clinical engineer",
    "healthcare technology",
    "health technology",
    "medical technology",

    "patient monitoring",
    "patient monitor",

    "ventilator",
    "ventilators",

    "dialysis",
    "dialysis machine",

    "infusion pump",
    "infusion pumps",

    "anesthesia",
    "anesthesia machine",

    "ultrasound",
    "mri",
    "magnetic resonance",
    "x-ray",
    "xray",
    "radiology",
    "ct scan",
    "computed tomography",

    "defibrillator",
    "ecg",
    "ekg",
    "eeg",

    "medical laboratory",
    "laboratory equipment",

    "surgical equipment",
    "surgical devices",

    "hospital equipment",
    "hospital devices",

    "diagnostic equipment",
    "diagnostic devices",

    "life support",

    "healthcare",
]

# ============================================================
# STRONG NEGATIVE TITLE KEYWORDS
# These are rejected unless the title also clearly contains
# biomedical/medical-device context.
# ============================================================

NEGATIVE_TITLE_KEYWORDS = [

    "sales engineer",
    "sales executive",
    "sales specialist",
    "sales representative",

    "civil engineer",
    "structural engineer",

    "mechanical engineer",
    "mechanical design engineer",

    "software engineer",
    "software developer",
    "frontend developer",
    "backend developer",
    "full stack",
    "full-stack",

    "network engineer",
    "network administrator",

    "data engineer",

    "devops engineer",

    "cloud engineer",

    "security engineer",
    "cybersecurity",

    "electrical engineer",

    "electronics engineer",

    "automotive engineer",

    "production engineer",

    "industrial engineer",

    "chemical engineer",

    "process engineer",

    "construction engineer",

    "architect",

    "accountant",

    "finance",

    "marketing",

    "human resources",
    "hr specialist",

    "customer service",

    "recruiter",

    "procurement specialist",

]

# ============================================================
# ROLE SCORES
# ============================================================

ROLE_SCORES = {

    "biomedical equipment engineer": 60,
    "biomedical engineer": 58,
    "medical device engineer": 57,
    "medical devices engineer": 57,

    "clinical engineer": 55,
    "clinical engineering": 55,

    "medical equipment engineer": 54,
    "medical equipment service engineer": 54,

    "biomedical service engineer": 53,

    "medical imaging engineer": 52,
    "imaging engineer": 48,

    "medical instrumentation engineer": 50,

    "field service engineer": 38,
    "technical service engineer": 35,
    "service engineer": 34,

    "equipment engineer": 32,
    "application engineer": 28,

    "maintenance engineer": 26,

    "quality engineer": 22,

    "research engineer": 24,
    "r&d engineer": 24,

}

# ============================================================
# SKILL SCORES
# ============================================================

SKILL_SCORES = {

    "biomedical": 20,

    "medical device": 20,
    "medical devices": 20,

    "medical equipment": 18,
    "medical instrumentation": 18,

    "clinical engineering": 18,
    "clinical engineer": 18,

    "medical technology": 15,
    "healthcare technology": 15,
    "health technology": 15,

    "medical imaging": 18,
    "imaging": 10,

    "mri": 12,
    "ultrasound": 12,
    "x-ray": 12,
    "xray": 12,
    "ct scan": 12,
    "computed tomography": 12,
    "radiology": 10,

    "patient monitoring": 12,
    "patient monitor": 12,

    "ventilator": 10,
    "dialysis": 10,
    "infusion pump": 10,
    "anesthesia": 10,
    "defibrillator": 10,
    "ecg": 8,
    "eeg": 8,

    "surgical equipment": 10,
    "diagnostic equipment": 10,
    "hospital equipment": 10,

    "electronics": 5,
    "electrical": 5,

    "embedded systems": 8,
    "embedded": 6,

    "control systems": 6,

    "signal processing": 10,

    "python": 4,
    "matlab": 6,

    "machine learning": 6,
    "deep learning": 6,

    "data analysis": 5,

    "field service": 8,
    "maintenance": 6,
    "troubleshooting": 8,
    "installation": 6,
    "calibration": 8,

    "quality assurance": 6,
    "regulatory affairs": 8,
    "regulatory": 6,

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
# BIOMEDICAL FILTER
# ============================================================

def is_biomedical_job(job: dict) -> bool:

    title = (
        job.get("job_title") or ""
    ).lower().strip()

    description = (
        job.get("job_description") or ""
    ).lower()

    company = (
        job.get("job_company") or ""
    ).lower()

    # --------------------------------------------------------
    # Combine available information
    # --------------------------------------------------------

    context = (
        title
        + " "
        + description
        + " "
        + company
    )

    # --------------------------------------------------------
    # Reject clearly unrelated job titles
    # --------------------------------------------------------

    has_strong_biomedical_title = any(
        keyword in title
        for keyword in STRONG_BIOMEDICAL_TITLE_KEYWORDS
    )

    negative_match = any(
        keyword in title
        for keyword in NEGATIVE_TITLE_KEYWORDS
    )

    if negative_match and not has_strong_biomedical_title:

        return False

    # --------------------------------------------------------
    # Strong biomedical title = ACCEPT
    # --------------------------------------------------------

    if has_strong_biomedical_title:

        return True

    # --------------------------------------------------------
    # Conditional engineering titles
    # Require medical context.
    # --------------------------------------------------------

    has_conditional_engineer_title = any(
        keyword in title
        for keyword in CONDITIONAL_ENGINEER_KEYWORDS
    )

    if has_conditional_engineer_title:

        medical_context_count = sum(
            1
            for keyword in MEDICAL_CONTEXT_KEYWORDS
            if keyword in context
        )

        # At least one strong medical context
        if medical_context_count >= 1:

            return True

    # --------------------------------------------------------
    # Additional protection:
    # If title has biomedical/medical equipment/device
    # language anywhere, accept.
    # --------------------------------------------------------

    if (
        "biomedical" in title
        or "medical device" in title
        or "medical equipment" in title
        or "clinical engineer" in title
    ):

        return True

    # --------------------------------------------------------
    # Otherwise reject
    # --------------------------------------------------------

    return False

# ============================================================
# JOB SCORING
# ============================================================

def score_job(job: dict) -> int:

    title = (
        job.get("job_title") or ""
    ).lower()

    desc = (
        job.get("job_description") or ""
    )[:1500].lower()

    city = (
        job.get("job_city") or ""
    ).lower()

    country = (
        job.get("job_country") or ""
    ).lower()

    score = 0

    # --------------------------------------------------------
    # Role score
    # --------------------------------------------------------

    for keyword, points in ROLE_SCORES.items():

        if keyword in title:

            score += points
            break

    # --------------------------------------------------------
    # Skill score
    # --------------------------------------------------------

    text = (
        title
        + " "
        + desc
    )

    skill_points = sum(
        points
        for keyword, points in SKILL_SCORES.items()
        if keyword in text
    )

    score += min(
        skill_points,
        45
    )

    # --------------------------------------------------------
    # Location score
    # --------------------------------------------------------

    location_text = (
        city
        + " "
        + country
    )

    for location, points in LOCATION_SCORES.items():

        if location in location_text:

            score += min(
                points,
                20
            )

            break

    # --------------------------------------------------------
    # Hybrid
    # --------------------------------------------------------

    if (
        "hybrid" in title
        or "hybrid" in desc[:500]
    ):

        score += 4

    return score


def score_label(score: int) -> str:

    if score >= 70:
        return "Excellent match"

    if score >= 55:
        return "Strong match"

    if score >= 40:
        return "Good match"

    return "Possible match"

# ============================================================
# APPLICANT COUNT
# ============================================================

def fetch_applicant_count(url: str) -> int | None:

    if not url:
        return None

    try:

        response = requests.get(
            url,
            headers=LINKEDIN_HEADERS,
            timeout=10
        )

        if response.status_code != 200:
            return None

        match = re.search(
            r'(\d[\d,]*)\+?\s*'
            r'(?:applicants|people clicked apply)',
            response.text,
            re.I
        )

        if not match:
            return None

        count = (
            match.group(1)
            .replace(",", "")
            .strip()
        )

        if not count.isdigit():
            return None

        return int(count)

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

    top = ranked[
        :APPLICANT_FETCH_LIMIT
    ]

    rest = ranked[
        APPLICANT_FETCH_LIMIT:
    ]

    for job in top:

        applicants = fetch_applicant_count(
            job.get("job_apply_link")
        )

        job["_applicants"] = applicants

        job["_score"] = (
            score_job(job)
            + applicant_bonus(
                applicants
            )
        )

        time.sleep(0.3)

    for job in rest:

        job["_applicants"] = None

        job["_score"] = score_job(job)

    return sorted(
        top + rest,
        key=lambda job: job["_score"],
        reverse=True
    )

# ============================================================
# LINKEDIN JOB PARSER
# ============================================================

def parse_card(
    card,
    search_location: str
) -> dict | None:

    link_tag = card.find(
        "a",
        class_="base-card__full-link"
    )

    if not link_tag:
        return None

    raw_url = link_tag.get(
        "href",
        ""
    )

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
        title_tag.get_text(
            " ",
            strip=True
        )
        if title_tag
        else ""
    )

    company = (
        company_tag.get_text(
            " ",
            strip=True
        )
        if company_tag
        else ""
    )

    location = (
        location_tag.get_text(
            " ",
            strip=True
        )
        if location_tag
        else search_location
    )

    # --------------------------------------------------------
    # Job ID
    # --------------------------------------------------------

    job_id = ""

    data_entity_urn = card.get(
        "data-entity-urn"
    )

    if data_entity_urn:

        match = re.search(
            r"(\d+)$",
            data_entity_urn
        )

        if match:
            job_id = match.group(1)

    if not job_id:

        href_match = re.search(
            r"-(\d+)(?:\?|$)",
            raw_url
        )

        if href_match:
            job_id = href_match.group(1)

    if not job_id:
        return None

    # --------------------------------------------------------
    # Description
    # --------------------------------------------------------

    description = ""

    description_tag = card.find(
        "p",
        class_="base-search-card__snippet"
    )

    if description_tag:

        description = (
            description_tag.get_text(
                " ",
                strip=True
            )
        )

    # --------------------------------------------------------
    # Remote / hybrid detection
    # This DOES NOT search outside Egypt.
    # It only describes the Egyptian job's work mode.
    # --------------------------------------------------------

    location_lower = location.lower()
    title_lower = title.lower()

    is_remote = (
        "remote" in location_lower
        or "remote" in title_lower
    )

    return {

        "job_id": job_id,

        "job_title": title,

        "job_company": company,

        "job_city": location,

        "job_country": "Egypt",

        "job_description": description,

        "job_apply_link": apply_url,

        "job_is_remote": is_remote,

        "search_location": search_location,

    }

# ============================================================
# LINKEDIN SEARCH
# ============================================================

def search_linkedin(
    keywords: str,
    location: str
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
    # Search ALL Egypt jobs.

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
                location
            )

            if not job:
                continue

            # ------------------------------------------------
            # IMPORTANT:
            # Biomedical filter happens HERE.
            # ------------------------------------------------

            if not is_biomedical_job(job):

                print(
                    f"Rejected non-biomedical job: "
                    f"{job.get('job_title')}",
                    flush=True
                )

                continue

            jobs.append(job)

        return jobs

    except requests.RequestException as error:

        print(
            f"Search error for "
            f"'{keywords}' / {location}: "
            f"{error}",
            flush=True
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
        ) as file:

            data = json.load(file)

        if not isinstance(
            data,
            dict
        ):

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


def save_seen_jobs(
    seen: dict
):

    with open(
        SEEN_JOBS_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            seen,
            file,
            indent=2,
            ensure_ascii=False
        )

# ============================================================
# TELEGRAM
# ============================================================

def send_telegram(
    message: str
) -> bool:

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

                    "chat_id":
                        TELEGRAM_CHAT_ID,

                    "text":
                        chunk,

                    "disable_web_page_preview":
                        True,

                },

                timeout=20
            )

            response.raise_for_status()

        except requests.RequestException as error:

            print(
                f"Error sending Telegram message: "
                f"{error}",
                flush=True
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
        "Egypt"
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

    # --------------------------------------------------------
    # Work mode
    # --------------------------------------------------------

    title_lower = title.lower()
    description_lower = (
        job.get(
            "job_description",
            ""
        ).lower()
    )

    if job.get("job_is_remote"):

        work_mode = "Remote"

    elif (
        "hybrid" in title_lower
        or "hybrid" in description_lower[:500]
    ):

        work_mode = "Hybrid"

    else:

        work_mode = "On-site"

    # --------------------------------------------------------
    # Applicants
    # --------------------------------------------------------

    if applicants is None:

        applicant_text = (
            "Applicants: N/A"
        )

    else:

        applicant_text = (
            f"Applicants: {applicants}"
        )

    return (

        f"{rank}. {title}\n"

        f"Company: {company}\n"

        f"Location: {city}, {country}\n"

        f"Work mode: {work_mode}\n"

        f"Match: "
        f"{score_label(score)} "
        f"({score})\n"

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
        "\n--- Egypt Biomedical Job Searches ---",
        flush=True
    )

    # ========================================================
    # SEARCH ALL EGYPT QUERIES
    # ========================================================

    for search in LINKEDIN_SEARCHES:

        keywords = search[
            "keywords"
        ]

        location = search[
            "location"
        ]

        print(
            f"Searching: "
            f"'{keywords}' / {location}",
            flush=True
        )

        jobs = search_linkedin(
            keywords,
            location
        )

        new_jobs = [

            job

            for job in jobs

            if job["job_id"]
            not in seen

        ]

        print(
            f"Found {len(jobs)} "
            f"Biomedical jobs, "
            f"{len(new_jobs)} new",
            flush=True
        )

        all_jobs.extend(
            new_jobs
        )

        time.sleep(1)

    print(
        f"\nTotal new biomedical jobs: "
        f"{len(all_jobs)}",
        flush=True
    )

    # ========================================================
    # NO NEW JOBS
    # ========================================================

    if not all_jobs:

        message = (
            "🇪🇬 🧬 No new biomedical "
            "engineering jobs in Egypt "
            "since last run."
        )

        if send_telegram(
            message
        ):

            print(
                "Telegram sent: "
                "No new jobs.",
                flush=True
            )

        else:

            print(
                "Telegram failed.",
                flush=True
            )

        return

    # ========================================================
    # DEDUPLICATION #1
    # LinkedIn Job ID
    # ========================================================

    unique_by_id = {}

    for job in all_jobs:

        job_id = job.get(
            "job_id"
        )

        if not job_id:
            continue

        if job_id not in unique_by_id:

            unique_by_id[
                job_id
            ] = job

    all_jobs = list(
        unique_by_id.values()
    )

    print(
        f"Job ID deduplication: "
        f"{len(all_jobs)} unique jobs",
        flush=True
    )

    # ========================================================
    # DEDUPLICATION #2
    # Title + Company + Location
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

            unique_secondary[
                key
            ] = job

    all_jobs = list(
        unique_secondary.values()
    )

    print(
        f"Final deduplication: "
        f"{len(all_jobs)} unique jobs",
        flush=True
    )

    # ========================================================
    # SCORE + APPLICANTS
    # ========================================================

    ranked = enrich_with_competition(
        all_jobs
    )

    # ========================================================
    # TOP 10
    # ========================================================

    top_jobs = ranked[
        :TOP_N
    ]

    # ========================================================
    # FINAL DUPLICATE SAFETY
    # ========================================================

    final_jobs = []

    final_ids = set()

    for job in top_jobs:

        job_id = job.get(
            "job_id"
        )

        if not job_id:
            continue

        if job_id in final_ids:
            continue

        final_ids.add(
            job_id
        )

        final_jobs.append(
            job
        )

    top_jobs = final_jobs

    print(
        f"Final Telegram jobs: "
        f"{len(top_jobs)}",
        flush=True
    )

    # ========================================================
    # TELEGRAM MESSAGE
    # ========================================================

    message_parts = [

        "🇪🇬 🧬 "
        "Top Biomedical Engineering Jobs in Egypt",

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

            "\n"
            + ("-" * 30)
            + "\n"

        )

    message = "\n".join(
        message_parts
    )

    # ========================================================
    # SEND
    # ========================================================

    telegram_success = send_telegram(
        message
    )

    if telegram_success:

        print(
            f"Telegram sent: "
            f"{len(top_jobs)} top "
            f"Egypt Biomedical jobs.",
            flush=True
        )

        # ----------------------------------------------------
        # ONLY SENT JOBS BECOME SEEN
        # ----------------------------------------------------

        for job in top_jobs:

            job_id = job.get(
                "job_id"
            )

            if job_id:

                seen[
                    job_id
                ] = now_iso

        save_seen_jobs(
            seen
        )

        print(
            f"Saved {len(top_jobs)} jobs "
            f"to seen_jobs.json",
            flush=True
        )

    else:

        print(
            "Telegram failed. "
            "Top jobs were NOT marked "
            "as seen.",
            flush=True
        )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    main()
