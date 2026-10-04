import os
import re
import json
import html
import requests

from bs4 import BeautifulSoup
from datetime import datetime, timedelta


# =========================================================
# CONFIGURATION
# =========================================================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

SEEN_JOBS_FILE = "seen_jobs.json"

TOP_N = 10

# Search jobs from the last 30 days
LINKEDIN_TIME_FILTER = "r2592000"

PAGE_SIZE = 25
MAX_SEARCH_PAGES = 10

LINKEDIN_URL = (
    "https://www.linkedin.com/jobs-guest/jobs/api/"
    "seeMoreJobPostings/search"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


# =========================================================
# BIOMEDICAL SEARCH QUERIES
# =========================================================

SEARCH_QUERIES = [

    "Biomedical Engineer",
    "Biomedical Engineering",
    "Biomedical Equipment Engineer",
    "Biomedical Service Engineer",
    "Biomedical Maintenance Engineer",
    "Biomedical Field Service Engineer",

    "Medical Device Engineer",
    "Medical Devices Engineer",
    "Medical Device Service Engineer",
    "Medical Device Field Service Engineer",

    "Medical Equipment Engineer",
    "Medical Equipment Service Engineer",
    "Medical Equipment Field Service Engineer",

    "Clinical Engineer",
    "Clinical Engineering",

    "Medical Imaging Engineer",
    "Imaging Engineer Medical",
    "Medical Imaging Service Engineer",

    "Medical Instrumentation Engineer",
    "Biomedical Instrumentation Engineer",

    "Field Service Engineer Medical Devices",
    "Field Service Engineer Medical Equipment",

    "Service Engineer Medical Devices",
    "Service Engineer Medical Equipment",
]


# =========================================================
# DIRECT BIOMEDICAL JOBS
# =========================================================

DIRECT_BIOMEDICAL = {

    "biomedical engineer": 200,
    "biomedical engineering": 195,

    "biomedical equipment engineer": 205,
    "biomedical service engineer": 205,
    "biomedical maintenance engineer": 200,
    "biomedical field service engineer": 205,

    "medical device engineer": 190,
    "medical devices engineer": 190,
    "medical device service engineer": 195,
    "medical device field service engineer": 200,

    "medical equipment engineer": 185,
    "medical equipment service engineer": 190,
    "medical equipment field service engineer": 195,

    "clinical engineer": 185,
    "clinical engineering": 180,

    "medical imaging engineer": 185,
    "medical imaging service engineer": 185,

    "medical instrumentation engineer": 180,
    "biomedical instrumentation engineer": 190,
}


# =========================================================
# HARD EXCLUSIONS
# =========================================================

HARD_EXCLUDE = [

    # Sales / Marketing
    "sales engineer",
    "sales representative",
    "sales specialist",
    "sales manager",
    "medical sales",
    "sales",

    "marketing",
    "brand manager",

    # Product / Business
    "product specialist",
    "product manager",
    "product executive",
    "business development",

    # Regulatory
    "regulatory affairs",
    "regulatory specialist",
    "regulatory associate",
    "regulatory officer",
    "regulatory",

    # Quality
    "quality assurance",
    "quality control",
    "qa specialist",
    "qc specialist",
    "quality engineer",
    "quality specialist",

    # HR
    "human resources",
    "hr specialist",
    "recruiter",
    "recruitment",

    # Finance
    "accountant",
    "accounting",
    "finance",

    # Procurement
    "procurement",
    "purchasing",

    # Customer service
    "customer service",

    # Pharmacy
    "pharmacist",
    "pharmacy",

    # Laboratory
    "laboratory technician",
    "lab technician",
    "laboratory specialist",
    "lab specialist",

    # Software / IT
    "software engineer",
    "software developer",
    "web developer",
    "frontend developer",
    "backend developer",
    "full stack developer",

    "data analyst",
    "data engineer",

    "devops",
    "cloud engineer",
    "network engineer",
    "cybersecurity",
    "it specialist",

    # Other engineering fields
    "civil engineer",
    "structural engineer",
    "mechanical engineer",
    "electrical engineer",
    "electronics engineer",
    "chemical engineer",
    "industrial engineer",
    "process engineer",
    "automotive engineer",

    "production engineer",
    "manufacturing engineer",
    "construction engineer",
    "architect",

    # Management
    "project manager",
    "project coordinator",

    # Non-engineering application roles
    "application specialist",
    "clinical application specialist",

    # Technician roles
    "biomedical technician",
    "medical equipment technician",
    "medical device technician",

    # Research / Science
    "research assistant",
    "research scientist",
    "scientist",
]


# =========================================================
# MEDICAL TECHNOLOGY TERMS
# =========================================================

MEDICAL_TECH_TERMS = [

    "ultrasound",
    "mri",
    "x-ray",
    "xray",
    "ct scanner",
    "computed tomography",
    "radiology",
    "ecg",
    "eeg",
    "patient monitor",
    "patient monitoring",
    "ventilator",
    "dialysis",
    "infusion pump",
    "anesthesia machine",
    "defibrillator",
    "medical imaging",
    "medical instrumentation",
    "diagnostic equipment",
    "hospital equipment",
]


# =========================================================
# LOAD SEEN JOBS
# =========================================================

def load_seen():

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
            f"Could not load seen_jobs.json: {e}"
        )

        return {}


# =========================================================
# SAVE SEEN JOBS
# =========================================================

def save_seen(seen):

    try:

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

    except Exception as e:

        print(
            f"Could not save seen_jobs.json: {e}"
        )


# =========================================================
# CLEAN OLD SEEN JOBS
# =========================================================

def cleanup_seen(seen):

    cutoff = datetime.utcnow() - timedelta(
        days=30
    )

    cleaned = {}

    for job_id, value in seen.items():

        try:

            if isinstance(value, str):

                dt = datetime.fromisoformat(
                    value.replace("Z", "")
                )

            elif isinstance(value, dict):

                seen_at = value.get(
                    "seen_at",
                    ""
                )

                dt = datetime.fromisoformat(
                    seen_at.replace("Z", "")
                )

            else:

                continue

            if dt >= cutoff:

                cleaned[job_id] = value

        except Exception:

            # Keep unknown entries
            cleaned[job_id] = value

    return cleaned


# =========================================================
# CLEAN TEXT
# =========================================================

def clean(text):

    if not text:
        return ""

    text = html.unescape(
        str(text)
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# =========================================================
# PARSE LINKEDIN JOB CARD
# =========================================================

def parse_job(card):

    try:

        title_el = card.select_one(
            "h3.base-search-card__title"
        )

        company_el = card.select_one(
            "h4.base-search-card__subtitle"
        )

        location_el = card.select_one(
            "span.job-search-card__location"
        )

        link_el = card.select_one(
            "a.base-card__full-link"
        )

        title = clean(
            title_el.get_text(
                " ",
                strip=True
            )
            if title_el
            else ""
        )

        company = clean(
            company_el.get_text(
                " ",
                strip=True
            )
            if company_el
            else ""
        )

        location = clean(
            location_el.get_text(
                " ",
                strip=True
            )
            if location_el
            else ""
        )

        url = ""

        if link_el:

            url = link_el.get(
                "href",
                ""
            )

        url = url.split("?")[0].strip()

        if not title or not url:
            return None

        # -------------------------------------------------
        # Get LinkedIn Job ID
        # -------------------------------------------------

        job_id = None

        data_entity = card.get(
            "data-entity-urn"
        )

        if data_entity:

            match = re.search(
                r"jobPosting:(\d+)",
                data_entity
            )

            if match:

                job_id = match.group(1)

        if not job_id:

            match = re.search(
                r"/jobs/view/(\d+)",
                url
            )

            if match:

                job_id = match.group(1)

        if not job_id:

            job_id = url

        return {

            "id": str(job_id),

            "title": title,

            "company": company,

            "location": location,

            "url": url,

        }

    except Exception as e:

        print(
            f"Error parsing job: {e}"
        )

        return None


# =========================================================
# SEARCH LINKEDIN
# =========================================================

def search_linkedin(query):

    jobs = []

    for page in range(
        MAX_SEARCH_PAGES
    ):

        start = page * PAGE_SIZE

        params = {

            "keywords": query,

            "location": "Egypt",

            "f_TPR": LINKEDIN_TIME_FILTER,

            "start": start,

        }

        try:

            response = requests.get(

                LINKEDIN_URL,

                params=params,

                headers=HEADERS,

                timeout=20

            )

            if response.status_code != 200:

                print(
                    f"HTTP {response.status_code}"
                )

                break

            soup = BeautifulSoup(

                response.text,

                "html.parser"

            )

            cards = soup.select("li")

            if not cards:

                break

            found_on_page = 0

            for card in cards:

                job = parse_job(card)

                if job:

                    # Keep the search query.
                    # This helps identify medical-specific
                    # service/field-service searches.

                    job["search_query"] = query

                    jobs.append(job)

                    found_on_page += 1

            if found_on_page == 0:

                break

            if len(cards) < PAGE_SIZE:

                break

        except Exception as e:

            print(
                f"Search error for '{query}': {e}"
            )

            break

    return jobs


# =========================================================
# DEDUPLICATE
# =========================================================

def deduplicate(jobs):

    unique = {}

    for job in jobs:

        job_id = str(
            job.get("id")
            or job.get("url")
        )

        if job_id not in unique:

            unique[job_id] = job

    return list(
        unique.values()
    )


# =========================================================
# HARD EXCLUSION CHECK
# =========================================================

def is_hard_excluded(title):

    title = clean(
        title
    ).lower()

    for word in HARD_EXCLUDE:

        if word in title:

            return True

    return False


# =========================================================
# CLASSIFY JOB
# =========================================================

def classify_job(job):

    title = clean(
        job.get("title", "")
    ).lower()

    query = clean(
        job.get("search_query", "")
    ).lower()

    if not title:

        return None

    # -----------------------------------------------------
    # HARD EXCLUSIONS
    # -----------------------------------------------------

    if is_hard_excluded(title):

        return None

    # -----------------------------------------------------
    # DIRECT BIOMEDICAL TITLES
    # -----------------------------------------------------

    for term, score in DIRECT_BIOMEDICAL.items():

        if term in title:

            return score

    # -----------------------------------------------------
    # MEDICAL + ENGINEERING
    # -----------------------------------------------------

    medical_terms = [

        "biomedical",

        "medical device",
        "medical devices",

        "medical equipment",

        "clinical engineer",
        "clinical engineering",

        "medical imaging",

        "medical instrumentation",

        "biomedical instrumentation",

    ]

    has_medical = any(
        term in title
        for term in medical_terms
    )

    has_engineer = (
        "engineer" in title
        or "engineering" in title
    )

    if has_medical and has_engineer:

        score = 115

        if "biomedical" in title:

            score += 15

        if "medical device" in title:

            score += 12

        if "medical equipment" in title:

            score += 12

        if "clinical" in title:

            score += 8

        if "imaging" in title:

            score += 8

        if "instrumentation" in title:

            score += 8

        if "field service" in title:

            score += 8

        if "service engineer" in title:

            score += 8

        if "maintenance" in title:

            score += 6

        return score

    # -----------------------------------------------------
    # MEDICAL TECHNOLOGY + ENGINEER
    # -----------------------------------------------------

    for term in MEDICAL_TECH_TERMS:

        if term in title and "engineer" in title:

            return 110

    # -----------------------------------------------------
    # CONDITIONAL ENGINEERING ROLES
    #
    # These are allowed when the search query itself
    # specifically asked for medical devices/equipment.
    # -----------------------------------------------------

    conditional_roles = [

        "field service engineer",

        "service engineer",

        "technical service engineer",

        "maintenance engineer",

        "equipment engineer",

    ]

    medical_service_queries = [

        "field service engineer medical devices",

        "field service engineer medical equipment",

        "service engineer medical devices",

        "service engineer medical equipment",

    ]

    has_medical_service_query = any(

        q in query

        for q in medical_service_queries

    )

    if has_medical_service_query:

        for role in conditional_roles:

            if role in title:

                if role == "field service engineer":

                    return 105

                if role == "service engineer":

                    return 100

                if role == "technical service engineer":

                    return 95

                if role == "maintenance engineer":

                    return 90

                if role == "equipment engineer":

                    return 90

    # -----------------------------------------------------
    # GENERAL BIOMEDICAL SEARCHES
    #
    # Since this job was returned by a specifically
    # Biomedical search query, allow relevant engineering
    # roles instead of throwing them away too aggressively.
    # -----------------------------------------------------

    biomedical_query = any(

        q in query

        for q in [

            "biomedical engineer",
            "biomedical engineering",
            "biomedical equipment engineer",
            "biomedical service engineer",
            "biomedical maintenance engineer",
            "biomedical field service engineer",
            "medical device engineer",
            "medical devices engineer",
            "medical device service engineer",
            "medical device field service engineer",
            "medical equipment engineer",
            "medical equipment service engineer",
            "medical equipment field service engineer",
            "clinical engineer",
            "clinical engineering",
            "medical imaging engineer",
            "imaging engineer medical",
            "medical imaging service engineer",
            "medical instrumentation engineer",
            "biomedical instrumentation engineer",

        ]

    )

    if biomedical_query:

        # Accept engineering/service roles that are not
        # obviously unrelated. This gives us enough genuine
        # Biomedical-related results to build the Top 10.

        if (
            "engineer" in title
            or "engineering" in title
        ):

            score = 75

            if "service" in title:

                score += 10

            if "field" in title:

                score += 8

            if "equipment" in title:

                score += 10

            if "device" in title:

                score += 10

            if "clinical" in title:

                score += 10

            if "imaging" in title:

                score += 10

            if "instrument" in title:

                score += 10

            return score

    # -----------------------------------------------------
    # NO MATCH
    # -----------------------------------------------------

    return None


# =========================================================
# FETCH APPLICANT COUNT
# =========================================================

def fetch_applicants(url):

    if not url:

        return None

    try:

        response = requests.get(

            url,

            headers=HEADERS,

            timeout=10

        )

        if response.status_code != 200:

            return None

        match = re.search(

            r"(\d[\d,]*) applicants",

            response.text,

            re.IGNORECASE

        )

        if match:

            return int(
                match.group(1).replace(
                    ",",
                    ""
                )
            )

    except Exception:

        pass

    return None


# =========================================================
# SEND TELEGRAM
# =========================================================

def send_telegram(message):

    if not TELEGRAM_TOKEN:

        raise RuntimeError(
            "TELEGRAM_TOKEN is missing."
        )

    if not TELEGRAM_CHAT_ID:

        raise RuntimeError(
            "TELEGRAM_CHAT_ID is missing."
        )

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

    response = requests.post(

        url,

        data=payload,

        timeout=20

    )

    response.raise_for_status()

    return response.json()


# =========================================================
# BUILD TELEGRAM MESSAGE
# =========================================================

def build_message(jobs):

    message = (

        f"🇪🇬 🧬 "
        f"<b>Top {len(jobs)} Biomedical "
        f"Engineering Jobs in Egypt</b>\n\n"

    )

    for index, job in enumerate(
        jobs,
        start=1
    ):

        title = html.escape(
            job.get(
                "title",
                "Unknown"
            )
        )

        company = html.escape(
            job.get(
                "company",
                "Unknown company"
            )
        )

        location = html.escape(
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

        message += (

            f"<b>{index}. {title}</b>\n"

            f"🏢 {company}\n"

            f"📍 {location}\n"

            f"⭐ Match Score: {score}\n"

        )

        if applicants is not None:

            message += (

                f"👥 Applicants: "
                f"{applicants}\n"

            )

        if url:

            message += (

                f"🔗 "
                f"<a href=\""
                f"{html.escape(url)}"
                f"\">Apply / View Job</a>\n"

            )

        message += "\n"

    return message


# =========================================================
# MAIN
# =========================================================

def main():

    print(
        "\n========================================"
    )

    print(
        "JOB SEARCH SCRIPT STARTED"
    )

    print(
        "========================================\n"
    )

    # -----------------------------------------------------
    # LOAD SEEN JOBS
    # -----------------------------------------------------

    seen = load_seen()

    seen = cleanup_seen(
        seen
    )

    print(
        f"Previously seen jobs: "
        f"{len(seen)}"
    )

    # -----------------------------------------------------
    # SEARCH ALL BIOMEDICAL QUERIES
    # -----------------------------------------------------

    all_jobs = []

    for query in SEARCH_QUERIES:

        print(
            f"Searching Egypt: {query}"
        )

        results = search_linkedin(
            query
        )

        print(
            f"  Found: {len(results)}"
        )

        all_jobs.extend(
            results
        )

    print(
        f"\nTotal raw jobs: "
        f"{len(all_jobs)}"
    )

    # -----------------------------------------------------
    # DEDUPLICATE
    # -----------------------------------------------------

    all_jobs = deduplicate(
        all_jobs
    )

    print(
        f"After deduplication: "
        f"{len(all_jobs)}"
    )

    # -----------------------------------------------------
    # CLASSIFY
    # -----------------------------------------------------

    qualified_jobs = []

    for job in all_jobs:

        score = classify_job(
            job
        )

        if score is not None:

            job["score"] = score

            qualified_jobs.append(
                job
            )

    print(
        f"Qualified Biomedical jobs: "
        f"{len(qualified_jobs)}"
    )

    # -----------------------------------------------------
    # SORT BY RELEVANCE
    # -----------------------------------------------------

    qualified_jobs.sort(

        key=lambda x: x.get(
            "score",
            0
        ),

        reverse=True

    )

    # -----------------------------------------------------
    # SEPARATE NEW / OLD
    # -----------------------------------------------------

    new_jobs = []

    old_jobs = []

    for job in qualified_jobs:

        job_id = str(

            job.get("id")
            or job.get("url")

        )

        if job_id in seen:

            old_jobs.append(
                job
            )

        else:

            new_jobs.append(
                job
            )

    print(
        f"New qualified jobs: "
        f"{len(new_jobs)}"
    )

    print(
        f"Previously seen qualified jobs: "
        f"{len(old_jobs)}"
    )

    # -----------------------------------------------------
    # SELECT TOP 10
    #
    # NEW JOBS FIRST
    # THEN OLD QUALIFIED JOBS
    # -----------------------------------------------------

    selected_jobs = []

    used_ids = set()

    # First: new jobs
    for job in new_jobs:

        job_id = str(

            job.get("id")
            or job.get("url")

        )

        if job_id in used_ids:

            continue

        selected_jobs.append(
            job
        )

        used_ids.add(
            job_id
        )

        if len(selected_jobs) >= TOP_N:

            break

    # Second: old jobs to fill remaining slots
    if len(selected_jobs) < TOP_N:

        for job in old_jobs:

            job_id = str(

                job.get("id")
                or job.get("url")

            )

            if job_id in used_ids:

                continue

            selected_jobs.append(
                job
            )

            used_ids.add(
                job_id
            )

            if len(selected_jobs) >= TOP_N:

                break

    selected_jobs = selected_jobs[
        :TOP_N
    ]

    # -----------------------------------------------------
    # PRINT FINAL SELECTION
    # -----------------------------------------------------

    print(
        f"Selected jobs for Telegram: "
        f"{len(selected_jobs)}"
    )

    for index, job in enumerate(
        selected_jobs,
        start=1
    ):

        print(
            f"{index}. "
            f"{job.get('title')} "
            f"| {job.get('company')} "
            f"| Score: "
            f"{job.get('score')}"
        )

    # -----------------------------------------------------
    # IF NO JOBS
    # -----------------------------------------------------

    if not selected_jobs:

        message = (

            "🇪🇬 🧬 "
            "<b>Biomedical Engineering "
            "Jobs in Egypt</b>\n\n"

            "No qualified Biomedical "
            "Engineering jobs were found "
            "today."

        )

        try:

            send_telegram(
                message
            )

            print(
                "No-jobs message sent."
            )

        except Exception as e:

            print(
                f"Telegram error: {e}"
            )

            return

        save_seen(
            seen
        )

        return

    # -----------------------------------------------------
    # FETCH APPLICANTS
    # -----------------------------------------------------

    for index, job in enumerate(

        selected_jobs,

        start=1

    ):

        print(

            f"Fetching applicants "
            f"{index}/"
            f"{len(selected_jobs)}: "
            f"{job.get('title')}"

        )

        job["applicants"] = (
            fetch_applicants(
                job.get("url")
            )
        )

    # -----------------------------------------------------
    # BUILD TELEGRAM MESSAGE
    # -----------------------------------------------------

    message = build_message(
        selected_jobs
    )

    # -----------------------------------------------------
    # SEND TELEGRAM
    # -----------------------------------------------------

    try:

        send_telegram(
            message
        )

        print(
            "\nTelegram message "
            "sent successfully."
        )

    except Exception as e:

        print(
            f"\nTelegram error: {e}"
        )

        # Do not mark jobs as seen
        # if Telegram failed.
        return

    # -----------------------------------------------------
    # SAVE SELECTED JOBS AS SEEN
    # -----------------------------------------------------

    now = datetime.utcnow().isoformat()

    for job in selected_jobs:

        job_id = str(

            job.get("id")
            or job.get("url")

        )

        seen[job_id] = {

            "seen_at": now,

            "title": job.get(
                "title",
                ""
            ),

            "company": job.get(
                "company",
                ""
            ),

            "url": job.get(
                "url",
                ""
            ),

        }

    # -----------------------------------------------------
    # SAVE SEEN
    # -----------------------------------------------------

    save_seen(
        seen
    )

    print(
        f"Saved "
        f"{len(selected_jobs)} jobs "
        f"to seen_jobs.json."
    )

    print(
        "\nJOB SEARCH SCRIPT FINISHED"
    )


# =========================================================
# RUN SCRIPT
# =========================================================

if __name__ == "__main__":

    main()
