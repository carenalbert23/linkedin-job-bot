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

    # -------------------------
    # Title relevance
    # -------------------------

    for kw, pts in ROLE_SCORES.items():

        if kw in title:

            score += pts

            break

    # -------------------------
    # Technical skills
    # -------------------------

    text = title + " " + desc

    skill_pts = sum(
        pts
        for kw, pts in SKILL_SCORES.items()
        if kw in text
    )

    score += min(
        skill_pts,
        35
    )

    # -------------------------
    # Location
    # -------------------------

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

            score += min(
                pts,
                16
            )

            break

    # -------------------------
    # Work mode
    # -------------------------

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

    top = ranked[
        :APPLICANT_FETCH_LIMIT
    ]

    rest = ranked[
        APPLICANT_FETCH_LIMIT:
    ]

    for job in top:

        count = fetch_applicant_count(
            job.get(
                "job_apply_link"
            )
        )

        job["_applicants"] = count

        job["_score"] = (
            score_job(job)
            + applicant_bonus(count)
        )

        time.sleep(0.3)

    for job in rest:

        job["_applicants"] = None

        job["_score"] = score_job(
            job
        )

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

    raw_url = link_tag.get(
        "href",
        ""
    )

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
        title_tag.get_text(
            strip=True
        )
        if title_tag
        else ""
    ).strip()

    company = (
        company_tag.get_text(
            strip=True
        )
        if company_tag
        else ""
    ).strip()

    location = (
        loc_tag.get_text(
            strip=True
        )
        if loc_tag
        else search_location
    ).strip()

    return {

        "job_id": job_id,

        "job_title": title,

        "employer_name": company,

        "job_city": location,

        "job_country": search_location,

        "job_is_remote": (
            remote_only
            or search_location != "Egypt"
        ),

        "job_apply_link": apply_url,

        "job_description": "",

        "apply_options": [
            {
                "apply_link": apply_url,
                "is_direct": False,
                "publisher": "LinkedIn"
            }
        ],
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
        "https://www.linkedin.com/jobs-guest/"
        "jobs/api/seeMoreJobPostings/search"
    )

    params = {

        "keywords": keywords,

        # Last 3 days
        "f_TPR": "r259200",

        "start": 0,
    }

    # Egypt:
    # no f_WT -> On-site + Hybrid + Remote
    #
    # Outside Egypt:
    # f_WT=2 -> Remote only

    if (
        remote_only
        or location != "Egypt"
    ):

        params["f_WT"] = "2"

    if (
        remote_only
        and location == "Worldwide"
    ):

        params["location"] = ""

    else:

        params["location"] = location

    try:

        # Delay to reduce 429 errors
        time.sleep(2)

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
                location,
                remote_only=(
                    remote_only
                    or location != "Egypt"
                )
            )

            if job:
                jobs.append(job)

        return jobs

    except requests.RequestException as e:

        print(
            f"Warning: LinkedIn search failed "
            f"for '{keywords}' / {location}: {e}"
        )

        return []


# ============================================================
# DEDUPLICATION
# ============================================================

def deduplicate_jobs(
    jobs: list
) -> list:

    unique_jobs = []

    seen_keys = set()

    for job in jobs:

        title = (
            job.get("job_title")
            or ""
        ).strip().lower()

        company = (
            job.get("employer_name")
            or ""
        ).strip().lower()

        city = (
            job.get("job_city")
            or ""
        ).strip().lower()

        country = (
            job.get("job_country")
            or ""
        ).strip().lower()

        key = (
            title,
            company,
            city,
            country
        )

        if key in seen_keys:
            continue

        seen_keys.add(key)

        unique_jobs.append(job)

    return unique_jobs


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

    except (
        json.JSONDecodeError,
        OSError
    ):

        return {}

    cutoff = (
        datetime.now()
        - timedelta(
            days=SEEN_JOBS_TTL_DAYS
        )
    ).isoformat()

    return {
        job_id: timestamp
        for job_id, timestamp
        in data.items()
        if timestamp >= cutoff
    }


def save_seen_jobs(
    seen: dict
):

    with open(
        SEEN_JOBS_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            seen,
            f,
            ensure_ascii=False,
            indent=2
        )


# ============================================================
# TELEGRAM
# ============================================================

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
        job.get(
            "job_title"
        )
        or "N/A"
    )

    company = esc(
        job.get(
            "employer_name"
        )
        or "N/A"
    )

    location = esc(
        job.get(
            "job_city"
        )
        or job.get(
            "job_country"
        )
        or "Unknown"
    )

    is_remote = job.get(
        "job_is_remote",
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
        job.get("job_title")
        or ""
    ).lower()

    location_lower = (
        location or ""
    ).lower()

    if (
        "hybrid" in title_lower
        or "hybrid" in location_lower
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
        job.get(
            "job_apply_link"
        )
        or ""
    )

    safe_url = (
        apply_url
        .replace("&", "&amp;")
    )

    if safe_url:

        apply_part = (
            f' | <a href="{safe_url}">'
            "Apply on LinkedIn</a>"
        )

    else:

        apply_part = ""

    if applicants is None:

        competition = ""

    elif applicants <= 25:

        competition = (
            f" | {applicants} applicants "
            "(low competition)"
        )

    else:

        competition = (
            f" | {applicants} applicants"
        )

    return (
        f"<b>#{rank} {title}</b>\n"
        f"{company} | {work_mode}\n"
        f"<i>{score_label(score)} "
        f"({score} pts)</i>"
        f"{competition}"
        f"{apply_part}"
    )


def send_telegram(
    text: str
):

    url = (
        "https://api.telegram.org/"
        f"bot{TELEGRAM_TOKEN}/sendMessage"
    )

    # Telegram message limit
    chunks = []

    current = ""

    for line in text.split("\n"):

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
                timeout=15
            )

            resp.raise_for_status()

        except requests.RequestException as e:

            print(
                f"Error sending Telegram "
                f"message: {e}"
            )


# ============================================================
# TOP 10 SELECTION
# ============================================================

def select_top_jobs(
    jobs: list,
    limit: int = TOP_N
) -> list:

    """
    Select highest scoring jobs.

    Maximum 3 jobs from the same search.
    If fewer than 10 suitable jobs exist,
    fill remaining positions from the
    highest-scoring remaining jobs.
    """

    top_jobs = []

    search_counts = {}

    selected_ids = set()

    for job in jobs:

        search_key = (
            job.get(
                "_search_keywords",
                ""
            ),
            job.get(
                "_search_location",
                ""
            )
        )

        count = search_counts.get(
            search_key,
            0
        )

        if count >= 3:
            continue

        top_jobs.append(job)

        selected_ids.add(
            job.get("job_id")
        )

        search_counts[
            search_key
        ] = count + 1

        if len(top_jobs) >= limit:
            break

    # Fill remaining positions
    # if necessary.
    if len(top_jobs) < limit:

        for job in jobs:

            job_id = job.get(
                "job_id"
            )

            if job_id in selected_ids:
                continue

            top_jobs.append(job)

            selected_ids.add(
                job_id
            )

            if len(top_jobs) >= limit:
                break

    return top_jobs


# ============================================================
# MAIN
# ============================================================

def main():

    check_config()

    print(
        f"[{datetime.now().strftime('%H:%M:%S')}] "
        "Starting LinkedIn job search..."
    )

    seen = load_seen_jobs()

    this_run_ids = set()

    all_jobs = []

    print(
        "--- Biomedical job searches ---"
    )

    # ----------------------------------------
    # Search LinkedIn
    # ----------------------------------------

    for search in LINKEDIN_SEARCHES:

        keywords = search[
            "keywords"
        ]

        location = search[
            "location"
        ]

        remote_only = search.get(
            "remote_only",
            False
        )

        jobs = search_linkedin(
            keywords,
            location,
            remote_only
        )

        kept = 0

        for job in jobs:

            job_id = job.get(
                "job_id"
            )

            # Ignore:
            # - invalid jobs
            # - previously seen jobs
            # - duplicates within same run

            if (
                not job_id
                or job_id in seen
                or job_id in this_run_ids
            ):

                continue

            this_run_ids.add(
                job_id
            )

            # Keep search information
            # for balanced Top 10.

            job[
                "_search_keywords"
            ] = keywords

            job[
                "_search_location"
            ] = location

            all_jobs.append(
                job
            )

            kept += 1

        print(
            f"  '{keywords}' / "
            f"{location} -> "
            f"{kept} new"
        )

    print(
        f"Total new jobs: "
        f"{len(all_jobs)}"
    )

    # ----------------------------------------
    # No new jobs
    # ----------------------------------------

    if not all_jobs:

        send_telegram(
            "<b>Daily Biomedical Job Report - "
            + datetime.now().strftime(
                "%b %d, %Y"
            )
            + "</b>\n"
            "No new LinkedIn jobs since "
            "last run. Check back tomorrow!"
        )

    # ----------------------------------------
    # We have jobs
    # ----------------------------------------

    else:

        before_dedup = len(
            all_jobs
        )

        all_jobs = deduplicate_jobs(
            all_jobs
        )

        after_dedup = len(
            all_jobs
        )

        print(
            f"Deduplication: "
            f"{before_dedup} -> "
            f"{after_dedup} unique jobs"
        )

        # Add applicant / competition score.

        all_jobs = (
            enrich_with_competition(
                all_jobs
            )
        )

        # Select Top 10.

        top_jobs = select_top_jobs(
            all_jobs,
            TOP_N
        )

        date_str = datetime.now().strftime(
            "%b %d, %Y"
        )

        lines = [

            (
                f"<b>Daily Biomedical Job "
                f"Report - {date_str}</b>\n"
            ),

            (
                "Remote + Hybrid + On-site "
                "in Egypt | Remote outside "
                "Egypt | LinkedIn only\n"
            ),

            "<b>-- Top 10 Biomedical "
            "Job Matches --</b>",

            ""
        ]

        for rank, job in enumerate(
            top_jobs,
            1
        ):

            lines.append(
                format_job(
                    rank,
                    job
                )
            )

            lines.append("")

        send_telegram(
            "\n".join(lines)
        )

        print(
            f"Telegram sent: "
            f"{len(top_jobs)} "
            "top Biomedical jobs."
        )

    # ----------------------------------------
    # Save seen jobs
    # ----------------------------------------

    now_iso = (
        datetime.now().isoformat()
    )

    for job_id in this_run_ids:

        seen[job_id] = now_iso

    save_seen_jobs(
        seen
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()
