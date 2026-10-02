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

    "Biomedical Engineer",
    "Biomedical",
    "Biomedical Engineering",

    "Biomedical Equipment",
    "Biomedical Service",
    "Biomedical Maintenance",

    "Medical Device",
    "Medical Devices",
    "Medical Device Engineer",

    "Medical Equipment",
    "Medical Equipment Engineer",
    "Medical Equipment Service",

    "Clinical Engineer",
    "Clinical Engineering",

    "Medical Imaging",
    "Medical Imaging Engineer",
    "Imaging Engineer",

    "Field Service Engineer",
    "Field Service Medical",

    "Service Engineer Medical",
    "Technical Service Medical",

    "Medical Technology",
    "Healthcare Technology",

    "Medical Instrumentation",
    "Medical Instrumentation Engineer",

    "Hospital Equipment",
    "Medical Equipment Technician",

]


# ============================================================
# WORDS THAT ARE DEFINITELY NOT WANTED
# ============================================================

HARD_EXCLUDE = [

    "sales",
    "sales representative",
    "sales specialist",
    "sales manager",

    "marketing",

    "human resources",
    "hr specialist",
    "recruiter",
    "recruitment",

    "accountant",
    "accounting",
    "finance",

    "procurement",
    "purchasing",

    "customer service",

    "software engineer",
    "software developer",
    "web developer",
    "frontend",
    "backend",
    "full stack",

    "data analyst",
    "data engineer",

    "devops",
    "cloud engineer",
    "network engineer",
    "cybersecurity",
    "it specialist",

    "civil engineer",
    "structural engineer",

    "mechanical engineer",
    "electrical engineer",
    "electronics engineer",

    "chemical engineer",
    "industrial engineer",
    "process engineer",
    "automotive engineer",

    "construction",
    "architect",

    "production engineer",
    "manufacturing engineer",

    "regulatory affairs",
    "regulatory specialist",
    "regulatory associate",
    "regulatory officer",

]


# ============================================================
# STRONG BIOMEDICAL TERMS
# ============================================================

STRONG_TERMS = {

    "biomedical engineer": 150,
    "biomedical engineering": 145,
    "biomedical": 110,

    "biomedical equipment": 140,
    "biomedical service": 140,
    "biomedical maintenance": 130,

    "medical device engineer": 135,
    "medical devices": 120,
    "medical device": 120,

    "medical equipment engineer": 135,
    "medical equipment": 115,

    "clinical engineer": 135,
    "clinical engineering": 130,

    "medical imaging engineer": 135,
    "medical imaging": 115,
    "imaging engineer": 110,

    "medical instrumentation engineer": 130,
    "medical instrumentation": 110,

    "field service engineer": 70,
    "service engineer medical": 100,

    "medical technology": 85,
    "healthcare technology": 85,

    "hospital equipment": 90,

}


# ============================================================
# MEDICAL DEVICE / EQUIPMENT CONTEXT
# ============================================================

MEDICAL_CONTEXT = {

    "ultrasound": 20,
    "mri": 20,
    "x-ray": 20,
    "xray": 20,
    "ct scanner": 20,
    "computed tomography": 20,

    "radiology": 20,
    "imaging": 15,

    "ecg": 18,
    "eeg": 18,

    "patient monitor": 20,
    "patient monitoring": 20,

    "ventilator": 20,
    "dialysis": 20,
    "infusion pump": 20,
    "anesthesia": 20,
    "defibrillator": 20,

    "medical device": 25,
    "medical devices": 25,
    "medical equipment": 25,

    "clinical": 15,
    "hospital equipment": 25,

}


# ============================================================
# LOAD SEEN
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

        print("Error loading seen_jobs.json:", e)

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
            indent=2,
            ensure_ascii=False
        )


def cleanup_seen(seen):

    cutoff = datetime.now() - timedelta(
        days=30
    )

    result = {}

    for job_id, timestamp in seen.items():

        try:

            dt = datetime.fromisoformat(timestamp)

            if dt >= cutoff:
                result[job_id] = timestamp

        except Exception:
            pass

    return result


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
# PARSE JOB CARD
# ============================================================

def parse_job(card):

    try:

        title_element = (
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

        company_element = (
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

        location_element = (
            card.select_one(
                ".job-search-card__location"
            )
            or
            card.select_one(
                ".base-search-card__metadata"
            )
        )

        link_element = (
            card.select_one(
                "a.base-card__full-link"
            )
            or
            card.select_one(
                "a[href*='/jobs/view/']"
            )
        )


        title = clean(
            title_element.get_text(
                " ",
                strip=True
            )
            if title_element
            else ""
        )

        company = clean(
            company_element.get_text(
                " ",
                strip=True
            )
            if company_element
            else ""
        )

        location = clean(
            location_element.get_text(
                " ",
                strip=True
            )
            if location_element
            else ""
        )


        url = ""

        if link_element:

            url = (
                link_element
                .get("href", "")
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

        print("Parse error:", e)

        return None


# ============================================================
# SEARCH ONE QUERY
# ============================================================

def search_linkedin(query):

    jobs = []

    print()
    print("SEARCH:", query)


    for page in range(MAX_SEARCH_PAGES):

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

                print("  No job cards.")
                break


            count = 0


            for card in cards:

                job = parse_job(card)

                if job:

                    jobs.append(job)

                    count += 1


            print(
                f"  Parsed {count} jobs"
            )


            if len(cards) < PAGE_SIZE:
                break


        except Exception as e:

            print(
                "  Search error:",
                e
            )


    return jobs


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


    return list(unique.values())


# ============================================================
# RELEVANCE + SCORE
# ============================================================

def score_job(job):

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
    # HARD EXCLUDE
    # --------------------------------------------------------

    for word in HARD_EXCLUDE:

        if word in title:

            return -1000


    score = 0


    # --------------------------------------------------------
    # STRONG TERMS
    # --------------------------------------------------------

    for word, points in STRONG_TERMS.items():

        if word in title:

            score += points


    # --------------------------------------------------------
    # MEDICAL CONTEXT
    # --------------------------------------------------------

    for word, points in MEDICAL_CONTEXT.items():

        if word in full_text:

            score += points


    # --------------------------------------------------------
    # LOCATION
    # --------------------------------------------------------

    if "cairo" in location:
        score += 25

    if "giza" in location:
        score += 25

    if "alexandria" in location:
        score += 20

    if "egypt" in location:
        score += 20


    # --------------------------------------------------------
    # DIRECT BIOMEDICAL BONUSES
    # --------------------------------------------------------

    if "biomedical engineer" in title:
        score += 80

    if "biomedical" in title:
        score += 50

    if "medical device engineer" in title:
        score += 70

    if "clinical engineer" in title:
        score += 70

    if "medical equipment engineer" in title:
        score += 70

    if "medical imaging engineer" in title:
        score += 70

    if "biomedical service engineer" in title:
        score += 70


    return score


# ============================================================
# FETCH APPLICANTS
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
        print("TELEGRAM_TOKEN missing.")
        return False

    if not TELEGRAM_CHAT_ID:
        print("TELEGRAM_CHAT_ID missing.")
        return False


    telegram_url = (
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
            telegram_url,
            json=payload,
            timeout=20
        )


        print(
            "Telegram:",
            response.status_code
        )


        if response.status_code == 200:

            return True


        print(
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
# BUILD MESSAGE
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


    for i, job in enumerate(
        jobs,
        1
    ):

        title = html.escape(
            job["title"]
        )

        company = html.escape(
            job["company"]
        )

        location = html.escape(
            job["location"]
            or "Egypt"
        )

        score = job["score"]


        if job.get("applicants") is not None:

            applicants = (
                f"👥 Applicants: "
                f"{job['applicants']}\n"
            )

        else:

            applicants = ""


        message += (

            f"<b>{i}. {title}</b>\n"

            f"🏢 {company}\n"

            f"📍 {location}\n"

            f"{applicants}"

            f"⭐ Match Score: {score}\n"

            f"🔗 <a href=\""
            f"{html.escape(job['url'])}"
            f"\">View Job</a>\n\n"

        )


    message += (
        "🤖 <i>Jobs are filtered and ranked "
        "for Biomedical Engineering.</i>"
    )


    return message


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 70)
    print("BIOMEDICAL JOB SEARCH STARTED")
    print("=" * 70)


    # --------------------------------------------------------
    # LOAD SEEN
    # --------------------------------------------------------

    seen = cleanup_seen(
        load_seen()
    )


    print(
        "Seen jobs:",
        len(seen)
    )


    # --------------------------------------------------------
    # SEARCH EVERYTHING
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
        "UNIQUE JOBS FOUND:",
        len(all_jobs)
    )


    # --------------------------------------------------------
    # SCORE
    # --------------------------------------------------------

    scored_jobs = []


    for job in all_jobs:

        score = score_job(
            job
        )


        if score > 0:

            job["score"] = score

            scored_jobs.append(
                job
            )


    print(
        "BIOMEDICAL/MEDICAL JOBS:",
        len(scored_jobs)
    )


    # --------------------------------------------------------
    # SORT ALL JOBS
    # --------------------------------------------------------

    scored_jobs.sort(
        key=lambda x: x["score"],
        reverse=True
    )


    # --------------------------------------------------------
    # NEW JOBS FIRST
    # --------------------------------------------------------

    new_jobs = []

    old_jobs = []


    for job in scored_jobs:

        job_id = job.get("id")


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
        "NEW:",
        len(new_jobs)
    )

    print(
        "OLD:",
        len(old_jobs)
    )


    # --------------------------------------------------------
    # TAKE TOP 10
    #
    # NEW FIRST
    # THEN OLD TO COMPLETE 10
    # --------------------------------------------------------

    selected = []


    selected.extend(
        new_jobs[:TOP_N]
    )


    if len(selected) < TOP_N:

        needed = (
            TOP_N
            - len(selected)
        )


        selected.extend(
            old_jobs[:needed]
        )


    # --------------------------------------------------------
    # FINAL DEDUP
    # --------------------------------------------------------

    selected = deduplicate(
        selected
    )


    # --------------------------------------------------------
    # FINAL SORT
    # --------------------------------------------------------

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
            f"{job['score']}"
        )


    # --------------------------------------------------------
    # IF LESS THAN 10
    # --------------------------------------------------------

    if len(selected) < TOP_N:

        print()
        print(
            "WARNING:"
        )

        print(
            f"LinkedIn/search returned only "
            f"{len(selected)} suitable jobs."
        )

        print(
            "The bot will still send them."
        )


    # --------------------------------------------------------
    # NO JOBS
    # --------------------------------------------------------

    if not selected:

        message = (
            "🇪🇬 🧬 "
            "<b>No Biomedical / Medical Device "
            "jobs found in Egypt today.</b>\n\n"
            f"📅 {datetime.now().strftime('%Y-%m-%d')}"
        )


        send_telegram(
            message
        )

        return


    # --------------------------------------------------------
    # APPLICANTS
    # --------------------------------------------------------

    for job in selected:

        job["applicants"] = (
            fetch_applicants(
                job["url"]
            )
        )


    # --------------------------------------------------------
    # SEND
    # --------------------------------------------------------

    message = build_message(
        selected
    )


    success = send_telegram(
        message
    )


    # --------------------------------------------------------
    # SAVE SEEN ONLY IF SENT
    # --------------------------------------------------------

    if success:

        timestamp = datetime.now().isoformat()


        for job in selected:

            if job.get("id"):

                seen[
                    str(job["id"])
                ] = timestamp


        save_seen(
            cleanup_seen(
                seen
            )
        )


        print(
            "Seen jobs updated."
        )

    else:

        print(
            "Telegram failed. "
            "Seen jobs NOT updated."
        )


    print()
    print("=" * 70)
    print("DONE")
    print("=" * 70)


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()

