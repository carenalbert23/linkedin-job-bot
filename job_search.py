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

TELEGRAM_TOKEN  = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

SEEN_JOBS_FILE    = os.path.join(os.path.dirname(__file__), "seen_jobs.json")
SEEN_JOBS_TTL_DAYS = 7
TOP_N = 10

# All searches are remote-only (f_WT=2, enforced in search_linkedin), scoped
# to Steven's target regions: North Europe (top priority), Gulf, Egypt, and
# the rest of Europe.
LINKEDIN_SEARCHES = [
    # North Europe — top priority
    {"keywords": "AI automation",             "location": "Switzerland"},
    {"keywords": "AI automation specialist",  "location": "Switzerland"},
    {"keywords": "AI automation",             "location": "Denmark"},
    {"keywords": "AI automation",             "location": "Finland"},
    {"keywords": "AI automation",             "location": "Sweden"},
    {"keywords": "AI automation",             "location": "Norway"},
    {"keywords": "n8n automation",            "location": "Switzerland"},
    {"keywords": "AI business analyst",       "location": "Sweden"},
    # Gulf
    {"keywords": "AI automation specialist",  "location": "United Arab Emirates"},
    {"keywords": "AI agentic developer",      "location": "United Arab Emirates"},
    {"keywords": "RPA developer no-code",     "location": "United Arab Emirates"},
    {"keywords": "AI automation",             "location": "Saudi Arabia"},
    {"keywords": "business analyst AI",       "location": "Saudi Arabia"},
    {"keywords": "AI business analyst",       "location": "United Arab Emirates"},
    {"keywords": "AI marketing automation",   "location": "United Arab Emirates"},
    {"keywords": "AI operations",             "location": "United Arab Emirates"},
    {"keywords": "n8n automation",            "location": "United Arab Emirates"},
    {"keywords": "Claude AI automation",      "location": "United Arab Emirates"},
    {"keywords": "AI automation",             "location": "Qatar"},
    {"keywords": "AI automation",             "location": "Kuwait"},
    {"keywords": "AI automation",             "location": "Bahrain"},
    {"keywords": "AI automation",             "location": "Oman"},
    # Egypt
    {"keywords": "AI automation developer",   "location": "Egypt"},
    {"keywords": "AI business analyst",       "location": "Egypt"},
    {"keywords": "AI automation",             "location": "Egypt"},
    # Rest of Europe
    {"keywords": "AI automation",             "location": "United Kingdom"},
    {"keywords": "AI automation",             "location": "Ireland"},
    {"keywords": "AI automation",             "location": "Germany"},
    {"keywords": "AI automation",             "location": "France"},
    {"keywords": "AI automation",             "location": "Netherlands"},
    {"keywords": "AI automation",             "location": "Spain"},
    {"keywords": "AI automation",             "location": "Portugal"},
    {"keywords": "AI automation",             "location": "Italy"},
    {"keywords": "AI automation",             "location": "Poland"},
    {"keywords": "AI automation",             "location": "Belgium"},
    # Global remote fallback — no location filter, remote-work-type only
    {"keywords": "AI automation",             "location": "Worldwide", "remote_only": True},
    {"keywords": "AI automation specialist",  "location": "Worldwide", "remote_only": True},
    {"keywords": "n8n automation",            "location": "Worldwide", "remote_only": True},
    {"keywords": "AI business analyst",       "location": "Worldwide", "remote_only": True},
]

# Target company searches — any open role at these companies is fetched,
# then filtered for skill relevance
COMPANY_SEARCHES = [
    {"keywords": "Bayzat",    "location": "United Arab Emirates"},
    {"keywords": "Careem",    "location": "United Arab Emirates"},
    {"keywords": "G42",       "location": "United Arab Emirates"},
    {"keywords": "Talabat",   "location": "United Arab Emirates"},
    {"keywords": "Halan",     "location": "Egypt"},
    {"keywords": "Paymob",    "location": "Egypt"},
    {"keywords": "Instabug",  "location": "Egypt"},
    {"keywords": "Tamara",    "location": "Saudi Arabia"},
    {"keywords": "maids.cc",  "location": "United Arab Emirates"},
    {"keywords": "Qureos",    "location": "United Arab Emirates"},
]

# A company-search job must contain at least one of these words in its title
# to be considered relevant for Steven's profile
COMPANY_RELEVANCE_TITLE_WORDS = {
    "automation", "ai", "agentic", "rpa", "analyst", "developer",
    "engineer", "operations", "product", "data", "digital", "technical",
    "software", "platform", "workflow", "process", "integration",
    "solution", "consultant", "api", "system", "no-code", "low-code",
    "marketing", "social", "n8n", "claude", "codex",
}

LINKEDIN_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}

# ── Scoring ───────────────────────────────────────────────────────────────────

ROLE_SCORES = {
    # "ai automation" is Steven's #1 priority — checked first, scored above
    # everything else, since score_job() takes the first dict match on the
    # job title. Every other AI-automation-adjacent family stays high but
    # strictly below it.
    "ai automation":         40,
    "ai automation & business analyst": 38,
    "ai business analyst":   30,
    "ai marketing automation": 28,
    "marketing automation":  24,
    "ai ba":                 26,
    "ai operations":         24,
    "automation specialist": 25,
    "workflow automation":   22,
    "ai agentic":            25,
    "agentic developer":     25,
    "agentic engineer":      25,
    "rpa developer":         20,
    "rpa engineer":          20,
    "robotic process":       18,
    "no-code":               18,
    "low-code":              18,
    "automation consultant": 20,
    "operations analyst":    18,
    "business analyst":      18,
    "ai product analyst":    18,
    "automation engineer":   20,
    "automation developer":  20,
    "process automation":    18,
}

SKILL_SCORES = {
    "ai automation": 20, "n8n":     22, "make.com":  18, "integromat": 15,
    "zapier":       12, "claude":    16, "anthropic":  14,
    "codex":        14, "airtable":  10, "supabase":   10,
    "whatsapp":      8, "chatbot":    8, "llm":         8,
    "gpt":           6, "openai":     6, "python":      6,
    "automation":   10, "workflow":   4, "ai agent":   10,
    "ai ops":       12,
}

LOCATION_SCORES = {
    # North Europe — top priority, scored above every other region
    "switzerland": 26, "zurich": 26, "geneva": 26,
    "denmark": 25, "copenhagen": 25,
    "finland": 25, "helsinki": 25,
    "sweden": 25, "stockholm": 25,
    "norway": 25, "oslo": 25,
    "ae": 20, "uae": 20, "dubai": 20, "abu dhabi": 20, "sharjah": 20, "united arab emirates": 20,
    "sa": 18, "saudi": 18, "riyadh": 18, "jeddah": 18, "saudi arabia": 18,
    "qa": 16, "qatar": 16, "doha": 16,
    "kw": 15, "kuwait": 15,
    "bh": 15, "bahrain": 15,
    "om": 15, "oman": 15, "muscat": 15,
    "eg": 16, "egypt": 16, "cairo": 16,
    "worldwide": 15, "global": 15,
    "united kingdom": 16, "uk": 16, "london": 16,
    "ireland": 16, "dublin": 16,
    "germany": 16, "berlin": 16, "munich": 16,
    "france": 16, "paris": 16,
    "netherlands": 16, "amsterdam": 16,
    "spain": 16, "madrid": 16, "barcelona": 16,
    "portugal": 16, "lisbon": 16,
    "italy": 16, "milan": 16, "rome": 16,
    "poland": 16, "warsaw": 16,
    "belgium": 16, "brussels": 16,
    "remote": 14,
}

TARGET_COMPANIES = [
    "maids", "justmop", "helperplace", "qureos", "bayzat", "huspy", "coraly",
    "halan", "paymob", "instabug", "breadfast", "rabbit",
    "g42", "presight", "careem", "noon", "talabat", "dubizzle",
    "stc", "neom", "zain", "tamara",
    "automattic", "zapier", "make.com", "n8n",
]

LOCATION_CODE_MAP = {
    "united arab emirates": "ae", "uae": "ae", "dubai": "ae", "abu dhabi": "ae",
    "saudi arabia": "sa", "riyadh": "sa", "jeddah": "sa",
    "egypt": "eg", "cairo": "eg",
    "qatar": "qa", "doha": "qa",
    "kuwait": "kw", "bahrain": "bh",
    "oman": "om", "muscat": "om",
    "worldwide": "global",
    "united kingdom": "gb", "ireland": "ie",
    "germany": "de", "france": "fr", "netherlands": "nl",
    "spain": "es", "portugal": "pt", "italy": "it", "poland": "pl",
    "belgium": "be", "switzerland": "ch",
    "denmark": "dk", "finland": "fi", "sweden": "se", "norway": "no",
}


def infer_country_code(location: str) -> str:
    loc = location.lower()
    for k, v in LOCATION_CODE_MAP.items():
        if k in loc:
            return v
    return "global"


def score_job(job: dict) -> int:
    title   = (job.get("job_title") or "").lower()
    desc    = (job.get("job_description") or "")[:500].lower()
    city    = (job.get("job_city") or "").lower()
    country = (job.get("job_country") or "").lower()
    company = (job.get("employer_name") or "").lower()
    is_remote = job.get("job_is_remote", False)

    score = 0
    for kw, pts in ROLE_SCORES.items():
        if kw in title:
            score += pts
            break
    skill_pts = sum(pts for kw, pts in SKILL_SCORES.items() if kw in title + " " + desc)
    score += min(skill_pts, 30)
    loc_hay = f"{city} {country}" + (" remote" if is_remote else "")
    for loc, pts in LOCATION_SCORES.items():
        if loc in loc_hay:
            score += pts
            break
    if any(name in company for name in TARGET_COMPANIES):
        score += 10
    if is_remote:
        score += 8
    elif any(w in title for w in ("hybrid", "remote")):
        score += 5
    return score


def score_label(score: int) -> str:
    if score >= 60: return "Excellent match"
    if score >= 45: return "Strong match"
    if score >= 30: return "Good match"
    return "Possible match"


# ── Competition (applicant count) ─────────────────────────────────────────────
# Steven wants jobs with fewer competing applicants prioritized, since those
# are the easiest to actually get hired for. We only fetch the applicant
# count for each pool's top-scoring candidates (APPLICANT_FETCH_LIMIT) to
# keep the number of extra LinkedIn requests bounded.

APPLICANT_FETCH_LIMIT = 15


def fetch_applicant_count(url: str) -> int | None:
    if not url:
        return None
    try:
        resp = requests.get(url, headers=LINKEDIN_HEADERS, timeout=10)
        if resp.status_code != 200:
            return None
        m = re.search(r'([\d,]+)\+?\s*(?:applicants|people clicked apply)', resp.text, re.I)
        if m:
            return int(m.group(1).replace(",", ""))
    except requests.RequestException:
        pass
    return None


def applicant_bonus(count: int | None) -> int:
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
    return -8  # heavily-applied jobs are deprioritized, not just unboosted


def enrich_with_competition(jobs: list) -> list:
    """Fetch applicant counts for the top-scoring jobs in the pool, fold a
    low-competition bonus into their final score, then re-sort the whole
    pool by that final score."""
    ranked = sorted(jobs, key=score_job, reverse=True)
    top, rest = ranked[:APPLICANT_FETCH_LIMIT], ranked[APPLICANT_FETCH_LIMIT:]
    for job in top:
        count = fetch_applicant_count(job.get("job_apply_link"))
        job["_applicants"] = count
        job["_score"] = score_job(job) + applicant_bonus(count)
        time.sleep(0.3)
    for job in rest:
        job["_applicants"] = None
        job["_score"] = score_job(job)
    return sorted(top + rest, key=lambda j: j["_score"], reverse=True)


# ── LinkedIn scraper ──────────────────────────────────────────────────────────

def parse_card(card, search_location: str) -> dict | None:
    link_tag = card.find("a", class_="base-card__full-link")
    if not link_tag:
        return None
    raw_url = link_tag.get("href", "")
    # Keep clean LinkedIn URL (strip tracking params after ?)
    apply_url = raw_url.split("?")[0] if raw_url else ""
    match = re.search(r"-(\d{8,})$", apply_url)
    job_id = f"li_{match.group(1)}" if match else None
    if not job_id:
        return None

    title_tag   = card.find("h3", class_="base-search-card__title")
    company_tag = card.find("h4", class_="base-search-card__subtitle")
    loc_tag     = card.find("span", class_="job-search-card__location")

    title    = (title_tag.get_text(strip=True)   if title_tag   else "").strip()
    company  = (company_tag.get_text(strip=True) if company_tag else "").strip()
    location = (loc_tag.get_text(strip=True)     if loc_tag     else search_location).strip()

    # Every search now enforces f_WT=2 (remote work type), so results are
    # remote by construction; keep the text check only as a hybrid signal.
    is_remote = True

    return {
        "job_id":        job_id,
        "job_title":     title,
        "employer_name": company,
        "job_city":      location,
        "job_country":   search_location,
        "_search_country": infer_country_code(search_location),
        "job_is_remote": is_remote,
        "job_apply_link": apply_url,
        "job_description": "",
        "apply_options": [{"apply_link": apply_url, "is_direct": False, "publisher": "LinkedIn"}],
    }


def search_linkedin(keywords: str, location: str, remote_only: bool = False) -> list:
    url = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    params = {
        "keywords": keywords,
        "f_TPR":    "r259200",  # last 3 days
        "start":    0,
        "f_WT":     "2",  # remote-work-type only — every search is remote-only now
    }
    if remote_only:
        # No location filter — search spans every country instead of just
        # the scoped Gulf/Egypt/Europe list.
        params["location"] = ""
    else:
        params["location"] = location
    try:
        resp = requests.get(url, headers=LINKEDIN_HEADERS, params=params, timeout=15)
        if resp.status_code != 200:
            print(f"Warning: LinkedIn returned {resp.status_code} for '{keywords}' / {location}")
            return []
        soup = BeautifulSoup(resp.text, "html.parser")
        jobs = []
        for card in soup.find_all("li"):
            job = parse_card(card, location)
            if job:
                jobs.append(job)
        return jobs
    except requests.RequestException as e:
        print(f"Warning: LinkedIn search failed for '{keywords}': {e}")
        return []


# ── Telegram ──────────────────────────────────────────────────────────────────

def esc(text: str) -> str:
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def format_job(rank: int, job: dict) -> str:
    title      = esc(job.get("job_title") or "N/A")
    company    = esc(job.get("employer_name") or "N/A")
    location   = esc(job.get("job_city") or job.get("job_country") or "Unknown")
    is_remote  = job.get("job_is_remote", False)
    is_target  = job.get("_company_match", False)
    score      = job.get("_score", score_job(job))
    applicants = job.get("_applicants")

    title_lower = (job.get("job_title") or "").lower()
    if "hybrid" in title_lower or "hybrid" in location.lower():
        work_mode = "Hybrid"
    elif is_remote or "remote" in title_lower:
        work_mode = "Remote"
    else:
        work_mode = location

    apply_url  = job.get("job_apply_link") or ""
    safe_url   = apply_url.replace("&", "&amp;")
    apply_part = f' | <a href="{safe_url}">Apply on LinkedIn</a>' if safe_url else ""
    badge      = " [TARGET CO.]" if is_target else ""
    if applicants is None:
        competition = ""
    elif applicants <= 25:
        competition = f" | {applicants} applicants (low competition)"
    else:
        competition = f" | {applicants} applicants"

    return (
        f"<b>#{rank} {title}</b>{badge}\n"
        f"{company} | {work_mode}\n"
        f"<i>{score_label(score)} ({score} pts)</i>{competition}{apply_part}"
    )


def send_telegram(text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    lines = text.split("\n")
    chunks, current = [], ""
    for line in lines:
        candidate = current + line + "\n"
        if len(candidate) > 4000:
            if current:
                chunks.append(current.rstrip())
            current = line + "\n"
        else:
            current = candidate
    if current.strip():
        chunks.append(current.rstrip())
    for chunk in chunks:
        try:
            resp = requests.post(url, json={
                "chat_id":   TELEGRAM_CHAT_ID,
                "text":      chunk,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            }, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"Error sending Telegram message: {e}")


# ── Persistence ───────────────────────────────────────────────────────────────

def check_config():
    missing = [k for k in ("TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID")
               if not os.getenv(k) or "your_" in os.getenv(k)]
    if missing:
        print(f"ERROR: Missing values in .env: {', '.join(missing)}")
        sys.exit(1)


def load_seen_jobs() -> dict:
    if not os.path.exists(SEEN_JOBS_FILE):
        return {}
    with open(SEEN_JOBS_FILE, "r") as f:
        data = json.load(f)
    cutoff = (datetime.now() - timedelta(days=SEEN_JOBS_TTL_DAYS)).isoformat()
    return {jid: ts for jid, ts in data.items() if ts >= cutoff}


def save_seen_jobs(seen: dict):
    with open(SEEN_JOBS_FILE, "w") as f:
        json.dump(seen, f)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    check_config()
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting LinkedIn job search...")

    seen = load_seen_jobs()
    this_run_ids: set = set()
    general_jobs: list = []
    company_jobs: list = []

    # ── Pass 1: general role searches ────────────────────────────────────────
    print("--- General searches ---")
    for s in LINKEDIN_SEARCHES:
        jobs = search_linkedin(s["keywords"], s["location"], s.get("remote_only", False))
        kept = 0
        for job in jobs:
            job_id = job.get("job_id")
            if not job_id or job_id in seen or job_id in this_run_ids:
                continue
            this_run_ids.add(job_id)
            general_jobs.append(job)
            kept += 1
        print(f"  '{s['keywords']}' / {s['location']} -> {kept} new")

    # ── Pass 2: target company searches ──────────────────────────────────────
    print("--- Target company searches ---")
    for s in COMPANY_SEARCHES:
        jobs = search_linkedin(s["keywords"], s["location"])
        kept = 0
        for job in jobs:
            job_id = job.get("job_id")
            if not job_id or job_id in seen or job_id in this_run_ids:
                continue
            # Filter: only keep roles that touch Steven's skill domain
            title_words = set((job.get("job_title") or "").lower().split())
            if not title_words & COMPANY_RELEVANCE_TITLE_WORDS:
                continue
            job["_company_match"] = True
            this_run_ids.add(job_id)
            company_jobs.append(job)
            kept += 1
        print(f"  '{s['keywords']}' / {s['location']} -> {kept} relevant")

    print(f"General: {len(general_jobs)} | Company: {len(company_jobs)}")

    all_new = general_jobs + company_jobs
    if not all_new:
        send_telegram(
            "<b>Daily Job Report - " + datetime.now().strftime("%b %d, %Y") + "</b>\n"
            "No new LinkedIn jobs since last run. Check back tomorrow!"
        )
    else:
        # Enrich each pool's top candidates with applicant counts (low
        # competition bonus), re-sort, then take the top 5 from each.
        general_jobs = enrich_with_competition(general_jobs)
        company_jobs = enrich_with_competition(company_jobs)
        top_general  = general_jobs[:5]
        top_company  = company_jobs[:5]

        date_str = datetime.now().strftime("%b %d, %Y")
        lines = [
            f"<b>Daily Job Report - {date_str}</b>\n"
            f"Remote only | North Europe + Gulf + Egypt + Europe | LinkedIn only\n"
        ]

        if top_general:
            lines.append("<b>-- Best Role Matches --</b>")
            lines.append("")
            for i, job in enumerate(top_general, 1):
                lines.append(format_job(i, job))
                lines.append("")

        if top_company:
            lines.append("<b>-- Target Company Openings --</b>")
            lines.append("")
            for i, job in enumerate(top_company, 1):
                lines.append(format_job(i, job))
                lines.append("")

        send_telegram("\n".join(lines))
        print(f"Telegram sent: {len(top_general)} role matches + {len(top_company)} company matches.")

    now_iso = datetime.now().isoformat()
    for job_id in this_run_ids:
        seen[job_id] = now_iso
    save_seen_jobs(seen)


if __name__ == "__main__":
    main()
