import os
import re
import json
import html
import requests

from bs4 import BeautifulSoup
from datetime import datetime, timedelta


# ============================================================
# CONFIGURATION
# ============================================================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

SEEN_JOBS_FILE = "seen_jobs.json"

TOP_N = 10

# Search jobs posted during the last 30 days
LINKEDIN_TIME_FILTER = "r2592000"

# LinkedIn guest API pagination
PAGE_SIZE = 25
MAX_SEARCH_PAGES = 10

# Applicant count
APPLICANT_FETCH_LIMIT = 10

LINKEDIN_URL = (
    "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
)


# ============================================================
# SEARCH TERMS
# ============================================================

LINKEDIN_SEARCHES = [

    # Direct Biomedical
    "Biomedical Engineer",
    "Biomedical Engineering",
    "Biomedical",
    "Biomedical Equipment Engineer",
    "Biomedical Service Engineer",

    # Medical Devices
    "Medical Device Engineer",
    "Medical Devices Engineer",
    "Medical Devices",
    "Medical Equipment Engineer",
    "Medical Equipment",

    # Clinical
    "Clinical Engineer",
    "Clinical Engineering",

    # Imaging
    "Medical Imaging Engineer",
    "Imaging Engineer",
    "Medical Imaging",

    # Field / Service
    "Field Service Engineer Medical Devices",
    "Field Service Engineer Medical",
    "Biomedical Field Service Engineer",
    "Medical Equipment Service Engineer",
    "Service Engineer Medical Devices",
    "Service Engineer Medical",

    # Technology / Instrumentation
    "Medical Technology",
    "Medical Technology Engineer",
    "Healthcare Technology Engineer",
    "Medical Instrumentation Engineer",

    # Equipment
    "Equipment Engineer Medical",
    "Medical Equipment Service",

]


# ============================================================
# HTTP HEADERS
# ============================================================

LINKEDIN_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


# ============================================================
# STRONG BIOMEDICAL TITLES
# ============================================================

STRONG_TITLE_KEYWORDS = [

    "biomedical engineer",
    "biomedical engineering",
    "biomedical equipment engineer",
    "biomedical service engineer",
    "biomedical field service engineer",

    "medical device engineer",
    "medical devices engineer",

    "clinical engineer",
    "clinical engineering",

    "medical equipment engineer",
    "medical equipment service engineer",

    "medical imaging engineer",
    "medical instrumentation engineer",

]


# ============================================================
# BIOMEDICAL / MEDICAL CONTEXT
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
    "medical technology",

    "patient monitoring",
    "patient monitor",

    "ventilator",
    "dialysis",
    "infusion pump",
    "anesthesia",
    "defibrillator",

    "ultrasound",
    "mri",
    "x-ray",
    "xray",
    "radiology",
    "ct scanner",
    "computed tomography",

    "ecg",
    "eeg",

    "surgical equipment",
    "surgical devices",

    "diagnostic equipment",
    "diagnostic devices",

    "hospital equipment",
    "hospital devices",

    "life support",

]


# ============================================================
# CONDITIONAL TITLES
# ============================================================

CONDITIONAL_TITLE_KEYWORDS = [

    "field service engineer",
    "service engineer",
    "equipment engineer",

    "technical service engineer",
    "maintenance engineer",

    "application engineer",

    "research engineer",
    "r&d engineer",

]


# ============================================================
# HARD EXCLUSIONS
# ============================================================

# These titles should NOT enter the Biomedical Engineering
# top list unless they contain a very strong Biomedical title.

NEGATIVE_TITLE_KEYWORDS = [

    # Regulatory / legal / compliance
    "regulatory affairs",
    "regulatory specialist",
    "regulatory associate",
    "regulatory officer",
    "compliance specialist",
    "compliance officer",

    # Sales
    "sales engineer",
    "sales specialist",
    "sales representative",
    "sales manager",
    "business development",

    # Marketing
    "marketing",
    "brand manager",

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

    # General customer service
    "customer service",

    # IT / Software
    "software engineer",
    "software developer",
    "web developer",
    "frontend",
    "backend",
    "full stack",
    "data engineer",
    "data analyst",
    "devops",
    "cloud engineer",
    "network engineer",
    "cybersecurity",
    "information technology",
    "it specialist",

    # Other engineering fields
    "civil engineer",
    "structural engineer",
    "mechanical engineer",
    "electrical engineer",
    "electronics engineer",
    "industrial engineer",
    "chemical engineer",
    "process engineer",
    "automotive engineer",

    # Manufacturing
    "production engineer",
    "manufacturing engineer",

    # Construction
    "construction engineer",
    "architect",

]


# ============================================================
# ROLE SCORING
# ============================================================

ROLE_SCORES = {

    "biomedical engineer": 100,
    "biomedical engineering": 95,
    "biomedical equipment engineer": 98,
    "biomedical service engineer": 98,
    "biomedical field service engineer": 98,

    "medical device engineer": 94,
    "medical devices engineer": 94,

    "clinical engineer": 92,
    "clinical engineering": 90,

    "medical equipment engineer": 92,
    "medical equipment service engineer": 94,

    "medical imaging engineer": 94,
    "medical instrumentation engineer": 92,

    "field service engineer": 70,
    "biomedical field service": 90,

    "service engineer": 55,
    "technical service engineer": 65,

    "equipment engineer": 65,
    "maintenance engineer": 45,

    "medical devices": 60,
    "medical device": 60,

    "medical equipment": 60,
    "medical imaging": 60,
    "medical instrumentation": 60,

    "healthcare technology": 45,
    "medical technology": 45,

    "research engineer": 35,
    "r&d engineer": 35,

}


# ============================================================
# MEDICAL SKILL SCORING
# ============================================================

SKILL_SCORES = {

    "biomedical": 35,

    "medical device": 25,
    "medical devices": 25,

    "medical equipment": 25,

    "medical imaging": 25,
    "medical instrumentation": 25,

    "ultrasound": 15,
    "mri": 15,
    "x-ray": 15,
    "xray": 15,
    "ct": 12,
    "radiology": 15,

    "ecg": 12,
    "eeg": 12,

    "patient monitoring": 15,

    "ventilator": 15,
    "dialysis": 15,
    "infusion pump": 15,
    "anesthesia": 15,
    "defibrillator": 15,

    "clinical engineering": 20,
    "healthcare technology": 15,
    "medical technology": 15,

}


# ============================================================
# LOCATION SCORING
# ============================================================

LOCATION_SCORES = {

    "egypt": 30,
    "cairo": 25,
    "giza": 25,
    "alexandria": 22,
    "new cairo": 24,
    "heliopolis": 24,
    "new heliopolis": 24,
    "6th of october": 22,
    "october": 20,

}


# ============================================================
# TEXT CLEANING
# ============================================================

def clean_text(value):
    if not value:
        return ""

    value = html.unescape(value)

    value = re.sub(r"\s+", " ", value)

    return value.strip()


# ============================================================
# SEEN JOBS
# ============================================================

def load_seen_jobs():

    if not os.path.exists(SEEN_JOBS_FILE):
        return {}

    try:

        with open(SEEN_JOBS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            return {str(x): datetime.now().isoformat() for x in data}

        if isinstance(data, dict):
            return data

    except Exception as e:
        print("Could not load seen_jobs.json:", e)

    return {}


def save_seen_jobs(seen_jobs):

    try:

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

    except Exception as e:

        print("Could not save seen_jobs.json:", e)


def cleanup_seen_jobs(seen_jobs):

    cutoff = datetime.now() - timedelta(days=30)

    cleaned = {}

    for job_id, timestamp in seen_jobs.items():

        try:

            dt = datetime.fromisoformat(timestamp)

            if dt >= cutoff:
                cleaned[job_id] = timestamp

        except Exception:
            continue

    return cleaned


# ============================================================
# PARSE JOB CARD
# ============================================================

def parse_card(card):

    try:

        title_el = card.select_one(
            "h3.base-search-card__title"
        )

        if not title_el:
            title_el = card.select_one(
                ".base-search-card__title"
            )

        if not title_el:
            title_el = card.select_one(
                "h3"
            )

        title = clean_text(
            title_el.get_text(" ", strip=True)
            if title_el
            else ""
        )


        company_el = card.select_one(
            "h4.base-search-card__subtitle"
        )

        if not company_el:
            company_el = card.select_one(
                ".base-search-card__subtitle"
            )

        if not company_el:
            company_el = card.select_one(
                "h4"
            )

        company = clean_text(
            company_el.get_text(" ", strip=True)
            if company_el
            else ""
        )


        location_el = card.select_one(
            ".job-search-card__location"
        )

        if not location_el:
            location_el = card.select_one(
                ".base-search-card__metadata"
            )

        location = clean_text(
            location_el.get_text(" ", strip=True)
            if location_el
            else ""
        )


        link_el = card.select_one(
            "a.base-card__full-link"
        )

        if not link_el:
            link_el = card.select_one(
                "a[href*='/jobs/view/']"
            )

        url = ""

        if link_el:

            url = (
                link_el.get("href", "")
                .split("?")[0]
                .strip()
            )


        job_id = None

        match = re.search(
            r"/jobs/view/(\d+)",
            url
        )

        if match:
            job_id = match.group(1)


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

        print("Card parsing error:", e)

        return None


# ============================================================
# SEARCH LINKEDIN
# ============================================================

def search_linkedin(keywords, location="Egypt"):

    results = []

    print()
    print("=" * 70)
    print("SEARCH:", keywords)
    print("LOCATION:", location)
    print("=" * 70)

    for page in range(MAX_SEARCH_PAGES):

        start = page * PAGE_SIZE

        params = {
            "keywords": keywords,
            "location": location,
            "f_TPR": LINKEDIN_TIME_FILTER,
            "start": start,
        }

        try:

            response = requests.get(
                LINKEDIN_URL,
                params=params,
                headers=LINKEDIN_HEADERS,
                timeout=20
            )

            print(
                f"Page {page + 1}/{MAX_SEARCH_PAGES} "
                f"| HTTP {response.status_code} "
                f"| results chars: {len(response.text)}"
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

                print("No cards found on this page.")
                break


            page_results = 0


            for card in cards:

                job = parse_card(card)

                if job:

                    results.append(job)

                    page_results += 1


            print(
                f"Parsed {page_results} jobs from page {page + 1}"
            )


            # If LinkedIn returned less than a full page,
            # there may be no next page.
            if len(cards) < PAGE_SIZE:
                break


        except Exception as e:

            print(
                f"Search error on page {page + 1}:",
                e
            )


    return results


# ============================================================
# JOB DEDUPLICATION
# ============================================================

def deduplicate_jobs(jobs):

    unique = {}

    for job in jobs:

        job_id = job.get("id")

        if job_id:

            key = f"id:{job_id}"

        else:

            key = (
                f"title:{job.get('title','').lower()}|"
                f"company:{job.get('company','').lower()}|"
                f"location:{job.get('location','').lower()}"
            )

        if key not in unique:
            unique[key] = job

    return list(unique.values())


# ============================================================
# JOB RELEVANCE FILTER
# ============================================================

def is_relevant_biomedical_job(job):

    title = job["title"].lower()
    company = job["company"].lower()
    location = job["location"].lower()

    combined = f"{title} {company} {location}"


    # --------------------------------------------------------
    # HARD NEGATIVE TITLES
    # --------------------------------------------------------

    for negative in NEGATIVE_TITLE_KEYWORDS:

        if negative in title:

            # Strong Biomedical title can override only
            # generic negative terms, but NOT regulatory affairs.

            if negative in [
                "regulatory affairs",
                "regulatory specialist",
                "regulatory associate",
                "regulatory officer",
                "compliance specialist",
                "compliance officer",
            ]:

                return False


            has_strong_biomedical = any(
                keyword in title
                for keyword in STRONG_TITLE_KEYWORDS
            )

            if not has_strong_biomedical:
                return False


    # --------------------------------------------------------
    # STRONG DIRECT BIOMEDICAL TITLE
    # --------------------------------------------------------

    for keyword in STRONG_TITLE_KEYWORDS:

        if keyword in title:
            return True


    # --------------------------------------------------------
    # CONDITIONAL MEDICAL SERVICE ROLES
    # --------------------------------------------------------

    has_conditional_role = any(
        keyword in title
        for keyword in CONDITIONAL_TITLE_KEYWORDS
    )

    has_medical_context = any(
        keyword in combined
        for keyword in MEDICAL_CONTEXT_KEYWORDS
    )

    if has_conditional_role and has_medical_context:

        return True


    return False


# ============================================================
# SCORE JOB
# ============================================================

def score_job(job):

    title = job["title"].lower()
    company = job["company"].lower()
    location = job["location"].lower()

    combined = (
        f"{title} {company} {location}"
    )

    score = 0


    # --------------------------------------------------------
    # ROLE SCORE
    # --------------------------------------------------------

    for keyword, points in ROLE_SCORES.items():

        if keyword in title:
            score += points


    # --------------------------------------------------------
    # SKILL SCORE
    # --------------------------------------------------------

    for keyword, points in SKILL_SCORES.items():

        if keyword in combined:
            score += points


    # --------------------------------------------------------
    # LOCATION SCORE
    # --------------------------------------------------------

    for keyword, points in LOCATION_SCORES.items():

        if keyword in location:
            score += points


    # --------------------------------------------------------
    # DIRECT TITLE BONUS
    # --------------------------------------------------------

    if "biomedical engineer" in title:
        score += 40

    elif "biomedical" in title:
        score += 25


    if "medical device engineer" in title:
        score += 35

    if "clinical engineer" in title:
        score += 35

    if "medical equipment engineer" in title:
        score += 35

    if "medical imaging engineer" in title:
        score += 35


    # --------------------------------------------------------
    # PENALTY FOR INDIRECT ROLES
    # --------------------------------------------------------

    if "regulatory" in title:
        score -= 100

    if "sales" in title:
        score -= 100

    if "marketing" in title:
        score -= 100

    if "procurement" in title:
        score -= 100


    return score


# ============================================================
# APPLICANT COUNT
# ============================================================

def fetch_applicant_count(url):

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

                value = (
                    match.group(1)
                    .replace(",", "")
                )

                try:
                    return int(value)
                except:
                    pass


    except Exception:
        pass


    return None


# ============================================================
# TELEGRAM
# ============================================================

def send_telegram(message):

    if not TELEGRAM_TOKEN:
        print("ERROR: TELEGRAM_TOKEN is missing.")
        return False

    if not TELEGRAM_CHAT_ID:
        print("ERROR: TELEGRAM_CHAT_ID is missing.")
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
            json=payload,
            timeout=20
        )


        print(
            "Telegram status:",
            response.status_code
        )


        if response.status_code == 200:

            print("Telegram message sent successfully.")

            return True


        print(
            "Telegram error:",
            response.text
        )

        return False


    except Exception as e:

        print(
            "Telegram sending error:",
            e
        )

        return False


# ============================================================
# BUILD TELEGRAM MESSAGE
# ============================================================

def build_telegram_message(jobs):

    today = datetime.now().strftime(
        "%Y-%m-%d"
    )


    message = (
        "🇪🇬 🧬 "
        "<b>Top Biomedical Engineering Jobs in Egypt</b>\n"
        f"📅 {today}\n\n"
    )


    for index, job in enumerate(
        jobs,
        start=1
    ):

        title = html.escape(
            job["title"]
        )

        company = html.escape(
            job["company"] or "Unknown company"
        )

        location = html.escape(
            job["location"] or "Egypt"
        )

        score = job.get(
            "score",
            0
        )

        applicants = job.get(
            "applicants"
        )


        if applicants is not None:

            applicant_text = (
                f"👥 Applicants: {applicants}\n"
            )

        else:

            applicant_text = ""


        message += (
            f"<b>{index}. {title}</b>\n"
            f"🏢 {company}\n"
            f"📍 {location}\n"
            f"{applicant_text}"
            f"⭐ Match Score: {score}\n"
            f"🔗 <a href=\"{html.escape(job['url'])}\">"
            f"View Job</a>\n\n"
        )


    message += (
        "🤖 <i>Jobs are filtered and ranked "
        "specifically for Biomedical Engineering.</i>"
    )


    return message


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 70)
    print("BIOMEDICAL JOB SEARCH SCRIPT STARTED")
    print("=" * 70)


    # --------------------------------------------------------
    # LOAD SEEN JOBS
    # --------------------------------------------------------

    seen_jobs = load_seen_jobs()

    seen_jobs = cleanup_seen_jobs(
        seen_jobs
    )

    print(
        "Previously seen jobs:",
        len(seen_jobs)
    )


    # --------------------------------------------------------
    # SEARCH ALL TERMS
    # --------------------------------------------------------

    all_jobs = []


    for query in LINKEDIN_SEARCHES:

        jobs = search_linkedin(
            query,
            "Egypt"
        )

        print(
            f"Query '{query}' returned "
            f"{len(jobs)} raw jobs."
        )

        all_jobs.extend(jobs)


    # --------------------------------------------------------
    # DEDUPLICATE
    # --------------------------------------------------------

    all_jobs = deduplicate_jobs(
        all_jobs
    )


    print()
    print(
        "TOTAL UNIQUE RAW JOBS:",
        len(all_jobs)
    )


    # --------------------------------------------------------
    # FILTER
    # --------------------------------------------------------

    relevant_jobs = []


    for job in all_jobs:

        if is_relevant_biomedical_job(job):

            job["score"] = score_job(job)

            relevant_jobs.append(job)


    print(
        "TOTAL RELEVANT BIOMEDICAL JOBS:",
        len(relevant_jobs)
    )


    # --------------------------------------------------------
    # REMOVE VERY LOW SCORE RESULTS
    # --------------------------------------------------------

    relevant_jobs = [
        job
        for job in relevant_jobs
        if job["score"] >= 50
    ]


    # --------------------------------------------------------
    # SORT BY SCORE
    # --------------------------------------------------------

    relevant_jobs.sort(
        key=lambda x: x["score"],
        reverse=True
    )


    print(
        "AFTER SCORE FILTER:",
        len(relevant_jobs)
    )


    # --------------------------------------------------------
    # SPLIT NEW / OLD
    # --------------------------------------------------------

    new_jobs = []
    old_jobs = []


    for job in relevant_jobs:

        job_id = job.get("id")


        if job_id and str(job_id) in seen_jobs:

            old_jobs.append(job)

        else:

            new_jobs.append(job)


    print(
        "NEW RELEVANT JOBS:",
        len(new_jobs)
    )

    print(
        "OLD RELEVANT JOBS:",
        len(old_jobs)
    )


    # --------------------------------------------------------
    # SELECT TOP 10
    #
    # New jobs first.
    # Old jobs are used only to fill the list.
    # --------------------------------------------------------

    selected_jobs = []


    selected_jobs.extend(
        new_jobs[:TOP_N]
    )


    if len(selected_jobs) < TOP_N:

        remaining = (
            TOP_N - len(selected_jobs)
        )

        selected_jobs.extend(
            old_jobs[:remaining]
        )


    selected_jobs = deduplicate_jobs(
        selected_jobs
    )


    # --------------------------------------------------------
    # FINAL SORT
    # --------------------------------------------------------

    selected_jobs.sort(
        key=lambda x: x["score"],
        reverse=True
    )


    selected_jobs = selected_jobs[
        :TOP_N
    ]


    print()
    print(
        "=" * 70
    )

    print(
        "FINAL JOBS TO SEND:",
        len(selected_jobs)
    )

    print(
        "=" * 70
    )


    for i, job in enumerate(
        selected_jobs,
        start=1
    ):

        print(
            f"{i}. "
            f"{job['title']} | "
            f"{job['company']} | "
            f"Score: {job['score']}"
        )


    # --------------------------------------------------------
    # NOTHING FOUND
    # --------------------------------------------------------

    if not selected_jobs:

        message = (
            "🇪🇬 🧬 "
            "<b>No suitable Biomedical Engineering "
            "jobs found in Egypt.</b>\n\n"
            f"📅 {datetime.now().strftime('%Y-%m-%d')}\n\n"
            "The search checked multiple LinkedIn "
            "queries and filtered out unrelated roles."
        )


        send_telegram(
            message
        )

        save_seen_jobs(
            seen_jobs
        )

        return


    # --------------------------------------------------------
    # APPLICANT COUNTS
    # --------------------------------------------------------

    print()
    print(
        "Fetching applicant counts..."
    )


    for job in selected_jobs:

        job["applicants"] = (
            fetch_applicant_count(
                job["url"]
            )
        )


    # --------------------------------------------------------
    # BUILD MESSAGE
    # --------------------------------------------------------

    message = build_telegram_message(
        selected_jobs
    )


    # --------------------------------------------------------
    # SEND TELEGRAM
    # --------------------------------------------------------

    telegram_success = send_telegram(
        message
    )


    # --------------------------------------------------------
    # SAVE SEEN JOBS ONLY AFTER SUCCESS
    # --------------------------------------------------------

    if telegram_success:

        now = datetime.now().isoformat()

        for job in selected_jobs:

            job_id = job.get("id")

            if job_id:

                seen_jobs[
                    str(job_id)
                ] = now


        seen_jobs = cleanup_seen_jobs(
            seen_jobs
        )


        save_seen_jobs(
            seen_jobs
        )


        print()
        print(
            f"Saved {len(selected_jobs)} "
            "jobs to seen_jobs.json."
        )

    else:

        print()
        print(
            "Telegram failed. "
            "Jobs were NOT marked as seen."
        )


    print()
    print("=" * 70)
    print("JOB SEARCH SCRIPT FINISHED")
    print("=" * 70)


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()

