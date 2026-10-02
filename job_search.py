import os
import re
import json
import html
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from urllib.parse import urlencode


# ============================================================
# CONFIG
# ============================================================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

SEEN_JOBS_FILE = "seen_jobs.json"
SEEN_JOBS_TTL_DAYS = 7

TOP_N = 10
APPLICANT_FETCH_LIMIT = 15

LINKEDIN_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/142.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


# ============================================================
# EGYPT-ONLY LINKEDIN SEARCHES
# ============================================================

LINKEDIN_SEARCHES = [
    {
        "keywords": "Biomedical Engineer",
        "location": "Egypt",
    },
    {
        "keywords": "Biomedical Equipment Engineer",
        "location": "Egypt",
    },
    {
        "keywords": "Medical Device Engineer",
        "location": "Egypt",
    },
    {
        "keywords": "Clinical Engineer",
        "location": "Egypt",
    },
    {
        "keywords": "Medical Equipment Engineer",
        "location": "Egypt",
    },
    {
        "keywords": "Biomedical Service Engineer",
        "location": "Egypt",
    },
    {
        "keywords": "Field Service Engineer Medical Devices",
        "location": "Egypt",
    },
    {
        "keywords": "Medical Imaging Engineer",
        "location": "Egypt",
    },
    {
        "keywords": "Imaging Engineer Medical",
        "location": "Egypt",
    },
    {
        "keywords": "Healthcare Technology Engineer",
        "location": "Egypt",
    },
    {
        "keywords": "Medical Instrumentation Engineer",
        "location": "Egypt",
    },
]


# ============================================================
# BIOMEDICAL FILTER
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
]


NEGATIVE_TITLE_KEYWORDS = [
    "sales engineer",
    "civil engineer",
    "structural engineer",
    "mechanical engineer",
    "software engineer",
    "network engineer",
    "data engineer",
    "devops engineer",
    "cloud engineer",
    "security engineer",
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
    "hr ",
    "customer service",
    "recruiter",
    "procurement",
]


def is_biomedical_job(job):
    """
    Decide whether a job is genuinely related to biomedical engineering.
    """

    title = (job.get("title") or "").lower().strip()
    description = (job.get("description") or "").lower()
    company = (job.get("company") or "").lower()

    context = f"{title} {description} {company}"

    # --------------------------------------------------------
    # Reject obvious non-biomedical titles
    # --------------------------------------------------------

    has_strong_title = any(
        keyword in title
        for keyword in STRONG_BIOMEDICAL_TITLE_KEYWORDS
    )

    has_negative_title = any(
        keyword in title
        for keyword in NEGATIVE_TITLE_KEYWORDS
    )

    if has_negative_title and not has_strong_title:
        return False

    # --------------------------------------------------------
    # Strong biomedical title = accept
    # --------------------------------------------------------

    if has_strong_title:
        return True

    # --------------------------------------------------------
    # Conditional engineering titles
    # --------------------------------------------------------

    has_conditional_title = any(
        keyword in title
        for keyword in CONDITIONAL_ENGINEER_KEYWORDS
    )

    if has_conditional_title:
        medical_context_found = any(
            keyword in context
            for keyword in MEDICAL_CONTEXT_KEYWORDS
        )

        if medical_context_found:
            return True

    # --------------------------------------------------------
    # Extra biomedical checks
    # --------------------------------------------------------

    if "biomedical" in title:
        return True

    if "medical device" in title:
        return True

    if "medical equipment" in title:
        return True

    if "clinical engineer" in title:
        return True

    return False


# ============================================================
# SCORING
# ============================================================

ROLE_SCORES = {
    "field service engineer": 42,
    "medical imaging engineer": 42,
    "imaging engineer": 40,
    "equipment engineer": 40,
    "medical device": 38,
    "medical devices": 38,
    "clinical": 35,
    "healthcare": 25,
    "healthcare engineer": 30,
    "health technology": 34,
    "healthcare technology": 34,
    "medical technology": 34,
    "field service": 32,
    "medical imaging": 32,
    "imaging": 28,
    "service engineer": 30,
    "technical service engineer": 30,
    "maintenance engineer": 26,
    "medical instrumentation": 38,
    "research engineer": 24,
    "r&d engineer": 24,
    "biomedical engineer": 50,
    "biomedical equipment": 48,
    "biomedical service": 48,
    "clinical engineer": 45,
    "medical equipment engineer": 45,
}


LOCATION_SCORES = {
    "egypt": 30,
    "cairo": 25,
    "giza": 24,
    "alexandria": 22,
    "new cairo": 24,
    "6th of october": 22,
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
    """
    Calculate relevance score for ranking.
    """

    title = (job.get("title") or "").lower()
    description = (job.get("description") or "").lower()
    company = (job.get("company") or "").lower()
    location = (job.get("location") or "").lower()

    score = 0

    # --------------------------------------------------------
    # Role score
    # --------------------------------------------------------

    for keyword, points in ROLE_SCORES.items():
        if keyword in title:
            score += points

    # --------------------------------------------------------
    # Location score
    # --------------------------------------------------------

    for keyword, points in LOCATION_SCORES.items():
        if keyword in location:
            score += points

    # --------------------------------------------------------
    # Biomedical / medical skills
    # --------------------------------------------------------

    full_text = f"{title} {description} {company}"

    for keyword, points in SKILL_SCORES.items():
        if keyword in full_text:
            score += points

    return score


# ============================================================
# SEEN JOBS
# ============================================================

def load_seen_jobs():
    """
    Load previously sent jobs.

    Format:
    {
        "linkedin_job_id": "2026-10-02T14:00:00"
    }
    """

    if not os.path.exists(SEEN_JOBS_FILE):
        return {}

    try:
        with open(SEEN_JOBS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, dict):
            return data

        return {}

    except Exception as e:
        print(f"Could not load seen jobs: {e}")
        return {}


def save_seen_jobs(seen_jobs):
    """
    Save seen jobs.
    """

    with open(SEEN_JOBS_FILE, "w", encoding="utf-8") as f:
        json.dump(
            seen_jobs,
            f,
            ensure_ascii=False,
            indent=2
        )


def cleanup_seen_jobs(seen_jobs):
    """
    Remove entries older than SEEN_JOBS_TTL_DAYS.
    """

    now = datetime.utcnow()
    cutoff = now - timedelta(days=SEEN_JOBS_TTL_DAYS)

    cleaned = {}

    for job_id, timestamp in seen_jobs.items():

        try:
            dt = datetime.fromisoformat(timestamp)

            if dt >= cutoff:
                cleaned[job_id] = timestamp

        except Exception:
            # Keep malformed entries rather than accidentally
            # treating them as new jobs.
            cleaned[job_id] = timestamp

    return cleaned


# ============================================================
# LINKEDIN JOB SEARCH
# ============================================================

def extract_job_id(url):
    """
    Extract LinkedIn job ID from a job URL.
    """

    if not url:
        return None

    patterns = [
        r"/view/(\d+)",
        r"currentJobId=(\d+)",
        r"jobId=(\d+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, url)

        if match:
            return match.group(1)

    return None


def parse_card(card):
    """
    Parse one LinkedIn job card.
    """

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
            title_element.get_text(" ", strip=True)
            if title_element
            else ""
        )

        company = (
            company_element.get_text(" ", strip=True)
            if company_element
            else ""
        )

        location = (
            location_element.get_text(" ", strip=True)
            if location_element
            else "Egypt"
        )

        url = (
            link_element.get("href", "").strip()
            if link_element
            else ""
        )

        url = url.split("?")[0]

        job_id = extract_job_id(url)

        if not job_id:
            # Try LinkedIn card data
            entity_urn = card.get("data-entity-urn", "")

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
        print(f"Error parsing job card: {e}")
        return None


def search_linkedin(keywords, location):
    """
    Search LinkedIn guest jobs.

    Searches only Egypt.
    """

    url = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"

    params = {
        "keywords": keywords,
        "location": location,
        "f_TPR": "r259200",   # Last 3 days
        "start": 0,
    }

    try:
        response = requests.get(
            url,
            params=params,
            headers=LINKEDIN_HEADERS,
            timeout=20,
        )

        if response.status_code != 200:
            print(
                f"LinkedIn returned status "
                f"{response.status_code}"
            )
            return []

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        cards = soup.select(
            "li.jobs-search__results-list"
        )

        # Some LinkedIn responses use this class instead.
        if not cards:
            cards = soup.select(
                "li.base-card"
            )

        jobs = []

        for card in cards:

            job = parse_card(card)

            if not job:
                continue

            if not is_biomedical_job(job):
                print(
                    f"Rejected non-biomedical job: "
                    f"{job['title']}"
                )
                continue

            job["score"] = calculate_score(job)

            jobs.append(job)

        return jobs

    except Exception as e:
        print(
            f"LinkedIn search error for "
            f"'{keywords}': {e}"
        )
        return []


# ============================================================
# APPLICANT COUNT
# ============================================================

def fetch_applicant_count(url):
    """
    Try to retrieve applicant count.

    LinkedIn may block this request, so failure is okay.
    """

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
                match.group(1).replace(",", "")
            )

        return None

    except Exception:
        return None


# ============================================================
# DEDUPLICATION
# ============================================================

def deduplicate_jobs(jobs):
    """
    Deduplicate first by LinkedIn ID.
    Then use title + company + city.
    """

    unique_jobs = []

    seen_ids = set()
    seen_secondary = set()

    for job in jobs:

        job_id = job.get("id")

        if job_id:

            if job_id in seen_ids:
                continue

            seen_ids.add(job_id)

        secondary_key = (
            (job.get("title") or "").lower().strip(),
            (job.get("company") or "").lower().strip(),
            (job.get("city") or "").lower().strip(),
        )

        if secondary_key in seen_secondary:
            continue

        seen_secondary.add(secondary_key)

        unique_jobs.append(job)

    return unique_jobs


# ============================================================
# TELEGRAM
# ============================================================

def escape_telegram(text):
    """
    Escape characters for Telegram HTML mode.
    """

    if text is None:
        return ""

    return html.escape(str(text))


def send_telegram(message):
    """
    Send message to Telegram.
    """

    if not TELEGRAM_TOKEN:
        print("ERROR: TELEGRAM_TOKEN is missing")
        return False

    if not TELEGRAM_CHAT_ID:
        print("ERROR: TELEGRAM_CHAT_ID is missing")
        return False

    url = (
        f"https://api.telegram.org/bot"
        f"{TELEGRAM_TOKEN}/sendMessage"
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
            f"Telegram error {response.status_code}: "
            f"{response.text}"
        )

        return False

    except Exception as e:
        print(f"Telegram send error: {e}")
        return False


# ============================================================
# FORMAT TELEGRAM MESSAGE
# ============================================================

def format_job_message(jobs):
    """
    Format Top N jobs for Telegram.
    """

    lines = []

    lines.append(
        "🇪🇬 🧬 <b>Top Biomedical Engineering Jobs in Egypt</b>"
    )

    lines.append(
        f"📅 {datetime.now().strftime('%Y-%m-%d')}"
    )

    lines.append("")

    for index, job in enumerate(jobs, start=1):

        title = escape_telegram(
            job.get("title", "Unknown position")
        )

        company = escape_telegram(
            job.get("company", "Unknown company")
        )

        location = escape_telegram(
            job.get("location", "Egypt")
        )

        url = job.get("url", "")

        score = job.get("score", 0)

        applicants = job.get("applicants")

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
                f"👥 Applicants: {applicants}"
            )

        lines.append(
            f"⭐ Match Score: {score}"
        )

        if url:
            lines.append(
                f"🔗 <a href=\"{html.escape(url, quote=True)}\">View Job</a>"
            )

        lines.append("")

    lines.append(
        "🤖 <i>Biomedical jobs are filtered for Egypt.</i>"
    )

    return "\n".join(lines)


# ============================================================
# MAIN
# ============================================================

def main():

    print("JOB SEARCH SCRIPT STARTED")

    if not TELEGRAM_TOKEN:
        print("WARNING: TELEGRAM_TOKEN is missing")

    if not TELEGRAM_CHAT_ID:
        print("WARNING: TELEGRAM_CHAT_ID is missing")

    print("CONFIG LOADED")

    seen_jobs = load_seen_jobs()

    # Remove old memory entries
    seen_jobs = cleanup_seen_jobs(seen_jobs)

    print(
        f"SEARCHES LOADED: "
        f"{len(LINKEDIN_SEARCHES)}"
    )

    print(
        "\n--- Egypt Biomedical Job Searches ---"
    )

    all_jobs = []

    # --------------------------------------------------------
    # SEARCH ALL EGYPT QUERIES
    # --------------------------------------------------------

    for search in LINKEDIN_SEARCHES:

        keywords = search["keywords"]
        location = search["location"]

        print(
            f"\nSearching: '{keywords}' / {location}"
        )

        jobs = search_linkedin(
            keywords,
            location,
        )

        # ----------------------------------------------------
        # Deduplicate inside each search
        # ----------------------------------------------------

        jobs = deduplicate_jobs(jobs)

        # ----------------------------------------------------
        # Count new jobs
        # ----------------------------------------------------

        new_count = 0

        for job in jobs:

            job_id = job.get("id")

            if job_id not in seen_jobs:
                new_count += 1

        print(
            f"Found {len(jobs)} Biomedical jobs, "
            f"{new_count} new"
        )

        all_jobs.extend(jobs)

    # --------------------------------------------------------
    # GLOBAL DEDUPLICATION
    # --------------------------------------------------------

    all_jobs = deduplicate_jobs(all_jobs)

    print(
        f"\nTotal unique biomedical jobs found: "
        f"{len(all_jobs)}"
    )

    if not all_jobs:

        print(
            "No biomedical jobs found at all."
        )

        message = (
            "🇪🇬 🧬 "
            "No biomedical engineering jobs "
            "were found in Egypt right now."
        )

        send_telegram(message)

        save_seen_jobs(seen_jobs)

        return

    # --------------------------------------------------------
    # CALCULATE SCORES AGAIN AFTER GLOBAL DEDUP
    # --------------------------------------------------------

    for job in all_jobs:
        job["score"] = calculate_score(job)

    # --------------------------------------------------------
    # SPLIT NEW / OLD
    # --------------------------------------------------------

    new_jobs = []
    old_jobs = []

    for job in all_jobs:

        job_id = job.get("id")

        if job_id and job_id in seen_jobs:
            old_jobs.append(job)
        else:
            new_jobs.append(job)

    print(
        f"New jobs available: {len(new_jobs)}"
    )

    print(
        f"Previously seen jobs available: "
        f"{len(old_jobs)}"
    )

    # --------------------------------------------------------
    # SORT
    # --------------------------------------------------------

    new_jobs.sort(
        key=lambda job: job.get("score", 0),
        reverse=True,
    )

    old_jobs.sort(
        key=lambda job: job.get("score", 0),
        reverse=True,
    )

    # --------------------------------------------------------
    # NEW BEHAVIOR:
    #
    # NEW JOBS FIRST
    # THEN OLD JOBS TO COMPLETE TOP 10
    # --------------------------------------------------------

    selected_jobs = []

    # Add new jobs first
    selected_jobs.extend(
        new_jobs[:TOP_N]
    )

    # If fewer than TOP_N new jobs,
    # fill the remaining places with old jobs.
    if len(selected_jobs) < TOP_N:

        remaining = TOP_N - len(selected_jobs)

        selected_jobs.extend(
            old_jobs[:remaining]
        )

    # --------------------------------------------------------
    # FINAL SAFETY DEDUPLICATION
    # --------------------------------------------------------

    final_jobs = []
    final_ids = set()

    for job in selected_jobs:

        job_id = job.get("id")

        if job_id and job_id in final_ids:
            continue

        if job_id:
            final_ids.add(job_id)

        final_jobs.append(job)

        if len(final_jobs) >= TOP_N:
            break

    selected_jobs = final_jobs

    print(
        f"\nSelected {len(selected_jobs)} jobs "
        f"for Telegram."
    )

    # --------------------------------------------------------
    # FETCH APPLICANT COUNTS FOR TOP JOBS
    # --------------------------------------------------------

    print(
        f"Fetching applicant counts for up to "
        f"{min(APPLICANT_FETCH_LIMIT, len(selected_jobs))} jobs..."
    )

    for job in selected_jobs[:APPLICANT_FETCH_LIMIT]:

        applicant_count = fetch_applicant_count(
            job.get("url")
        )

        job["applicants"] = applicant_count

    # --------------------------------------------------------
    # CREATE TELEGRAM MESSAGE
    # --------------------------------------------------------

    telegram_message = format_job_message(
        selected_jobs
    )

    print("\nSending Telegram message...")

    telegram_success = send_telegram(
        telegram_message
    )

    # --------------------------------------------------------
    # IMPORTANT:
    #
    # ONLY MARK NEW JOBS AS SEEN IF TELEGRAM SUCCESSFULLY
    # SENT.
    # --------------------------------------------------------

    if telegram_success:

        now_iso = datetime.utcnow().isoformat()

        newly_saved = 0

        for job in selected_jobs:

            job_id = job.get("id")

            if not job_id:
                continue

            # Only add genuinely new jobs.
            if job_id not in seen_jobs:

                seen_jobs[job_id] = now_iso
                newly_saved += 1

        save_seen_jobs(seen_jobs)

        print(
            f"Telegram sent: "
            f"{len(selected_jobs)} Biomedical jobs."
        )

        print(
            f"Saved {newly_saved} new jobs "
            f"to seen_jobs.json"
        )

    else:

        print(
            "Telegram failed. "
            "Seen jobs were NOT updated."
        )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()
