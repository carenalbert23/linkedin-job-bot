import os
import re
import json
import html
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

# ============================================================
# Configuration
# ============================================================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

SEEN_JOBS_FILE = "seen_jobs.json"
TOP_N = 10
SEEN_JOBS_TTL_DAYS = 30
LINKEDIN_TIME_FILTER = "r604800"  # Prefer fresh LinkedIn results from the last 7 days
PAGE_SIZE = 25
MAX_SEARCH_PAGES = 2
REQUEST_TIMEOUT = 20
PAGE_DELAY_SECONDS = 1.2
QUERY_DELAY_SECONDS = 2.0
LINKEDIN_RATE_LIMITED = False

LINKEDIN_URL = (
    "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
)

LINKEDIN_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/142.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}

# Search Egypt only. LinkedIn guest search can return loosely related jobs,
# so every result is checked by the classifier below before it is sent.
SEARCH_QUERIES = [
    "Biomedical Engineer",
    "Biomedical Equipment Engineer",
    "Biomedical Service Engineer",
    "Biomedical Maintenance Engineer",
    "Medical Device Engineer",
    "Medical Equipment Engineer",
    "Medical Equipment Service Engineer",
    "Clinical Engineer",
    "Field Service Engineer Medical Devices",
    "Medical Field Service Engineer",
    "Medical Imaging Engineer",
    "Medical Instrumentation Engineer",
    "Hospital Equipment Engineer",
    "Ultrasound Service Engineer",
]
# Strong role terms. The classifier checks title first, then the company/title
# context for roles whose titles are more generic (e.g. Field Service Engineer).
DIRECT_BIOMEDICAL_TERMS = [
    "biomedical engineer",
    "biomedical engineering",
    "biomedical equipment",
    "biomedical service",
    "biomedical maintenance",
    "clinical engineer",
    "medical device engineer",
    "medical devices engineer",
    "medical equipment engineer",
    "medical equipment service",
    "medical equipment maintenance",
    "medical imaging engineer",
    "medical instrumentation engineer",
    "healthcare technology engineer",
    "health technology engineer",
    "medical technology engineer",
    "hospital equipment engineer",
    "radiology equipment engineer",
    "ultrasound service engineer",
    "medical systems engineer",
    "medical service engineer",
    "medical maintenance engineer",
    "medical installation engineer",
    "medical equipment installation",
    "diagnostic equipment engineer",
    "medical device service",
    "medical device maintenance",
    "medical equipment technician",
    "biomedical technician",
]

MEDICAL_CONTEXT_TERMS = [
    "biomedical",
    "medical device",
    "medical devices",
    "medical equipment",
    "clinical engineering",
    "medical imaging",
    "medical instrumentation",
    "healthcare technology",
    "health technology",
    "medical technology",
    "hospital equipment",
    "radiology",
    "ultrasound",
    "mri",
    "x-ray",
    "xray",
    "ct scanner",
    "computed tomography",
    "patient monitor",
    "patient monitoring",
    "ventilator",
    "dialysis",
    "infusion pump",
    "anesthesia machine",
    "anaesthesia machine",
    "defibrillator",
    "ecg",
    "eeg",
    "endoscopy",
    "mammography",
    "surgical equipment",
    "diagnostic equipment",
    "diagnostic imaging",
    "laboratory analyzer",
    "laboratory analyser",
    "medical analyser",
    "medical analyzer",
    "healthcare",
    "medical",
    "clinical",
    "diagnostic",
    "medical-grade",
    "patient care",
    "operating theatre",
    "operating room",
    "laboratory analyzer",
    "laboratory analyser",
    "blood gas analyzer",
    "blood gas analyser",
    "chemistry analyzer",
    "hematology analyzer",
    "haematology analyzer",
    "mammography",
    "bone densitometry",
    "dexa",
    "pet scanner",
    "gamma camera",
    "surgical",
]

# Known healthcare / medical-device companies can provide context when a job
# title is generic. This is deliberately a limited list to reduce false matches.
MEDICAL_COMPANY_TERMS = [
    "ge healthcare",
    "siemens healthineers",
    "philips",
    "mindray",
    "drager",
    "dräger",
    "fresenius",
    "baxter",
    "medtronic",
    "abbott",
    "roche diagnostics",
    "beckman coulter",
    "canon medical",
    "canon healthcare",
    "paxerahealth",
    "nihon kohden",
    "b. braun",
    "bbraun",
    "stryker",
    "olympus medical",
    "elekta",
    "varian medical",
    "varex imaging",
    "carestream",
    "getinge",
    "bd",
    "becton dickinson",
    "terumo",
    "schiller",
    "zoll medical",
    "masimo",
    "contec medical",
    "ecomed",
    "medical union",
    "medix",
    "medica",
    "philips healthcare",
    "siemens",
    "ge medical",
    "mindray medical",
    "fujifilm healthcare",
    "fujifilm medical",
    "samsung medison",
    "hologic",
    "agfa healthcare",
    "medtronic egypt",
    "boston scientific",
    "edwards lifesciences",
    "alcon",
    "bio-rad",
    "thermo fisher",
    "danaher",
    "sysmex",
    "eppendorf",
    "b. braun medical",
    "medical equipment",
]

# Exclude roles that are not the intended biomedical/device engineering jobs.
# Checks are performed on the title, not the company name.
HARD_EXCLUDE_TERMS = [
    "sales",
    "business development",
    "marketing",
    "account manager",
    "account executive",
    "regulatory affairs",
    "regulatory",
    "quality assurance",
    "quality control",
    "quality engineer",
    "hr ",
    "human resources",
    "recruiter",
    "finance",
    "accountant",
    "procurement",
    "purchasing",
    "customer service",
    "customer support",
    "call center",
    "pharmacist",
    "pharmacy",
    "nurse",
    "nursing",
    "lab technician",
    "laboratory technician",
    "medical representative",
    "medical rep",
    "software engineer",
    "software developer",
    "web developer",
    "data engineer",
    "data analyst",
    "network engineer",
    "devops",
    "cyber security",
    "cybersecurity",
    "it support",
    "information technology",
    "civil engineer",
    "mechanical engineer",
    "electrical engineer",
    "chemical engineer",
    "automotive engineer",
    "construction",
    "architect",
    "production engineer",
    "industrial engineer",
    "field sales",
    "application specialist",
    "clinical application",
    "product specialist",
    "product manager",
    "project manager",
    "general manager",
    "technician",
    "technologist",
    "research scientist",
    "scientist",
    "internship",
]

ROLE_SCORES = [
    ("biomedical engineer", 100),
    ("biomedical equipment", 98),
    ("biomedical service", 97),
    ("biomedical maintenance", 96),
    ("clinical engineer", 94),
    ("medical device engineer", 93),
    ("medical devices engineer", 93),
    ("medical equipment engineer", 92),
    ("medical equipment service", 91),
    ("medical equipment maintenance", 90),
    ("medical imaging engineer", 89),
    ("medical instrumentation engineer", 88),
    ("healthcare technology engineer", 87),
    ("health technology engineer", 86),
    ("medical technology engineer", 85),
    ("hospital equipment engineer", 84),
    ("radiology equipment engineer", 83),
    ("ultrasound service engineer", 82),
    ("field service engineer", 70),
    ("service engineer", 65),
    ("maintenance engineer", 60),
    ("equipment engineer", 55),
    ("engineer", 30),
]


# ============================================================
# General helpers
# ============================================================

def utc_now():
    return datetime.now(timezone.utc)


def parse_datetime(value):
    """Parse ISO timestamps stored by older and newer versions of the bot."""
    if not value:
        return None
    try:
        text = str(value).strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def clean_job_url(url):
    if not url:
        return ""
    url = html.unescape(url.strip())
    if url.startswith("/"):
        url = "https://www.linkedin.com" + url
    try:
        parsed = urlparse(url)
        # Remove tracking/query parameters, which should not make a new job.
        clean_path = parsed.path.rstrip("/")
        return urlunparse(
            (parsed.scheme or "https", parsed.netloc, clean_path, "", "", "")
        )
    except Exception:
        return url.split("?")[0].rstrip("/")


def extract_job_id(value):
    """Extract a LinkedIn numeric job ID from an ID, URL, or URN."""
    if value is None:
        return None
    text = str(value).strip()
    if text.isdigit():
        return text
    match = re.search(r"(?:jobs/view/|jobPosting:|urn:li:jobPosting:)(\d+)", text)
    if match:
        return match.group(1)
    return None


def job_key(job):
    return extract_job_id(job.get("id")) or clean_job_url(job.get("url")) or (
        f"{job.get('title', '').strip().lower()}|"
        f"{job.get('company', '').strip().lower()}|"
        f"{job.get('location', '').strip().lower()}"
    )


# ============================================================
# Seen-jobs storage (supports both legacy ID keys and URL keys)
# ============================================================

def load_seen():
    if not os.path.exists(SEEN_JOBS_FILE):
        return {}
    try:
        with open(SEEN_JOBS_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        print("WARNING: Could not read seen_jobs.json; starting with an empty in-memory set.")
        return {}


def entry_seen_at(value):
    if isinstance(value, dict):
        return value.get("seen_at") or value.get("timestamp") or value.get("date")
    if isinstance(value, str):
        return value
    return None


def normalize_seen(seen):
    """
    Convert legacy URL keys and numeric ID keys to one canonical ID key.
    Preserve stored values and keep entries that cannot be identified.
    """
    normalized = {}
    for key, value in (seen or {}).items():
        url_in_value = value.get("url", "") if isinstance(value, dict) else ""
        canonical_id = extract_job_id(key) or extract_job_id(url_in_value)

        if canonical_id:
            target_key = canonical_id
        else:
            target_key = clean_job_url(key) if str(key).startswith("http") else str(key)

        if target_key not in normalized:
            normalized[target_key] = value
            continue

        # If duplicate URL/ID records exist, retain the newest record.
        old_dt = parse_datetime(entry_seen_at(normalized[target_key]))
        new_dt = parse_datetime(entry_seen_at(value))
        if new_dt and (not old_dt or new_dt > old_dt):
            normalized[target_key] = value

    return normalized


def cleanup_seen(seen):
    cutoff = utc_now() - timedelta(days=SEEN_JOBS_TTL_DAYS)
    cleaned = {}
    for key, value in seen.items():
        dt = parse_datetime(entry_seen_at(value))
        # Keep malformed/unknown timestamps rather than risk re-sending old jobs.
        if dt is None or dt >= cutoff:
            cleaned[key] = value
    return cleaned


def save_seen(seen):
    temp_file = SEEN_JOBS_FILE + ".tmp"
    with open(temp_file, "w", encoding="utf-8") as file:
        json.dump(seen, file, ensure_ascii=False, indent=2)
    os.replace(temp_file, SEEN_JOBS_FILE)


def is_job_seen(job, seen):
    key = job_key(job)
    if key in seen:
        return True

    job_id = extract_job_id(job.get("id")) or extract_job_id(job.get("url"))
    if job_id and job_id in seen:
        return True

    url = clean_job_url(job.get("url"))
    if url and url in seen:
        return True

    # Legacy records may be keyed by a URL but not yet normalized for any reason.
    for saved_key, value in seen.items():
        if extract_job_id(saved_key) == job_id and job_id:
            return True
        if isinstance(value, dict):
            saved_url = clean_job_url(value.get("url", ""))
            if url and saved_url == url:
                return True
    return False


# ============================================================
# LinkedIn search and parsing
# ============================================================

def parse_job(card):
    title_node = card.select_one("h3.base-search-card__title")
    company_node = card.select_one("h4.base-search-card__subtitle")
    location_node = card.select_one(".job-search-card__location")
    link_node = card.select_one("a.base-card__full-link") or card.select_one("a[href*='/jobs/view/']")

    title = title_node.get_text(" ", strip=True) if title_node else ""
    company = company_node.get_text(" ", strip=True) if company_node else ""
    location = location_node.get_text(" ", strip=True) if location_node else ""
    url = clean_job_url(link_node.get("href", "")) if link_node else ""
    snippet_node = (
        card.select_one(".job-search-card__snippet")
        or card.select_one(".base-search-card__metadata")
        or card.select_one("p")
    )
    snippet = snippet_node.get_text(" ", strip=True) if snippet_node else ""
    card_text = card.get_text(" ", strip=True)

    urn = card.get("data-entity-urn", "")
    job_id = extract_job_id(urn) or extract_job_id(url)

    if not title or not url:
        return None

    return {
        "id": job_id or url,
        "title": title,
        "company": company,
        "location": location,
        "url": url,
        "snippet": snippet,
        "card_text": card_text,
    }


def search_linkedin(query):
    global LINKEDIN_RATE_LIMITED
    results = []
    session = requests.Session()
    session.headers.update(LINKEDIN_HEADERS)

    for page in range(MAX_SEARCH_PAGES):
        if LINKEDIN_RATE_LIMITED:
            break

        params = {
            "keywords": query,
            "location": "Egypt",
            "f_TPR": LINKEDIN_TIME_FILTER,
            "sortBy": "DD",  # Sort by date, newest first
            "start": page * PAGE_SIZE,
        }

        try:
            response = session.get(
                LINKEDIN_URL,
                params=params,
                timeout=REQUEST_TIMEOUT,
            )

            if response.status_code == 429:
                print(
                    f"LinkedIn rate-limited the request (HTTP 429) for '{query}'. "
                    "Waiting 25 seconds, then retrying once..."
                )
                time.sleep(25)
                response = session.get(
                    LINKEDIN_URL,
                    params=params,
                    timeout=REQUEST_TIMEOUT,
                )

            if response.status_code == 429:
                print(
                    "LinkedIn is still rate-limiting requests. "
                    "Stopping further LinkedIn searches for this run."
                )
                LINKEDIN_RATE_LIMITED = True
                break

            if response.status_code != 200:
                print(
                    f"LinkedIn returned HTTP {response.status_code} "
                    f"for query: {query}"
                )
                break

            soup = BeautifulSoup(response.text, "html.parser")
            cards = soup.select("li")
            page_jobs = []

            for card in cards:
                if not card.select_one("a[href*='/jobs/view/']"):
                    continue
                job = parse_job(card)
                if job:
                    job["search_queries"] = [query]
                    page_jobs.append(job)

            if not page_jobs:
                break

            results.extend(page_jobs)
            print(f"  {query}: page {page + 1}, found {len(page_jobs)} cards")

            if len(page_jobs) < 5:
                break

            time.sleep(PAGE_DELAY_SECONDS)

        except requests.RequestException as exc:
            print(f"Search error for '{query}': {exc}")
            break

    return results


def deduplicate_jobs(jobs):
    unique = {}
    for job in jobs:
        key = job_key(job)
        if not key:
            continue
        if key not in unique:
            unique[key] = job
            continue

        # Keep the version with more useful metadata.
        existing = unique[key]
        for field in ("title", "company", "location", "url", "snippet", "card_text"):
            if not existing.get(field) and job.get(field):
                existing[field] = job[field]
        existing_queries = existing.setdefault("search_queries", [])
        for query in job.get("search_queries", []):
            if query not in existing_queries:
                existing_queries.append(query)
    return list(unique.values())


# ============================================================
# Biomedical relevance filtering and scoring
# ============================================================

def contains_any(text, terms):
    text = (text or "").lower()
    return any(term in text for term in terms)


def is_hard_excluded(title):
    title = (title or "").lower().strip()
    padded_title = f" {title} "
    for term in HARD_EXCLUDE_TERMS:
        if term == "hr ":
            if " hr " in padded_title:
                return True
        elif term in title:
            return True
    return False


def classify_job(job):
    """
    Classify biomedical engineering jobs using title, employer,
    and available job-card text. Return a score or None.
    """
    title = (job.get("title") or "").strip().lower()
    company = (job.get("company") or "").strip().lower()
    snippet = (job.get("snippet") or "").strip().lower()
    card_text = (job.get("card_text") or "").strip().lower()

    context = " ".join([title, company, snippet, card_text])

    if not title:
        return None

    # Exclude clearly unrelated job titles.
    if is_hard_excluded(title):
        return None

    direct_terms = [
        "biomedical engineer",
        "biomedical equipment",
        "biomedical service",
        "biomedical maintenance",
        "clinical engineer",
        "medical device engineer",
        "medical devices engineer",
        "medical equipment engineer",
        "medical equipment service",
        "medical equipment maintenance",
        "medical imaging engineer",
        "medical instrumentation engineer",
        "hospital equipment engineer",
        "radiology equipment engineer",
        "ultrasound service engineer",
        "medical service engineer",
        "medical maintenance engineer",
        "medical installation engineer",
        "diagnostic equipment engineer",
        "medical device service",
        "medical device maintenance",
    ]

    medical_terms = [
        "biomedical",
        "medical device",
        "medical devices",
        "medical equipment",
        "clinical engineering",
        "medical imaging",
        "medical instrumentation",
        "healthcare technology",
        "health technology",
        "medical technology",
        "hospital equipment",
        "radiology equipment",
        "ultrasound",
        "mri",
        "x-ray",
        "xray",
        "ct scanner",
        "patient monitor",
        "patient monitoring",
        "ventilator",
        "dialysis",
        "infusion pump",
        "anesthesia machine",
        "anaesthesia machine",
        "defibrillator",
        "ecg",
        "eeg",
        "endoscopy",
        "mammography",
        "surgical equipment",
        "diagnostic equipment",
        "diagnostic imaging",
        "laboratory analyzer",
        "laboratory analyser",
        "blood gas analyzer",
        "blood gas analyser",
        "chemistry analyzer",
        "hematology analyzer",
        "haematology analyzer",
        "bone densitometry",
        "dexa",
        "pet scanner",
        "gamma camera",
    ]

    medical_companies = [
        "ge healthcare",
        "siemens healthineers",
        "philips healthcare",
        "philips",
        "mindray",
        "drager",
        "dräger",
        "fresenius",
        "baxter",
        "medtronic",
        "abbott",
        "roche diagnostics",
        "beckman coulter",
        "canon medical",
        "nihon kohden",
        "stryker",
        "olympus medical",
        "elekta",
        "varian medical",
        "carestream",
        "getinge",
        "becton dickinson",
        "terumo",
        "schiller",
        "zoll medical",
        "masimo",
        "fujifilm healthcare",
        "samsung medison",
        "hologic",
        "agfa healthcare",
        "boston scientific",
        "edwards lifesciences",
        "bio-rad",
        "thermo fisher",
        "sysmex",
    ]

    engineering_terms = [
        "engineer",
        "engineering",
        "technician",
        "technologist",
    ]

    service_terms = [
        "service",
        "maintenance",
        "field service",
        "installation",
        "repair",
        "calibration",
        "equipment",
        "imaging",
        "instrumentation",
        "technical support",
        "application",
    ]

    has_engineering_role = any(
        term in title for term in engineering_terms
    )

    if not has_engineering_role:
        return None

    direct_match = any(term in title for term in direct_terms)
    medical_context = any(term in context for term in medical_terms)
    known_medical_company = any(
        term in company for term in medical_companies
    )
    service_role = any(term in title for term in service_terms)

    # Do not accept generic engineering jobs based only on the search query.
    if not direct_match:
        if not medical_context:
            if not (known_medical_company and service_role):
                return None

    # Base score: specific biomedical titles rank highest.
    score = 85

    for term, points in ROLE_SCORES:
        if term in title:
            score = max(score, points)

    if direct_match:
        score = max(score, 88)
    elif medical_context:
        score = max(score, 72)
    elif known_medical_company and service_role:
        score = max(score, 70)

    # Small location bonuses.
    location = (job.get("location") or "").lower()

    if "egypt" in location:
        score += 5

    if "cairo" in location or "القاهرة" in location:
        score += 3

    if "giza" in location or "الجيزة" in location:
        score += 2

    job["match_score"] = min(score, 100)

    return job["match_score"]


    # Exact biomedical/medical-device titles are strongest matches.
    if direct_match:
        score = max(score, 88)
    # A relevant device/clinical term anywhere in the card gives context for
    # a general engineering title, including field service and maintenance.
    elif medical_context:
        score = max(score, 72)
        if any(term in title for term in ("field service", "service", "maintenance", "installation")):
            score += 4
    # A known medical-device company can make a generic service/equipment
    # engineering title relevant even when the title omits "medical".
    elif company_context and service_or_equipment_role:
        score = max(score, 70)
    else:
        # Never accept a generic engineer solely because LinkedIn returned it
        # for a biomedical keyword search.
        return None

    location = (job.get("location") or "").lower()
    if "egypt" in location:
        score += 5
    if "cairo" in location or "القاهرة" in location:
        score += 3
    if "giza" in location or "الجيزة" in location:
        score += 2

    job["match_score"] = min(score, 100)
    return job["match_score"]

# ============================================================
# Applicant count and Telegram
# ============================================================

def fetch_applicants(url):
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

        text = BeautifulSoup(response.text, "html.parser").get_text(" ", strip=True)
        patterns = [
            r"([\d,]+)\s+applicants",
            r"([\d,]+)\s+applicant",
            r"Over\s+([\d,]+)\s+applicants",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                try:
                    return int(match.group(1).replace(",", ""))
                except ValueError:
                    pass
    except requests.RequestException as exc:
        print(f"Applicant count lookup failed: {exc}")
    return None


def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("ERROR: TELEGRAM_TOKEN or TELEGRAM_CHAT_ID is missing.")
        return False

    api_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        response = requests.post(
            api_url,
            data={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=20,
        )

        try:
            payload = response.json()
        except ValueError:
            payload = {}

        if response.status_code == 200 and payload.get("ok") is True:
            print("Telegram message sent successfully.")
            return True

        print(
            "Telegram send failed:",
            response.status_code,
            payload.get("description", response.text[:300]),
        )
        return False

    except requests.RequestException as exc:
        print(f"Telegram request failed: {exc}")
        return False


def build_message(jobs):
    count = len(jobs)
    lines = [
        f"🇪🇬 🧬 <b>Top {count} New Biomedical Engineering Jobs in Egypt</b>",
        f"📅 <i>{datetime.now().strftime('%d %b %Y')}</i>",
        "",
    ]

    for index, job in enumerate(jobs, start=1):
        title = html.escape(job.get("title") or "Biomedical Engineering Role")
        company = html.escape(job.get("company") or "Company not listed")
        location = html.escape(job.get("location") or "Egypt")
        score = job.get("match_score", 0)
        applicants = job.get("applicants")

        lines.extend([
            f"<b>{index}. {title}</b>",
            f"🏢 Company: {company}",
            f"📍 Location: {location}",
            f"🎯 Match score: {score}/100",
        ])

        if applicants is not None:
            lines.append(f"👥 Applicants: {applicants}")

        url = html.escape(job.get("url") or "", quote=True)
        if url:
            lines.append(f'🔗 <a href="{url}">View Job</a>')
        lines.append("")

    return "\n".join(lines).strip()


# ============================================================
# Main
# ============================================================

def main():
    print("=" * 60)
    print("BIOMEDICAL JOB SEARCH SCRIPT STARTED")
    print(f"Search window: last 7 days, newest first | Country: Egypt | Max alerts: {TOP_N}")
    print("=" * 60)

    seen = normalize_seen(load_seen())
    seen = cleanup_seen(seen)
    print(f"Loaded {len(seen)} saved seen-job records.")

    all_jobs = []
    for index, query in enumerate(SEARCH_QUERIES):
        if LINKEDIN_RATE_LIMITED:
            print("Search loop stopped early because LinkedIn rate-limited requests.")
            break
        print(f"Searching: {query}")
        all_jobs.extend(search_linkedin(query))
        if index < len(SEARCH_QUERIES) - 1 and not LINKEDIN_RATE_LIMITED:
            time.sleep(QUERY_DELAY_SECONDS)

    print(f"Raw results collected: {len(all_jobs)}")
    if LINKEDIN_RATE_LIMITED:
        print("NOTE: This run was limited by LinkedIn HTTP 429; some queries were skipped.")

    unique_jobs = deduplicate_jobs(all_jobs)
    print(f"Unique jobs after deduplication: {len(unique_jobs)}")

    qualified_jobs = []
    excluded_count = 0
    for job in unique_jobs:
        score = classify_job(job)
        if score is None:
            excluded_count += 1
            continue
        qualified_jobs.append(job)

    qualified_jobs.sort(
        key=lambda job: (
            job.get("match_score", 0),
            bool(extract_job_id(job.get("id"))),
            job.get("title", "").lower(),
        ),
        reverse=True,
    )

    print(f"Qualified biomedical/device engineering jobs: {len(qualified_jobs)}")
    print(f"Excluded unrelated jobs: {excluded_count}")

    new_jobs = [job for job in qualified_jobs if not is_job_seen(job, seen)]
    print(f"New jobs not sent before: {len(new_jobs)}")

    # IMPORTANT: Never fill the list with old jobs. Send only genuinely new jobs.
    selected_jobs = new_jobs[:TOP_N]

    if not selected_jobs:
        print("No new qualified jobs to send. No Telegram message will be sent.")
        # Save normalized storage so legacy URL keys become canonical IDs.
        save_seen(seen)
        return

    # Fetch applicant counts only for the jobs that will actually be sent.
    for job in selected_jobs:
        job["applicants"] = fetch_applicants(job.get("url"))
        time.sleep(0.2)

    message = build_message(selected_jobs)
    if not send_telegram(message):
        print("Telegram send failed; selected jobs were NOT added to seen_jobs.json.")
        return

    # Only mark jobs as seen after Telegram confirms successful delivery.
    now = utc_now().isoformat()
    for job in selected_jobs:
        key = job_key(job)
        if not key:
            continue
        seen[key] = {
            "seen_at": now,
            "title": job.get("title", ""),
            "company": job.get("company", ""),
            "location": job.get("location", ""),
            "url": clean_job_url(job.get("url", "")),
        }

    save_seen(seen)
    print(f"Saved {len(selected_jobs)} newly sent jobs to {SEEN_JOBS_FILE}.")
    print("JOB SEARCH COMPLETED SUCCESSFULLY.")


if __name__ == "__main__":
    main()
