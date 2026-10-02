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

# Maximum number of jobs sent
TOP_N = 10

# Search last 30 days
LINKEDIN_TIME_FILTER = "r2592000"

# LinkedIn pagination
PAGE_SIZE = 25
MAX_SEARCH_PAGES = 10

LINKEDIN_URL = (
    "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


# ============================================================
# SEARCH QUERIES
#
# IMPORTANT:
# Only specific Biomedical / Medical Device / Medical
# Equipment engineering searches are used.
# ============================================================

SEARCH_QUERIES = [

    # ---------------- DIRECT BIOMEDICAL ----------------

    "Biomedical Engineer",
    "Biomedical Engineering",
    "Biomedical Equipment Engineer",
    "Biomedical Service Engineer",
    "Biomedical Maintenance Engineer",
    "Biomedical Field Service Engineer",

    # ---------------- MEDICAL DEVICES ----------------

    "Medical Device Engineer",
    "Medical Devices Engineer",
    "Medical Device Service Engineer",
    "Medical Device Field Service Engineer",

    # ---------------- MEDICAL EQUIPMENT ----------------

    "Medical Equipment Engineer",
    "Medical Equipment Service Engineer",
    "Medical Equipment Field Service Engineer",

    # ---------------- CLINICAL ENGINEERING ----------------

    "Clinical Engineer",
    "Clinical Engineering",

    # ---------------- MEDICAL IMAGING ----------------

    "Medical Imaging Engineer",
    "Medical Imaging Service Engineer",

    # ---------------- MEDICAL INSTRUMENTATION ----------------

    "Medical Instrumentation Engineer",
    "Biomedical Instrumentation Engineer",

    # ---------------- SERVICE ENGINEERING ----------------

    "Field Service Engineer Medical Devices",
    "Field Service Engineer Medical Equipment",
    "Service Engineer Medical Devices",
    "Service Engineer Medical Equipment",
]


# ============================================================
# DIRECT BIOMEDICAL TITLE PATTERNS
#
# A job is directly accepted when its TITLE contains one
# of these patterns.
# ============================================================

DIRECT_BIOMEDICAL_PATTERNS = [

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
    "medical imaging service engineer",

    "medical instrumentation engineer",
    "biomedical instrumentation engineer",
]


# ============================================================
# ENGINEERING ROLES THAT NEED MEDICAL CONTEXT
#
# These NEVER qualify by themselves.
# ============================================================

CONDITIONAL_ENGINEERING_ROLES = [

    "field service engineer",
    "service engineer",
    "technical service engineer",
    "maintenance engineer",
    "equipment engineer",
]


# ============================================================
# MEDICAL CONTEXT ALLOWED FOR CONDITIONAL ENGINEERING
#
# IMPORTANT:
# The context must appear in the JOB TITLE itself.
#
# We deliberately DO NOT use company/location/score
# to turn a generic engineering job into Biomedical.
# ============================================================

MEDICAL_CONTEXT_IN_TITLE = [

    "medical device",
    "medical devices",

    "medical equipment",

    "biomedical",

    "clinical",

    "medical imaging",

    "medical instrumentation",

    "hospital equipment",

    "diagnostic equipment",

    "patient monitor",
    "patient monitoring",

    "ultrasound",
    "mri",

    "x-ray",
    "xray",

    "ct scanner",
    "computed tomography",

    "radiology",

    "ecg",
    "eeg",

    "ventilator",
    "dialysis",

    "infusion pump",

    "anesthesia machine",
    "anesthesia",

    "defibrillator",
]


# ============================================================
# HARD EXCLUSIONS
#
# These are rejected BEFORE any Biomedical matching.
# ============================================================

HARD_EXCLUDE = [

    # ---------------- SALES ----------------

    "sales engineer",
    "sales representative",
    "sales specialist",
    "sales manager",
    "medical sales",
    "sales",

    # ---------------- MARKETING ----------------

    "marketing",
    "brand manager",

    # ---------------- PRODUCT / COMMERCIAL ----------------

    "product specialist",
    "product manager",
    "product executive",
    "business development",

    # ---------------- REGULATORY ----------------

    "regulatory affairs",
    "regulatory specialist",
    "regulatory associate",
    "regulatory officer",
    "regulatory manager",

    # ---------------- QUALITY ----------------

    "quality assurance",
    "quality control",
    "qa specialist",
    "qc specialist",
    "quality specialist",
    "quality engineer",

    # ---------------- HR ----------------

    "human resources",
    "hr specialist",
    "hr manager",
    "recruiter",
    "recruitment",

    # ---------------- FINANCE ----------------

    "accountant",
    "accounting",
    "finance",
    "financial",

    # ---------------- PROCUREMENT ----------------

    "procurement",
    "purchasing",

    # ---------------- CUSTOMER SERVICE ----------------

    "customer service",
    "customer support",

    # ---------------- PHARMACY ----------------

    "pharmacist",
    "pharmacy",

    # ---------------- LAB ----------------

    "laboratory technician",
    "lab technician",
    "laboratory specialist",
    "lab specialist",

    # ---------------- IT / SOFTWARE ----------------

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
    "cyber security",
    "it specialist",
    "information technology",

    # ---------------- OTHER ENGINEERING ----------------

    "civil engineer",
    "structural engineer",
    "mechanical engineer",
    "electrical engineer",
    "electronics engineer",
    "chemical engineer",
    "industrial engineer",
    "process engineer",
    "automotive engineer",

    # ---------------- MANUFACTURING ----------------

    "production engineer",
    "manufacturing engineer",

    # ---------------- CONSTRUCTION ----------------

    "construction engineer",
    "architect",

    # ---------------- OTHER NON-BIOMEDICAL ----------------

    "account manager",
    "project manager",
    "operations manager",
    "administrative",
]


# ============================================================
# SCORE VALUES
# ============================================================

DIRECT_SCORES = {

    "biomedical engineer": 200,
    "biomedical engineering": 195,

    "biomedical equipment engineer": 200,
    "biomedical service engineer": 200,
    "biomedical maintenance engineer": 195,
    "biomedical field service engineer": 200,

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
    "medical imaging service engineer": 190,

    "medical instrumentation engineer": 180,
    "biomedical instrumentation engineer": 190,
}


# ============================================================
# TEXT NORMALIZATION
# ============================================================

def normalize_text(text):

    if not text:
        return ""

    text = html.unescape(text)

    text = text.lower()

    text = text.replace("&", " and ")

    # Normalize common punctuation
    text = re.sub(
        r"[-_/|(),:]+",
        " ",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


def clean(text):

    if not text:
        return ""

    text = html.unescape(text)

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# ============================================================
# LOAD SEEN JOBS
# ============================================================

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

        if isinstance(data, list):

            return {
                str(x): datetime.now().isoformat()
                for x in data
            }

    except Exception as e:

        print(
            "Error loading seen_jobs.json:",
            e
        )

    return {}


def save_seen(seen):

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


def cleanup_seen(seen):

    cutoff = (
        datetime.now()
        - timedelta(days=30)
    )

    cleaned = {}

    for job_id, timestamp in seen.items():

        try:

            date = datetime.fromisoformat(
                timestamp
            )

            if date >= cutoff:

                cleaned[job_id] = timestamp

        except Exception:

            pass

    return cleaned


# ============================================================
# PARSE LINKEDIN CARD
# ============================================================

def parse_job(card):

    try:

        title_el = (
            card.select_one(
                "h3.base-search-card__title"
            )
            or
            card.select_one(
                ".base-search-card__title"
            )
            or
            card.select_one("h3")
        )

        company_el = (
            card.select_one(
                "h4.base-search-card__subtitle"
            )
            or
            card.select_one(
                ".base-search-card__subtitle"
            )
            or
            card.select_one("h4")
        )

        location_el = (
            card.select_one(
                ".job-search-card__location"
            )
            or
            card.select_one(
                ".base-search-card__metadata"
            )
        )

        link_el = (
            card.select_one(
                "a.base-card__full-link"
            )
            or
            card.select_one(
                "a[href*='/jobs/view/']"
            )
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

            url = (
                link_el.get(
                    "href",
                    ""
                )
                .split("?")[0]
                .strip()
            )

        match = re.search(
            r"/jobs/view/(\d+)",
            url
        )

        job_id = (
            match.group(1)
            if match
            else None
        )

        if not title or not url:

            return None

        return {

            "id": job_id,

            "title": title,

            "company": company,

            "location": location,

            "url": url,

        }

    except Exception as e:

        print(
            "Parse error:",
            e
        )

        return None


# ============================================================
# SEARCH LINKEDIN
# ============================================================

def search_linkedin(query):

    results = []

    print()
    print(
        f"SEARCHING: {query}"
    )

    for page in range(
        MAX_SEARCH_PAGES
    ):

        start = (
            page
            * PAGE_SIZE
        )

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

            print(
                f"  Page {page + 1}: "
                f"HTTP {response.status_code}"
            )

            if response.status_code != 200:

                continue

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

            if not cards:

                print(
                    "  No cards found."
                )

                break

            page_count = 0

            for card in cards:

                job = parse_job(card)

                if job:

                    results.append(job)

                    page_count += 1

            print(
                f"  Parsed: {page_count}"
            )

            if len(cards) < PAGE_SIZE:

                break

        except Exception as e:

            print(
                "  Error:",
                e
            )

    return results


# ============================================================
# DEDUPLICATE
# ============================================================

def deduplicate(jobs):

    unique = {}

    for job in jobs:

        if job.get("id"):

            key = (
                "id:"
                + str(job["id"])
            )

        else:

            key = (
                normalize_text(
                    job["title"]
                )
                + "|"
                + normalize_text(
                    job["company"]
                )
                + "|"
                + normalize_text(
                    job["location"]
                )
            )

        if key not in unique:

            unique[key] = job

    return list(
        unique.values()
    )


# ============================================================
# HARD EXCLUSION
# ============================================================

def is_hard_excluded(title):

    title_normalized = normalize_text(
        title
    )

    for excluded in HARD_EXCLUDE:

        excluded_normalized = normalize_text(
            excluded
        )

        if excluded_normalized in title_normalized:

            return True

    return False


# ============================================================
# CHECK DIRECT BIOMEDICAL TITLE
# ============================================================

def get_direct_match(title):

    normalized_title = normalize_text(
        title
    )

    matches = []

    for pattern in DIRECT_BIOMEDICAL_PATTERNS:

        pattern_normalized = normalize_text(
            pattern
        )

        if pattern_normalized in normalized_title:

            matches.append(
                pattern_normalized
            )

    if not matches:

        return None

    # Prefer the longest/more specific match
    matches.sort(
        key=len,
        reverse=True
    )

    return matches[0]


# ============================================================
# CHECK CONDITIONAL ENGINEERING ROLE
# ============================================================

def get_conditional_role(title):

    normalized_title = normalize_text(
        title
    )

    matches = []

    for role in CONDITIONAL_ENGINEERING_ROLES:

        role_normalized = normalize_text(
            role
        )

        if role_normalized in normalized_title:

            matches.append(
                role_normalized
            )

    if not matches:

        return None

    matches.sort(
        key=len,
        reverse=True
    )

    return matches[0]


# ============================================================
# CHECK MEDICAL CONTEXT IN TITLE
# ============================================================

def get_medical_context(title):

    normalized_title = normalize_text(
        title
    )

    matches = []

    for context in MEDICAL_CONTEXT_IN_TITLE:

        context_normalized = normalize_text(
            context
        )

        if context_normalized in normalized_title:

            matches.append(
                context_normalized
            )

    if not matches:

        return None

    matches.sort(
        key=len,
        reverse=True
    )

    return matches[0]


# ============================================================
# CLASSIFY JOB
#
# VERY STRICT:
#
# 1. Hard exclusion
# 2. Direct Biomedical title
# 3. Conditional engineering + medical context IN TITLE
# 4. Otherwise reject
#
# Company/location NEVER make a job Biomedical.
# ============================================================

def classify_job(job):

    title = job.get(
        "title",
        ""
    )

    normalized_title = normalize_text(
        title
    )

    # --------------------------------------------------------
    # 1. HARD EXCLUSION
    # --------------------------------------------------------

    if is_hard_excluded(title):

        return (
            False,
            0,
            "excluded"
        )


    # --------------------------------------------------------
    # 2. DIRECT BIOMEDICAL
    # --------------------------------------------------------

    direct_match = get_direct_match(
        title
    )

    if direct_match:

        score = DIRECT_SCORES.get(
            direct_match,
            180
        )

        return (
            True,
            score,
            "direct-biomedical"
        )


    # --------------------------------------------------------
    # 3. CONDITIONAL ENGINEERING
    #
    # Example ACCEPT:
    #
    # "Field Service Engineer - Medical Equipment"
    #
    # Example REJECT:
    #
    # "Field Service Engineer"
    #
    # Example REJECT:
    #
    # "Service Engineer - General Equipment"
    # --------------------------------------------------------

    conditional_role = get_conditional_role(
        title
    )

    if conditional_role:

        medical_context = get_medical_context(
            title
        )

        if medical_context:

            score = 120

            # Stronger score for explicit biomedical
            if "biomedical" in normalized_title:

                score += 35

            # Medical device/equipment
            if (
                "medical device" in normalized_title
                or
                "medical devices" in normalized_title
            ):

                score += 30

            if "medical equipment" in normalized_title:

                score += 30

            if "clinical" in normalized_title:

                score += 25

            if (
                "medical imaging" in normalized_title
                or
                "medical instrumentation" in normalized_title
            ):

                score += 25

            return (
                True,
                score,
                "medical-engineering"
            )


    # --------------------------------------------------------
    # 4. EVERYTHING ELSE = REJECT
    # --------------------------------------------------------

    return (
        False,
        0,
        "not-biomedical"
    )


# ============================================================
# APPLICANT COUNT
# ============================================================

def fetch_applicants(url):

    try:

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=10
        )

        if response.status_code != 200:

            return None

        text = response.text

        patterns = [

            r"([\d,]+)\s+applicants",

            r"([\d,]+)\s+applicant",

            r"Over\s+([\d,]+)\s+applicants",

        ]

        for pattern in patterns:

            match = re.search(
                pattern,
                text,
                re.IGNORECASE
            )

            if match:

                try:

                    return int(
                        match.group(1)
                        .replace(",", "")
                    )

                except Exception:

                    pass

    except Exception:

        pass

    return None


# ============================================================
# TELEGRAM
# ============================================================

def send_telegram(message):

    if not TELEGRAM_TOKEN:

        print(
            "ERROR: TELEGRAM_TOKEN missing."
        )

        return False

    if not TELEGRAM_CHAT_ID:

        print(
            "ERROR: TELEGRAM_CHAT_ID missing."
        )

        return False

    url = (
        "https://api.telegram.org/"
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
            json=payload,
            timeout=20
        )

        print(
            "Telegram status:",
            response.status_code
        )

        if response.status_code == 200:

            return True

        print(
            "Telegram error:",
            response.text
        )

        return False

    except Exception as e:

        print(
            "Telegram error:",
            e
        )

        return False


# ============================================================
# TELEGRAM MESSAGE
# ============================================================

def build_message(jobs):

    today = datetime.now().strftime(
        "%Y-%m-%d"
    )

    count = len(jobs)

    message = (
        "🇪🇬 🧬 "
        f"<b>Biomedical Engineering Jobs in Egypt "
        f"({count})</b>\n"
        f"📅 {today}\n\n"
    )

    for index, job in enumerate(
        jobs,
        1
    ):

        title = html.escape(
            job["title"]
        )

        company = html.escape(
            job["company"]
            or "Unknown"
        )

        location = html.escape(
            job["location"]
            or "Egypt"
        )

        applicants = job.get(
            "applicants"
        )

        applicant_line = ""

        if applicants is not None:

            applicant_line = (
                f"👥 Applicants: "
                f"{applicants}\n"
            )

        message += (

            f"<b>{index}. "
            f"{title}</b>\n"

            f"🏢 {company}\n"

            f"📍 {location}\n"

            f"{applicant_line}"

            f"⭐ Match Score: "
            f"{job['score']}\n"

            f"🔗 <a href=\""
            f"{html.escape(job['url'])}"
            f"\">View Job</a>\n\n"

        )

    message += (
        "🤖 <i>Strict Biomedical Engineering "
        "filter. Non-engineering medical roles, "
        "regulatory, sales, product and unrelated "
        "engineering roles are excluded.</i>"
    )

    return message


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 70)
    print(
        "BIOMEDICAL JOB SEARCH STARTED"
    )
    print("=" * 70)

    # --------------------------------------------------------
    # SEEN
    # --------------------------------------------------------

    seen = cleanup_seen(
        load_seen()
    )

    print(
        "Seen jobs:",
        len(seen)
    )

    # --------------------------------------------------------
    # SEARCH
    # --------------------------------------------------------

    all_jobs = []

    for query in SEARCH_QUERIES:

        results = search_linkedin(
            query
        )

        all_jobs.extend(
            results
        )

    # --------------------------------------------------------
    # DEDUPLICATE
    # --------------------------------------------------------

    all_jobs = deduplicate(
        all_jobs
    )

    print()
    print(
        "UNIQUE LINKEDIN JOBS:",
        len(all_jobs)
    )

    # --------------------------------------------------------
    # CLASSIFY
    # --------------------------------------------------------

    qualified = []

    rejected = 0

    for job in all_jobs:

        accepted, score, tier = classify_job(
            job
        )

        if accepted:

            job["score"] = score

            job["tier"] = tier

            qualified.append(
                job
            )

        else:

            rejected += 1

    print(
        "REJECTED NON-BIOMEDICAL JOBS:",
        rejected
    )

    print(
        "QUALIFIED BIOMEDICAL JOBS:",
        len(qualified)
    )

    # --------------------------------------------------------
    # SORT
    # --------------------------------------------------------

    qualified.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    # --------------------------------------------------------
    # NEW / OLD
    # --------------------------------------------------------

    new_jobs = []

    old_jobs = []

    for job in qualified:

        job_id = job.get(
            "id"
        )

        if (
            job_id
            and str(job_id) in seen
        ):

            old_jobs.append(
                job
            )

        else:

            new_jobs.append(
                job
            )

    print(
        "NEW QUALIFIED JOBS:",
        len(new_jobs)
    )

    print(
        "OLD QUALIFIED JOBS:",
        len(old_jobs)
    )

    # --------------------------------------------------------
    # SELECT
    #
    # NEW JOBS FIRST.
    #
    # OLD QUALIFIED JOBS ONLY FILL REMAINING SLOTS.
    #
    # IMPORTANT:
    # No unrelated jobs are ever added just to reach 10.
    # --------------------------------------------------------

    selected = []

    selected.extend(
        new_jobs[:TOP_N]
    )

    if len(selected) < TOP_N:

        remaining = (
            TOP_N
            - len(selected)
        )

        selected.extend(
            old_jobs[:remaining]
        )

    # --------------------------------------------------------
    # FINAL DEDUP + SORT
    # --------------------------------------------------------

    selected = deduplicate(
        selected
    )

    selected.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    selected = selected[:TOP_N]

    print()
    print("=" * 70)
    print(
        "FINAL JOB COUNT:",
        len(selected)
    )
    print("=" * 70)

    for i, job in enumerate(
        selected,
        1
    ):

        print(
            f"{i}. "
            f"{job['title']} | "
            f"{job['company']} | "
            f"{job['tier']} | "
            f"Score={job['score']}"
        )

    # --------------------------------------------------------
    # NO QUALIFIED JOBS
    # --------------------------------------------------------

    if not selected:

        message = (
            "🇪🇬 🧬 "
            "<b>No qualified Biomedical "
            "Engineering jobs found in Egypt.</b>\n\n"
            f"📅 {datetime.now().strftime('%Y-%m-%d')}\n\n"
            "The strict filter rejected unrelated "
            "medical, regulatory, sales, product "
            "and non-engineering roles."
        )

        send_telegram(
            message
        )

        return

    # --------------------------------------------------------
    # FETCH APPLICANTS
    # --------------------------------------------------------

    print(
        "Fetching applicant counts..."
    )

    for job in selected:

        job["applicants"] = (
            fetch_applicants(
                job["url"]
            )
        )

    # --------------------------------------------------------
    # SEND TELEGRAM
    # --------------------------------------------------------

    message = build_message(
        selected
    )

    success = send_telegram(
        message
    )

    # --------------------------------------------------------
    # SAVE SEEN
    # --------------------------------------------------------

    if success:

        now = datetime.now().isoformat()

        for job in selected:

            if job.get("id"):

                seen[
                    str(job["id"])
                ] = now

        save_seen(
            cleanup_seen(
                seen
            )
        )

        print(
            "seen_jobs.json updated."
        )

    else:

        print(
            "Telegram failed. "
            "Jobs were NOT marked as seen."
        )

    print()
    print("=" * 70)
    print(
        "JOB SEARCH FINISHED"
    )
    print("=" * 70)


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    main()

