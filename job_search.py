import os
import re
import json
import html
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta


# ============================================================
# CONFIG
# ============================================================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

SEEN_JOBS_FILE = "seen_jobs.json"

# Keep jobs in memory for 30 days
SEEN_JOBS_TTL_DAYS = 30

# ALWAYS TRY TO SEND TOP 10
TOP_N = 10

# Applicant count only for final jobs
APPLICANT_FETCH_LIMIT = 10

# Search jobs posted during the last 30 days
LINKEDIN_TIME_FILTER = "r2592000"

# Number of LinkedIn result pages to check
MAX_SEARCH_PAGES = 5

# LinkedIn normally uses 25 jobs per page
PAGE_SIZE = 25


LINKEDIN_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/142.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,*/*;q=0.8"
    ),
}


# ============================================================
# LINKEDIN SEARCHES - EGYPT
# ============================================================

LINKEDIN_SEARCHES = [

    "Biomedical Engineer",
    "Biomedical",
    "Biomedical Equipment Engineer",
    "Biomedical Service Engineer",
    "Medical Device Engineer",
    "Medical Devices",
    "Clinical Engineer",
    "Clinical Engineering",
    "Medical Equipment Engineer",
    "Medical Equipment",
    "Medical Imaging Engineer",
    "Imaging Engineer",
    "Field Service Engineer Medical Devices",
    "Field Service Engineer",
    "Service Engineer Medical",
    "Healthcare Technology Engineer",
    "Healthcare Engineer",
    "Medical Technology",
    "Medical Instrumentation Engineer",
]


# ============================================================
# BIOMEDICAL FILTER
# ============================================================

STRONG_BIOMEDICAL_TITLE_KEYWORDS = [
    "biomedical",
    "medical device",
    "medical devices",
    "clinical engineer",
    "clinical engineering",
    "medical equipment",
    "medical imaging",
    "imaging engineer",
    "medical instrumentation",
    "healthcare technology",
    "medical technology",
]


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


MEDICAL_CONTEXT_KEYWORDS = [
    "biomedical",
    "medical device",
    "medical devices",
    "medical equipment",
    "medical imaging",
    "medical instrumentation",
    "clinical engineering",
    "healthcare technology",
    "medical technology",
    "patient monitoring",
    "ventilator",
    "dialysis",
    "infusion pump",
    "anesthesia",
    "ultrasound",
    "mri",
    "x-ray",
    "xray",
    "radiology",
    "ct scanner",
    "computed tomography",
    "defibrillator",
    "ecg",
    "eeg",
    "medical lab",
    "medical laboratory",
    "surgical equipment",
    "surgical devices",
    "hospital equipment",
    "hospital devices",
    "diagnostic equipment",
    "diagnostic devices",
    "life support",
    "laboratory equipment",
    "patient care",
    "healthcare equipment",
]


NEGATIVE_TITLE_KEYWORDS = [
    "civil engineer",
    "structural engineer",
    "mechanical engineer",
    "software engineer",
    "network engineer",
    "data engineer",
    "devops engineer",
    "cloud engineer",
    "security engineer",
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
    "recruiter",
    "procurement",
]


def is_biomedical_job(job):

    title = (
        job.get("title") or ""
    ).lower().strip()

    description = (
        job.get("description") or ""
    ).lower()

    company = (
        job.get("company") or ""
    ).lower()

    context = (
        f"{title} "
        f"{description} "
        f"{company}"
    )

    # --------------------------------------------------------
    # Reject unrelated titles
    # --------------------------------------------------------

    for keyword in NEGATIVE_TITLE_KEYWORDS:

        if keyword in title:
            return False

    # --------------------------------------------------------
    # Strong biomedical title
    # --------------------------------------------------------

    for keyword in STRONG_BIOMEDICAL_TITLE_KEYWORDS:

        if keyword in title:
            return True

    # --------------------------------------------------------
    # Conditional engineering titles
    # --------------------------------------------------------

    has_conditional_title = any(
        keyword in title
        for keyword in CONDITIONAL_ENGINEER_KEYWORDS
    )

    if has_conditional_title:

        has_medical_context = any(
            keyword in context
            for keyword in MEDICAL_CONTEXT_KEYWORDS
        )

        if has_medical_context:
            return True

    return False


# ============================================================
# SCORING
# ============================================================

ROLE_SCORES = {

    "biomedical engineer": 50,
    "biomedical equipment": 48,
    "biomedical service": 48,

    "clinical engineer": 45,
    "medical equipment engineer": 45,
    "medical imaging engineer": 44,
    "medical instrumentation": 44,

    "field service engineer": 42,
    "imaging engineer": 40,
    "equipment engineer": 40,

    "medical device": 38,
    "medical devices": 38,

    "clinical": 35,

    "healthcare technology": 34,
    "health technology": 34,
    "medical technology": 34,

    "field service": 32,
    "medical imaging": 32,

    "service engineer": 30,
    "technical service engineer": 30,

    "maintenance engineer": 26,
    "research engineer": 24,
    "r&d engineer": 24,
}


LOCATION_SCORES = {

    "egypt": 30,
    "cairo": 25,
    "giza": 24,
    "alexandria": 22,
    "new cairo": 24,
    "6th of october": 22,
    "new heliopolis": 24,
}


SKILL_SCORES = {

    "ultrasound": 12,
    "mri": 12,
    "x-ray": 12,
    "xray": 12,
    "ct": 10,
    "radiology": 12,

    "ecg": 10,
    "eeg": 10,

    "patient monitoring": 12,
    "ventilator": 12,
    "dialysis": 12,
    "infusion pump": 12,
    "anesthesia": 12,
    "defibrillator": 12,

    "medical devices": 15,
    "medical equipment": 15,
    "medical imaging": 15,
    "clinical engineering": 15,

    "biomedical": 20,
}


def calculate_score(job):

    title = (
        job.get("title") or ""
    ).lower()

    description = (
        job.get("description") or ""
    ).lower()

    company = (
        job.get("company") or ""
    ).lower()

    location = (
        job.get("location") or ""
    ).lower()

    score = 0

    # Role
    for keyword, points in ROLE_SCORES.items():

        if keyword in title:
            score += points

    # Location
    for keyword, points in LOCATION_SCORES.items():

        if keyword in location:
            score += points

    # Medical skills/context
    full_text = (
        f"{title} "
        f"{description} "
        f"{company}"
    )

    for keyword, points in SKILL_SCORES.items():

        if keyword in full_text:
            score += points

    return score


# ============================================================
# SEEN JOBS
# ============================================================

def load_seen_jobs():

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

        if isinstance(data, dict):
            return data

        return {}

    except Exception as e:

        print(
            f"Could not load seen jobs: {e}"
        )

        return {}


def save_seen_jobs(seen_jobs):

    with open(
        SEEN_JOBS_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            seen_jobs,
            f,
            ensure_ascii=False,
            indent=2
        )


def cleanup_seen_jobs(seen_jobs):

    cutoff = (
        datetime.utcnow()
        - timedelta(
            days=SEEN_JOBS_TTL_DAYS
        )
    )

    cleaned = {}

    for job_id, timestamp in seen_jobs.items():

        try:

            dt = datetime.fromisoformat(
                timestamp
            )

            if dt >= cutoff:

                cleaned[
                    job_id
                ] = timestamp

        except Exception:

            cleaned[
                job_id
            ] = timestamp

    return cleaned


# ============================================================
# JOB ID
# ============================================================

def extract_job_id(url):

    if not url:
        return None

    patterns = [
        r"/view/(\d+)",
        r"currentJobId=(\d+)",
        r"jobId=(\d+)",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            url
        )

        if match:
            return match.group(1)

    return None


# ============================================================
# PARSE CARD
# ============================================================

def parse_card(card):

    try:

        title_element = card.select_one(
            "h3.base-search-card__title"
        )

        company_element = card.select_one(
            "h4.base-search-card__subtitle"
        )

        location_element = card.select_one(
            "span.job-search-card__location"
        )

        link_element = card.select_one(
            "a.base-card__full-link"
        )

        title = (
            title_element.get_text(
                " ",
                strip=True
            )
            if title_element
            else ""
        )

        company = (
            company_element.get_text(
                " ",
                strip=True
            )
            if company_element
            else ""
        )

        location = (
            location_element.get_text(
                " ",
                strip=True
            )
            if location_element
            else "Egypt"
        )

        url = (
            link_element.get(
                "href",
                ""
            ).strip()
            if link_element
            else ""
        )

        url = url.split("?")[0]

        job_id = extract_job_id(
            url
        )

        if not job_id:

            entity_urn = card.get(
                "data-entity-urn",
                ""
            )

            match = re.search(
                r"job:(\d+)",
                entity_urn
            )

            if match:
                job_id = match.group(1)

        if not title:
            return None

        return {
            "id": job_id,
            "title": title,
            "company": company,
            "location": location,
            "city": location,
            "country": "Egypt",
            "url": url,
            "description": "",
            "applicants": None,
            "score": 0,
        }

    except Exception as e:

        print(
            f"Error parsing job card: {e}"
        )

        return None


# ============================================================
# LINKEDIN SEARCH - MULTIPLE PAGES
# ============================================================

def search_linkedin(
    keywords,
    location
):

    base_url = (
        "https://www.linkedin.com/jobs-guest/"
        "jobs/api/seeMoreJobPostings/search"
    )

    all_jobs = []

    print(
        f"\nSearching LinkedIn: "
        f"{keywords}"
    )

    # --------------------------------------------------------
    # Search multiple pages
    # --------------------------------------------------------

    for page in range(
        MAX_SEARCH_PAGES
    ):

        start = (
            page *
            PAGE_SIZE
        )

        params = {
            "keywords": keywords,
            "location": location,

            # LAST 30 DAYS
            "f_TPR": LINKEDIN_TIME_FILTER,

            "start": start,
        }

        print(
            f"  Page {page + 1} "
            f"(start={start})"
        )

        try:

            response = requests.get(
                base_url,
                params=params,
                headers=LINKEDIN_HEADERS,
                timeout=20,
            )

            print(
                f"  HTTP status: "
                f"{response.status_code}"
            )

            if response.status_code != 200:

                print(
                    "  LinkedIn request failed."
                )

                break

            soup = BeautifulSoup(
                response.text,
                "html.parser"
            )

            cards = soup.select(
                "li.jobs-search__results-list"
            )

            if not cards:

                cards = soup.select(
                    "li.base-card"
                )

            if not cards:

                cards = soup.select(
                    "div.base-card"
                )

            print(
                f"  Raw cards: "
                f"{len(cards)}"
            )

            # If page is empty, stop pagination
            if not cards:

                print(
                    "  No more cards. "
                    "Stopping pagination."
                )

                break

            page_jobs = []

            for card in cards:

                job = parse_card(
                    card
                )

                if not job:
                    continue

                if not is_biomedical_job(
                    job
                ):

                    continue

                job["score"] = (
                    calculate_score(
                        job
                    )
                )

                page_jobs.append(
                    job
                )

            print(
                f"  Biomedical jobs "
                f"accepted: {len(page_jobs)}"
            )

            all_jobs.extend(
                page_jobs
            )

            # If fewer than 25 cards were returned,
            # this is probably the final page.
            if len(cards) < PAGE_SIZE:

                print(
                    "  Last page reached."
                )

                break

        except Exception as e:

            print(
                f"  Search error: {e}"
            )

            break

    # --------------------------------------------------------
    # Deduplicate this search
    # --------------------------------------------------------

    all_jobs = deduplicate_jobs(
        all_jobs
    )

    print(
        f"Total biomedical jobs "
        f"from '{keywords}': "
        f"{len(all_jobs)}"
    )

    return all_jobs


# ============================================================
# APPLICANTS
# ============================================================

def fetch_applicant_count(url):

    if not url:
        return None

    try:

        response = requests.get(
            url,
            headers=LINKEDIN_HEADERS,
            timeout=10,
        )

        if response.status_code != 200:
            return None

        match = re.search(
            r"(\d[\d,]*)\s+applicants?",
            response.text,
            re.IGNORECASE,
        )

        if match:

            return int(
                match.group(1).replace(
                    ",",
                    ""
                )
            )

        return None

    except Exception:

        return None


# ============================================================
# DEDUPLICATION
# ============================================================

def deduplicate_jobs(jobs):

    unique_jobs = []

    seen_ids = set()
    seen_secondary = set()

    for job in jobs:

        job_id = job.get(
            "id"
        )

        # ----------------------------------------------------
        # Primary ID
        # ----------------------------------------------------

        if job_id:

            if job_id in seen_ids:
                continue

            seen_ids.add(
                job_id
            )

        # ----------------------------------------------------
        # Secondary identity
        # ----------------------------------------------------

        secondary_key = (
            (
                job.get("title")
                or ""
            ).lower().strip(),

            (
                job.get("company")
                or ""
            ).lower().strip(),

            (
                job.get("city")
                or ""
            ).lower().strip(),
        )

        if secondary_key in seen_secondary:
            continue

        seen_secondary.add(
            secondary_key
        )

        unique_jobs.append(
            job
        )

    return unique_jobs


# ============================================================
# TELEGRAM
# ============================================================

def escape_telegram(text):

    if text is None:
        return ""

    return html.escape(
        str(text)
    )


def send_telegram(message):

    if not TELEGRAM_TOKEN:

        print(
            "ERROR: TELEGRAM_TOKEN missing"
        )

        return False

    if not TELEGRAM_CHAT_ID:

        print(
            "ERROR: TELEGRAM_CHAT_ID missing"
        )

        return False

    url = (
        f"https://api.telegram.org/"
        f"bot{TELEGRAM_TOKEN}/sendMessage"
    )

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    try:

        response = requests.post(
            url,
            data=payload,
            timeout=20,
        )

        if response.status_code == 200:

            return True

        print(
            f"Telegram error "
            f"{response.status_code}: "
            f"{response.text}"
        )

        return False

    except Exception as e:

        print(
            f"Telegram send error: {e}"
        )

        return False


# ============================================================
# TELEGRAM MESSAGE
# ============================================================

def format_job_message(jobs):

    lines = []

    lines.append(
        "🇪🇬 🧬 "
        "<b>Top 10 Biomedical Engineering Jobs in Egypt</b>"
    )

    lines.append(
        f"📅 "
        f"{datetime.now().strftime('%Y-%m-%d')}"
    )

    lines.append("")

    for index, job in enumerate(
        jobs,
        start=1
    ):

        title = escape_telegram(
            job.get(
                "title",
                "Unknown position"
            )
        )

        company = escape_telegram(
            job.get(
                "company",
                "Unknown company"
            )
        )

        location = escape_telegram(
            job.get(
                "location",
                "Egypt"
            )
        )

        url = job.get(
            "url",
            ""
        )

        score = job.get(
            "score",
            0
        )

        applicants = job.get(
            "applicants"
        )

        lines.append(
            f"<b>{index}. {title}</b>"
        )

        lines.append(
            f"🏢 {company}"
        )

        lines.append(
            f"📍 {location}"
        )

        if applicants is not None:

            lines.append(
                f"👥 Applicants: "
                f"{applicants}"
            )

        lines.append(
            f"⭐ Match Score: "
            f"{score}"
        )

        if url:

            safe_url = html.escape(
                url,
                quote=True
            )

            lines.append(
                f'🔗 <a href="{safe_url}">'
                f"View Job</a>"
            )

        lines.append("")

    lines.append(
        "🤖 <i>Jobs are filtered and ranked "
        "for Biomedical Engineering.</i>"
    )

    return "\n".join(
        lines
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "=========================================="
    )

    print(
        "JOB SEARCH SCRIPT STARTED"
    )

    print(
        "=========================================="
    )

    # --------------------------------------------------------
    # Telegram check
    # --------------------------------------------------------

    print(
        "Telegram token: "
        + (
            "OK"
            if TELEGRAM_TOKEN
            else "MISSING"
        )
    )

    print(
        "Telegram chat ID: "
        + (
            "OK"
            if TELEGRAM_CHAT_ID
            else "MISSING"
        )
    )

    # --------------------------------------------------------
    # Load seen jobs
    # --------------------------------------------------------

    seen_jobs = load_seen_jobs()

    seen_jobs = cleanup_seen_jobs(
        seen_jobs
    )

    print(
        f"Previously remembered jobs: "
        f"{len(seen_jobs)}"
    )

    print(
        f"Search queries: "
        f"{len(LINKEDIN_SEARCHES)}"
    )

    print(
        f"Search period: LAST 30 DAYS"
    )

    print(
        f"Pages per query: "
        f"{MAX_SEARCH_PAGES}"
    )

    # --------------------------------------------------------
    # Search all queries
    # --------------------------------------------------------

    all_jobs = []

    for keywords in LINKEDIN_SEARCHES:

        jobs = search_linkedin(
            keywords,
            "Egypt"
        )

        print(
            f"Found {len(jobs)} "
            f"biomedical jobs "
            f"for '{keywords}'"
        )

        all_jobs.extend(
            jobs
        )

    # --------------------------------------------------------
    # GLOBAL DEDUPLICATION
    # --------------------------------------------------------

    all_jobs = deduplicate_jobs(
        all_jobs
    )

    print(
        "\n=========================================="
    )

    print(
        f"TOTAL UNIQUE BIOMEDICAL JOBS: "
        f"{len(all_jobs)}"
    )

    print(
        "=========================================="
    )

    # --------------------------------------------------------
    # NO JOBS AT ALL
    # --------------------------------------------------------

    if not all_jobs:

        print(
            "No biomedical jobs found."
        )

        send_telegram(
            "🇪🇬 🧬 "
            "<b>No Biomedical Engineering Jobs "
            "Found</b>\n\n"
            "LinkedIn did not return any matching "
            "Biomedical Engineering jobs in Egypt "
            "during this search."
        )

        save_seen_jobs(
            seen_jobs
        )

        return

    # --------------------------------------------------------
    # Calculate scores
    # --------------------------------------------------------

    for job in all_jobs:

        job["score"] = (
            calculate_score(
                job
            )
        )

    # --------------------------------------------------------
    # Separate NEW / OLD
    # --------------------------------------------------------

    new_jobs = []
    old_jobs = []

    for job in all_jobs:

        job_id = job.get(
            "id"
        )

        if (
            job_id
            and job_id in seen_jobs
        ):

            old_jobs.append(
                job
            )

        else:

            new_jobs.append(
                job
            )

    print(
        f"NEW jobs: "
        f"{len(new_jobs)}"
    )

    print(
        f"OLD jobs: "
        f"{len(old_jobs)}"
    )

    # --------------------------------------------------------
    # Sort
    # --------------------------------------------------------

    new_jobs.sort(
        key=lambda job: (
            job.get(
                "score",
                0
            )
        ),
        reverse=True
    )

    old_jobs.sort(
        key=lambda job: (
            job.get(
                "score",
                0
            )
        ),
        reverse=True
    )

    # --------------------------------------------------------
    # TOP 10
    #
    # New jobs first
    # Then old jobs
    #
    # If there are 10 total jobs,
    # ALWAYS TRY TO SEND 10.
    # --------------------------------------------------------

    selected_jobs = []

    selected_jobs.extend(
        new_jobs[
            :TOP_N
        ]
    )

    if len(selected_jobs) < TOP_N:

        remaining = (
            TOP_N -
            len(selected_jobs)
        )

        selected_jobs.extend(
            old_jobs[
                :remaining
            ]
        )

    # --------------------------------------------------------
    # Final safety deduplication
    # --------------------------------------------------------

    final_jobs = []
    final_ids = set()

    for job in selected_jobs:

        job_id = job.get(
            "id"
        )

        if job_id:

            if job_id in final_ids:
                continue

            final_ids.add(
                job_id
            )

        final_jobs.append(
            job
        )

        if len(final_jobs) >= TOP_N:
            break

    selected_jobs = final_jobs

    print(
        "\n=========================================="
    )

    print(
        f"SELECTED FOR TELEGRAM: "
        f"{len(selected_jobs)}"
    )

    print(
        "=========================================="
    )

    # --------------------------------------------------------
    # Print final jobs
    # --------------------------------------------------------

    for index, job in enumerate(
        selected_jobs,
        start=1
    ):

        print(
            f"{index}. "
            f"{job.get('title')} | "
            f"{job.get('company')} | "
            f"{job.get('location')} | "
            f"Score: "
            f"{job.get('score')}"
        )

    # --------------------------------------------------------
    # Applicant counts
    # --------------------------------------------------------

    print(
        "\nFetching applicant counts..."
    )

    for job in selected_jobs[
        :APPLICANT_FETCH_LIMIT
    ]:

        job["applicants"] = (
            fetch_applicant_count(
                job.get("url")
            )
        )

    # --------------------------------------------------------
    # Telegram
    # --------------------------------------------------------

    telegram_message = (
        format_job_message(
            selected_jobs
        )
    )

    print(
        "\nSending Telegram message..."
    )

    telegram_success = send_telegram(
        telegram_message
    )

    # --------------------------------------------------------
    # Save seen jobs
    # --------------------------------------------------------

    if telegram_success:

        now_iso = (
            datetime.utcnow()
            .isoformat()
        )

        newly_saved = 0

        for job in selected_jobs:

            job_id = job.get(
                "id"
            )

            if not job_id:
                continue

            if job_id not in seen_jobs:

                seen_jobs[
                    job_id
                ] = now_iso

                newly_saved += 1

        save_seen_jobs(
            seen_jobs
        )

        print(
            "\n=========================================="
        )

        print(
            "TELEGRAM SENT SUCCESSFULLY"
        )

        print(
            f"Jobs sent: "
            f"{len(selected_jobs)}"
        )

        print(
            f"New jobs saved: "
            f"{newly_saved}"
        )

        print(
            "=========================================="
        )

    else:

        print(
            "\nTelegram failed."
        )

        print(
            "seen_jobs.json was NOT updated."
        )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()
