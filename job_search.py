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
SEEN_JOBS_TTL_DAYS = 7

TOP_N = 10
APPLICANT_FETCH_LIMIT = 10

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
    "biomedical",
    "biomedical engineer",
    "biomedical equipment",
    "biomedical service",
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
    """
    Decide whether a job is genuinely related
    to biomedical / medical engineering.
    """

    title = (job.get("title") or "").lower().strip()
    description = (job.get("description") or "").lower()
    company = (job.get("company") or "").lower()

    context = f"{title} {description} {company}"

    # --------------------------------------------------------
    # Reject obvious unrelated titles
    # --------------------------------------------------------

    has_negative_title = any(
        keyword in title
        for keyword in NEGATIVE_TITLE_KEYWORDS
    )

    if has_negative_title:
        return False

    # --------------------------------------------------------
    # Strong biomedical title
    # --------------------------------------------------------

    has_strong_title = any(
        keyword in title
        for keyword in STRONG_BIOMEDICAL_TITLE_KEYWORDS
    )

    if has_strong_title:
        return True

    # --------------------------------------------------------
    # Conditional engineering title + medical context
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
    Calculate relevance score.
    """

    title = (job.get("title") or "").lower()
    description = (job.get("description") or "").lower()
    company = (job.get("company") or "").lower()
    location = (job.get("location") or "").lower()

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
    full_text = f"{title} {description} {company}"

    for keyword, points in SKILL_SCORES.items():
        if keyword in full_text:
            score += points

    return score


# ============================================================
# SEEN JOBS
# ============================================================

def load_seen_jobs():

    if not os.path.exists(SEEN_JOBS_FILE):
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

    now = datetime.utcnow()

    cutoff = now - timedelta(
        days=SEEN_JOBS_TTL_DAYS
    )

    cleaned = {}

    for job_id, timestamp in seen_jobs.items():

        try:

            dt = datetime.fromisoformat(
                timestamp
            )

            if dt >= cutoff:
                cleaned[job_id] = timestamp

        except Exception:

            cleaned[job_id] = timestamp

    return cleaned


# ============================================================
# LINKEDIN
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

        job_id = extract_job_id(url)

        # Backup ID extraction
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


def search_linkedin(keywords, location):

    url = (
        "https://www.linkedin.com/jobs-guest/"
        "jobs/api/seeMoreJobPostings/search"
    )

    params = {
        "keywords": keywords,
        "location": location,
        "f_TPR": "r259200",
        "start": 0,
    }

    try:

        response = requests.get(
            url,
            params=params,
            headers=LINKEDIN_HEADERS,
            timeout=20,
        )

        print(
            f"LinkedIn HTTP status: "
            f"{response.status_code}"
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

        # Try both LinkedIn formats
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
            f"LinkedIn raw cards returned: "
            f"{len(cards)}"
        )

        jobs = []
        rejected = 0

        for card in cards:

            job = parse_card(card)

            if not job:
                continue

            if not is_biomedical_job(job):

                rejected += 1

                print(
                    f"Rejected: "
                    f"{job['title']}"
                )

                continue

            job["score"] = calculate_score(
                job
            )

            jobs.append(job)

        print(
            f"Accepted biomedical jobs: "
            f"{len(jobs)}"
        )

        print(
            f"Rejected by biomedical filter: "
            f"{rejected}"
        )

        return jobs

    except Exception as e:

        print(
            f"LinkedIn search error for "
            f"'{keywords}': {e}"
        )

        return []


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

        job_id = job.get("id")

        if job_id:

            if job_id in seen_ids:
                continue

            seen_ids.add(job_id)

        secondary_key = (
            (job.get("title") or "")
            .lower()
            .strip(),

            (job.get("company") or "")
            .lower()
            .strip(),

            (job.get("city") or "")
            .lower()
            .strip(),
        )

        if secondary_key in seen_secondary:
            continue

        seen_secondary.add(
            secondary_key
        )

        unique_jobs.append(job)

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
            "ERROR: TELEGRAM_TOKEN is missing"
        )

        return False

    if not TELEGRAM_CHAT_ID:

        print(
            "ERROR: TELEGRAM_CHAT_ID is missing"
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
        f"📅 {datetime.now().strftime('%Y-%m-%d')}"
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
                f"👥 Applicants: {applicants}"
            )

        lines.append(
            f"⭐ Match Score: {score}"
        )

        if url:

            lines.append(
                f'🔗 <a href="{html.escape(url, quote=True)}">'
                f"View Job</a>"
            )

        lines.append("")

    lines.append(
        "🤖 <i>Jobs are filtered and ranked "
        "for Biomedical Engineering.</i>"
    )

    return "\n".join(lines)


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "======================================"
    )

    print(
        "JOB SEARCH SCRIPT STARTED"
    )

    print(
        "======================================"
    )

    if not TELEGRAM_TOKEN:

        print(
            "WARNING: TELEGRAM_TOKEN is missing"
        )

    else:

        print(
            "Telegram token: OK"
        )

    if not TELEGRAM_CHAT_ID:

        print(
            "WARNING: TELEGRAM_CHAT_ID is missing"
        )

    else:

        print(
            "Telegram chat ID: OK"
        )

    # --------------------------------------------------------
    # LOAD SEEN JOBS
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
        f"SEARCHES LOADED: "
        f"{len(LINKEDIN_SEARCHES)}"
    )

    print(
        "\n--- Egypt Biomedical Job Searches ---"
    )

    all_jobs = []

    # --------------------------------------------------------
    # SEARCH
    # --------------------------------------------------------

    for search in LINKEDIN_SEARCHES:

        keywords = search["keywords"]
        location = search["location"]

        print(
            f"\nSearching: "
            f"'{keywords}' / {location}"
        )

        jobs = search_linkedin(
            keywords,
            location
        )

        jobs = deduplicate_jobs(
            jobs
        )

        new_count = 0
        old_count = 0

        for job in jobs:

            job_id = job.get("id")

            if job_id and job_id in seen_jobs:

                old_count += 1

            else:

                new_count += 1

        print(
            f"Found {len(jobs)} biomedical jobs | "
            f"NEW: {new_count} | "
            f"OLD: {old_count}"
        )

        all_jobs.extend(
            jobs
        )

    # --------------------------------------------------------
    # GLOBAL DEDUP
    # --------------------------------------------------------

    all_jobs = deduplicate_jobs(
        all_jobs
    )

    print(
        "\n======================================"
    )

    print(
        f"TOTAL UNIQUE JOBS FOUND: "
        f"{len(all_jobs)}"
    )

    print(
        "======================================"
    )

    # --------------------------------------------------------
    # IMPORTANT:
    # ONLY SAY "NO JOBS" IF THERE ARE ACTUALLY ZERO JOBS
    # --------------------------------------------------------

    if not all_jobs:

        print(
            "\nNO BIOMEDICAL JOBS FOUND."
        )

        message = (
            "🇪🇬 🧬 "
            "<b>No Biomedical Engineering Jobs "
            "Found</b>\n\n"
            "LinkedIn did not return any matching "
            "Biomedical Engineering jobs in Egypt "
            "during this search."
        )

        send_telegram(
            message
        )

        save_seen_jobs(
            seen_jobs
        )

        return

    # --------------------------------------------------------
    # RECALCULATE SCORES
    # --------------------------------------------------------

    for job in all_jobs:

        job["score"] = calculate_score(
            job
        )

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
        f"New jobs available: "
        f"{len(new_jobs)}"
    )

    print(
        f"Previously seen jobs available: "
        f"{len(old_jobs)}"
    )

    # --------------------------------------------------------
    # SORT BOTH
    # --------------------------------------------------------

    new_jobs.sort(
        key=lambda job: (
            job.get("score", 0)
        ),
        reverse=True
    )

    old_jobs.sort(
        key=lambda job: (
            job.get("score", 0)
        ),
        reverse=True
    )

    # --------------------------------------------------------
    # SELECT TOP 10
    #
    # NEW JOBS FIRST
    # THEN OLD JOBS
    #
    # THIS MEANS:
    # EVEN IF THERE ARE ZERO NEW JOBS,
    # WE STILL SEND AVAILABLE JOBS.
    # --------------------------------------------------------

    selected_jobs = []

    selected_jobs.extend(
        new_jobs[:TOP_N]
    )

    if len(selected_jobs) < TOP_N:

        remaining = (
            TOP_N -
            len(selected_jobs)
        )

        selected_jobs.extend(
            old_jobs[:remaining]
        )

    # --------------------------------------------------------
    # FINAL DEDUP
    # --------------------------------------------------------

    final_jobs = []
    final_ids = set()

    for job in selected_jobs:

        job_id = job.get("id")

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
        f"\nSELECTED FOR TELEGRAM: "
        f"{len(selected_jobs)}"
    )

    # --------------------------------------------------------
    # PRINT SELECTED JOBS
    # --------------------------------------------------------

    print(
        "\n--- FINAL JOBS ---"
    )

    for index, job in enumerate(
        selected_jobs,
        start=1
    ):

        print(
            f"{index}. "
            f"{job.get('title')} | "
            f"{job.get('company')} | "
            f"Score: {job.get('score')}"
        )

    # --------------------------------------------------------
    # APPLICANT COUNTS
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
    # TELEGRAM
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
    # SAVE ONLY IF TELEGRAM SUCCESS
    # --------------------------------------------------------

    if telegram_success:

        now_iso = datetime.utcnow().isoformat()

        newly_saved = 0

        for job in selected_jobs:

            job_id = job.get("id")

            if not job_id:
                continue

            if job_id not in seen_jobs:

                seen_jobs[job_id] = (
                    now_iso
                )

                newly_saved += 1

        save_seen_jobs(
            seen_jobs
        )

        print(
            "\n======================================"
        )

        print(
            "TELEGRAM SENT SUCCESSFULLY"
        )

        print(
            f"Sent: {len(selected_jobs)} jobs"
        )

        print(
            f"New jobs saved: {newly_saved}"
        )

        print(
            "======================================"
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
