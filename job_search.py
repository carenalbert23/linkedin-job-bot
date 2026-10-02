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
# ============================================================

SEARCH_QUERIES = [

    # DIRECT BIOMEDICAL
    "Biomedical Engineer",
    "Biomedical Engineering",
    "Biomedical Equipment Engineer",
    "Biomedical Service Engineer",
    "Biomedical Maintenance Engineer",
    "Biomedical Field Service Engineer",

    # MEDICAL DEVICES
    "Medical Device Engineer",
    "Medical Devices Engineer",
    "Medical Device Service Engineer",
    "Medical Device Field Service Engineer",

    # MEDICAL EQUIPMENT
    "Medical Equipment Engineer",
    "Medical Equipment Service Engineer",
    "Medical Equipment Field Service Engineer",

    # CLINICAL ENGINEERING
    "Clinical Engineer",
    "Clinical Engineering",

    # MEDICAL IMAGING
    "Medical Imaging Engineer",
    "Imaging Engineer Medical",
    "Medical Imaging Service Engineer",

    # MEDICAL INSTRUMENTATION
    "Medical Instrumentation Engineer",
    "Biomedical Instrumentation Engineer",

    # MEDICAL SERVICE
    "Field Service Engineer Medical Devices",
    "Field Service Engineer Medical Equipment",
    "Service Engineer Medical Devices",
    "Service Engineer Medical Equipment",
]


# ============================================================
# DIRECT BIOMEDICAL TITLE TERMS
# ============================================================

DIRECT_BIOMEDICAL = {

    "biomedical engineer": 200,
    "biomedical engineering": 190,

    "biomedical equipment engineer": 200,
    "biomedical service engineer": 200,
    "biomedical maintenance engineer": 190,
    "biomedical field service engineer": 200,

    "medical device engineer": 185,
    "medical devices engineer": 185,

    "medical device service engineer": 185,
    "medical device field service engineer": 190,

    "medical equipment engineer": 180,
    "medical equipment service engineer": 185,
    "medical equipment field service engineer": 190,

    "clinical engineer": 180,
    "clinical engineering": 175,

    "medical imaging engineer": 180,
    "medical imaging service engineer": 180,

    "medical instrumentation engineer": 175,
    "biomedical instrumentation engineer": 185,
}


# ============================================================
# MEDICAL DEVICE / EQUIPMENT TERMS
# ============================================================

MEDICAL_DEVICE_TERMS = {

    "medical device": 80,
    "medical devices": 80,

    "medical equipment": 80,

    "biomedical equipment": 90,

    "medical imaging": 75,

    "medical instrumentation": 75,

    "clinical engineering": 80,

    "hospital equipment": 60,

    "diagnostic equipment": 60,

}


# ============================================================
# MEDICAL TECHNOLOGY TERMS
# ============================================================

MEDICAL_TECH_TERMS = {

    "ultrasound": 30,
    "mri": 30,
    "x-ray": 30,
    "xray": 30,
    "ct scanner": 30,
    "computed tomography": 30,

    "radiology": 25,

    "ecg": 25,
    "eeg": 25,

    "patient monitor": 30,
    "patient monitoring": 30,

    "ventilator": 30,
    "dialysis": 30,
    "infusion pump": 30,
    "anesthesia machine": 30,
    "defibrillator": 30,

}


# ============================================================
# CONDITIONAL ENGINEERING TITLES
#
# These are NOT accepted by themselves.
# They need strong medical-device context.
# ============================================================

CONDITIONAL_ENGINEERING = {

    "field service engineer": 90,
    "service engineer": 75,
    "technical service engineer": 70,
    "maintenance engineer": 60,
    "application engineer": 45,
    "equipment engineer": 70,

}


# ============================================================
# HARD EXCLUSIONS
# ============================================================

HARD_EXCLUDE = [

    # SALES
    "sales engineer",
    "sales representative",
    "sales specialist",
    "sales manager",
    "medical sales",
    "sales",

    # MARKETING
    "marketing",
    "brand manager",

    # PRODUCT / COMMERCIAL
    "product specialist",
    "product manager",
    "product executive",
    "business development",

    # REGULATORY
    "regulatory affairs",
    "regulatory specialist",
    "regulatory associate",
    "regulatory officer",

    # QUALITY
    "quality assurance",
    "quality control",
    "qa specialist",
    "qc specialist",

    # HR
    "human resources",
    "hr specialist",
    "recruiter",
    "recruitment",

    # FINANCE
    "accountant",
    "accounting",
    "finance",

    # PROCUREMENT
    "procurement",
    "purchasing",

    # CUSTOMER SERVICE
    "customer service",

    # PHARMACY
    "pharmacist",
    "pharmacy",

    # LAB
    "laboratory technician",
    "lab technician",
    "laboratory specialist",
    "lab specialist",

    # IT / SOFTWARE
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

    # OTHER ENGINEERING
    "civil engineer",
    "structural engineer",
    "mechanical engineer",
    "electrical engineer",
    "electronics engineer",
    "chemical engineer",
    "industrial engineer",
    "process engineer",
    "automotive engineer",

    # MANUFACTURING
    "production engineer",
    "manufacturing engineer",

    # CONSTRUCTION
    "construction engineer",
    "architect",

]


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

                cleaned[
                    job_id
                ] = timestamp

        except:

            pass

    return cleaned


# ============================================================
# CLEAN TEXT
# ============================================================

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

                job = parse_job(
                    card
                )

                if job:

                    results.append(
                        job
                    )

                    page_count += 1


            print(
                f"  Parsed: "
                f"{page_count}"
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
                job["title"].lower()
                + "|"
                + job["company"].lower()
                + "|"
                + job["location"].lower()
            )


        if key not in unique:

            unique[key] = job


    return list(
        unique.values()
    )


# ============================================================
# CHECK HARD EXCLUSION
# ============================================================

def is_hard_excluded(title):

    title = title.lower()

    for word in HARD_EXCLUDE:

        if word in title:

            return True

    return False


# ============================================================
# CHECK IF JOB IS BIOMEDICAL
# ============================================================

def classify_job(job):

    title = job["title"].lower()

    company = job["company"].lower()

    location = job["location"].lower()


    full_text = (
        title
        + " "
        + company
        + " "
        + location
    )


    # --------------------------------------------------------
    # HARD EXCLUSION FIRST
    # --------------------------------------------------------

    if is_hard_excluded(title):

        return False, 0, "excluded"


    # --------------------------------------------------------
    # TIER 1
    # DIRECT BIOMEDICAL TITLE
    # --------------------------------------------------------

    for keyword, points in DIRECT_BIOMEDICAL.items():

        if keyword in title:

            score = points

            # Extra location bonus

            if "cairo" in location:
                score += 20

            if "giza" in location:
                score += 20

            if "egypt" in location:
                score += 15

            return True, score, "direct"


    # --------------------------------------------------------
    # TIER 2
    # MEDICAL DEVICE / EQUIPMENT ENGINEERING
    # --------------------------------------------------------

    has_engineering_word = any(
        word in title
        for word in [
            "engineer",
            "engineering"
        ]
    )


    has_medical_device_context = any(
        word in full_text
        for word in [
            "medical device",
            "medical devices",
            "medical equipment",
            "biomedical equipment",
            "medical imaging",
            "medical instrumentation",
            "clinical engineering",
            "hospital equipment",
        ]
    )


    if (
        has_engineering_word
        and has_medical_device_context
    ):

        score = 120


        for word, points in MEDICAL_DEVICE_TERMS.items():

            if word in full_text:

                score += points


        if "cairo" in location:
            score += 20

        if "giza" in location:
            score += 20


        return True, score, "medical-device-engineering"


    # --------------------------------------------------------
    # TIER 3
    # FIELD / SERVICE ENGINEER
    #
    # Accepted ONLY when medical equipment/device
    # context exists.
    # --------------------------------------------------------

    has_service_role = any(
        word in title
        for word in [
            "field service engineer",
            "service engineer",
            "technical service engineer",
            "maintenance engineer",
            "equipment engineer",
        ]
    )


    has_strong_medical_context = any(
        word in full_text
        for word in [
            "medical device",
            "medical devices",
            "medical equipment",
            "biomedical",
            "ultrasound",
            "mri",
            "x-ray",
            "xray",
            "ct scanner",
            "radiology",
            "ecg",
            "eeg",
            "patient monitor",
            "ventilator",
            "dialysis",
            "infusion pump",
            "anesthesia",
            "defibrillator",
        ]
    )


    if (
        has_service_role
        and has_strong_medical_context
    ):

        score = 100


        for word, points in MEDICAL_TECH_TERMS.items():

            if word in full_text:

                score += points


        if "cairo" in location:
            score += 20

        if "giza" in location:
            score += 20


        return True, score, "medical-service-engineering"


    # --------------------------------------------------------
    # OTHERWISE
    # --------------------------------------------------------

    return False, 0, "not-biomedical"


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

                except:

                    pass


    except:

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


    message = (
        "🇪🇬 🧬 "
        "<b>Top 10 Biomedical Engineering "
        "Jobs in Egypt</b>\n"
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
        "🤖 <i>Strictly filtered for "
        "Biomedical Engineering, Medical Devices "
        "and Medical Equipment Engineering.</i>"
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
    # DEDUP
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
    # SELECT TOP 10
    #
    # New first.
    # Old jobs fill remaining slots.
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
    # FINAL SORT
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
            "The bot rejected unrelated medical, "
            "sales, regulatory and non-engineering roles."
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
