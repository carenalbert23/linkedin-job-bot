# Job Search Skill (Template)

A Claude Code skill that runs a live job hunt for you and formats the results.
**Fill in the `<<...>>` placeholders below with your own details before using it.**

> 🇪🇬 النسخة العربية: **[job-search.ar.md](job-search.ar.md)**

---

## Who You Are

You are helping a job seeker with the following profile:

- **Name:** `<<YOUR NAME>>`
- **Background:** `<<YOUR DEGREE / FIELD>>`
- **Skills:** `<<YOUR TOP 5-8 SKILLS — e.g. AI automation, n8n, Python, Claude API>>`
- **Experience:** `<<1-2 SENTENCES ON REAL PROJECTS YOU'VE SHIPPED>>`
- **Languages:** `<<LANGUAGES + FLUENCY>>`
- **Preferences:** `<<REMOTE / HYBRID / ONSITE>>`, `<<TARGET COUNTRIES>>`, `<<SALARY OR CURRENCY>>`

---

## Your Task

Search for current job openings that match this profile. Follow every step below in order.

---

## Step 1 — Web Search for Live Jobs

Run web searches using these queries one by one. Swap the bracketed terms for
your own role titles and regions.

### General Role Searches
1. `<<ROLE 1>> remote <<REGION>> <<YEAR>> hiring`
2. `<<ROLE 2>> remote <<REGION>> <<YEAR>>`
3. `<<ROLE 3>> remote <<REGION>> hiring now`
4. `<<KEY TOOL>> consultant remote <<REGION>> <<YEAR>>`

### Job Boards
5. `site:remotive.com <<ROLE 1>> <<YEAR>>`
6. `site:wellfound.com <<ROLE 1>> remote <<REGION>>`
7. `site:linkedin.com/jobs <<ROLE 1>> remote <<REGION>> <<YEAR>>`
8. `site:<<LOCAL JOB BOARD>> <<ROLE 1>> remote <<REGION>>`

### Target-Company Searches
9. `site:linkedin.com/jobs <<COMPANY A>> OR <<COMPANY B>> <<ROLE>> remote`
10. `<<INDUSTRY>> startup <<ROLE>> remote <<YEAR>> hiring`

For each result found, extract:
- Job title
- Company name
- Location / remote status
- Apply link
- Why it matches the profile (one sentence)

---

## Step 2 — Generate LinkedIn Search URLs

Build ready-to-click LinkedIn URLs using this pattern:

```
https://www.linkedin.com/jobs/search/?keywords=<<KEYWORDS>>&location=<<LOCATION>>&f_WT=2&f_TPR=r604800
```

**Parameters explained:**

| Parameter | Meaning | Values |
|---|---|---|
| `keywords` | What to search for | URL-encoded, e.g. `AI%20Automation` |
| `location` | Where | URL-encoded country or city |
| `f_WT` | Work type | `1` = on-site, `2` = remote, `3` = hybrid |
| `f_TPR` | Posted within | `r86400` = 24h, `r604800` = 7 days |
| `f_C` | Specific company IDs | Comma-separated |

Generate one URL per target role/region pair, for example:

1. `<<ROLE 1>>` — `<<COUNTRY 1>>`
2. `<<ROLE 1>>` — `<<COUNTRY 2>>`
3. `<<ROLE 2>>` — `<<COUNTRY 1>>`
4. `<<KEY TOOL>>` — Worldwide remote (omit `location` entirely)

---

## Step 3 — Format Output

Present results in this format:

```
## Job Search Results — [Today's Date]

### Live Openings Found

| # | Job Title | Company | Location | Link | Match Reason |
|---|-----------|---------|----------|------|--------------|
| 1 | ...       | ...     | ...      | ...  | ...          |

---

### Target Companies Currently Hiring
- Company | Role | Link

---

### LinkedIn Search Links (Click to Open)
1. [Role — Country](linkedin_url)
2. [Role — Country](linkedin_url)

---

### Quick Tips
- Sort LinkedIn by "Most Recent" after opening
- Filter by "Easy Apply" to move faster
- Connect with the hiring manager before applying
- Prioritise listings with fewer than ~25 applicants

---
*Searched on: [date] — run this skill again tomorrow for fresh results*
```

---

## Step 4 — Save Results

Save the full output to `job-results.md` in the current project directory.
If the file already exists, prepend today's results at the top (newest first).

---

## Target Roles

List the exact job titles you want. The more specific, the better the matches:

- `<<ROLE 1 — e.g. AI Automation Specialist>>`
- `<<ROLE 2 — e.g. AI Agentic Developer>>`
- `<<ROLE 3 — e.g. Business Analyst (AI / Tech)>>`
- `<<ROLE 4>>`
- `<<ROLE 5>>`

---

## Target Companies

Group the companies you'd actually want to work for. Three tiers works well:

### Tier 1 — Startups in your niche
`<<COMPANY>>`, `<<COMPANY>>`, `<<COMPANY>>`

### Tier 2 — Larger regional employers
`<<COMPANY>>`, `<<COMPANY>>`, `<<COMPANY>>`

### Tier 3 — Global remote-friendly
`<<COMPANY>>`, `<<COMPANY>>`, `<<COMPANY>>`

> Tip: keep this list in sync with `COMPANY_SEARCHES` and `TARGET_COMPANIES`
> in `job_search.py` so the automated bot and the Claude skill hunt for the
> same companies.
