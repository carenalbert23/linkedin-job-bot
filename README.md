# 🤖 LinkedIn Job Bot

**Wake up to a ranked shortlist of remote jobs in your Telegram — every single morning.**

This bot searches LinkedIn for you once a day, scores every listing against your
skills, checks how many people already applied, and sends you only the best ones.
No dashboard. No login. Just a message on your phone.

It's ~500 lines of Python and it costs **$0** to run.

> 🇪🇬 النسخة العربية: **[README.ar.md](README.ar.md)**

---

## 📱 What you actually get

Every morning, one Telegram message that looks like this:

```
Daily Job Report - Sep 23, 2026
Remote only | Europe + Gulf + Egypt | LinkedIn only

-- Best Role Matches --

#1 AI Automation Engineer
Nordic Tech AB | Remote
Excellent match (78 pts) | 7 applicants (low competition) | Apply on LinkedIn

#2 Business Analyst, AI Division
Bayzat | Remote
Strong match (54 pts) | 23 applicants (low competition) | Apply on LinkedIn

-- Target Company Openings --

#1 Automation Specialist  [TARGET CO.]
Careem | Remote
Good match (41 pts) | Apply on LinkedIn
```

Tap the link, apply, done. **It never sends you the same job twice.**

---

## ✨ Why it's not just "a LinkedIn search"

| Feature | What it means for you |
|---|---|
| 🎯 **Smart scoring** | Every job gets points for role title, your skills, and location — the best matches float to the top automatically |
| 🥇 **Low-competition boost** | The bot opens the top listings and reads the applicant count. **7 applicants beats 400 applicants**, so it ranks those higher |
| 🔁 **Zero duplicates** | Remembers everything it sent for 7 days |
| 🏢 **Company watchlist** | Separately tracks *any* opening at the companies you actually want to work for |
| 🌍 **40+ searches per run** | Across every country you care about, plus a worldwide-remote sweep |
| 🆓 **No paid API** | Uses LinkedIn's public guest endpoint. No RapidAPI, no subscription, no key |

---

## 🚀 Setup — 5 minutes

### Step 1 — Get the code

```bash
git clone https://github.com/stevenayman70/linkedin-job-bot.git
cd linkedin-job-bot
pip install -r requirements.txt
```

> Needs **Python 3.10 or newer**.

### Step 2 — Create your Telegram bot

1. Open Telegram and message **[@BotFather](https://t.me/BotFather)**
2. Send `/newbot` and follow the prompts
3. Copy the token it gives you — looks like `1234567890:AAExampleTokenGoesHere`

### Step 3 — Get your chat ID

1. **Send any message to your new bot** (this step is required — skip it and you'll get nothing back)
2. Open this URL in your browser, pasting your token in:
   ```
   https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
   ```
3. Find `"chat":{"id":123456789` — that number is your chat ID

### Step 4 — Add your credentials

```bash
cp .env.example .env
```

Open `.env` and fill in both values:

```env
TELEGRAM_TOKEN=1234567890:AAExampleTokenGoesHere
TELEGRAM_CHAT_ID=987654321
```

> 🔒 `.env` is gitignored. Your tokens never leave your machine.

### Step 5 — Run it

```bash
python job_search.py
```

Check your Telegram. 🎉

---

## ⏰ Make it run automatically

You have two options. **Pick one.**

### Option A — On your own computer (recommended, most reliable)

**Windows** — one command, registers a daily task:

```powershell
powershell -ExecutionPolicy Bypass -File ".\setup_scheduler.ps1"
```

Change the time with `-At "09:30"`. Test it immediately with:

```powershell
Start-ScheduledTask -TaskName "LinkedIn Job Search Bot"
```

**Mac / Linux** — add a cron job with `crontab -e`:

```cron
0 11 * * * cd /path/to/linkedin-job-bot && /usr/bin/python3 job_search.py
```

### Option B — In the cloud with GitHub Actions (free, no computer needed)

This repo ships with [`.github/workflows/daily-job-search.yml`](.github/workflows/daily-job-search.yml),
which runs the bot on GitHub's servers every day at 08:00 UTC.

1. Fork this repo
2. Go to **Settings → Secrets and variables → Actions → New repository secret**
3. Add two secrets:
   - `TELEGRAM_TOKEN`
   - `TELEGRAM_CHAT_ID`
4. Go to the **Actions** tab, pick **Daily Job Search**, and hit **Run workflow** to test it

Change the schedule by editing the `cron:` line. Note that GitHub cron is
**always UTC**, so convert from your local time.

> ⚠️ **Heads up:** LinkedIn sometimes blocks requests coming from datacenter IP
> ranges, which is what GitHub's runners use. If your cloud runs come back empty
> while the same code works fine on your laptop, that's why — use **Option A**
> instead. This is a LinkedIn limitation, not a bug in the bot.

---

## 🛠️ Make it yours

Everything you'd want to change lives at the top of [`job_search.py`](job_search.py).

**1. Where you want to work** — edit `LINKEDIN_SEARCHES`:

```python
LINKEDIN_SEARCHES = [
    {"keywords": "AI automation",    "location": "Sweden"},
    {"keywords": "data engineer",    "location": "Germany"},
    # no location filter at all — searches everywhere:
    {"keywords": "python developer", "location": "Worldwide", "remote_only": True},
]
```

**2. Companies you're targeting** — edit `COMPANY_SEARCHES`. The bot pulls *every*
opening at these companies, then filters by title relevance:

```python
COMPANY_SEARCHES = [
    {"keywords": "Spotify", "location": "Sweden"},
    {"keywords": "Careem",  "location": "United Arab Emirates"},
]
```

**3. How jobs get scored** — three dictionaries control the ranking. Higher number
= higher priority:

| Dictionary | Controls | Example |
|---|---|---|
| `ROLE_SCORES` | Job titles you want | `"ai automation": 40` |
| `SKILL_SCORES` | Your tech stack | `"n8n": 22, "python": 6` |
| `LOCATION_SCORES` | Preferred countries | `"sweden": 25, "remote": 14` |

Put your dream role at the highest number and your dream country right behind it.

**4. How many jobs you get** — the bot sends the top 5 role matches and top 5
company matches. Change the `[:5]` slices in `main()`.

**5. How fresh the jobs are** — `f_TPR` in `search_linkedin()` is set to
`r259200` (last 3 days). Use `r86400` for the last 24 hours only.

---

## 🧠 Bonus: the Claude Code skill

[`job-search.md`](job-search.md) is a **Claude Code skill template** — a
fill-in-the-blanks prompt that makes Claude run a live, interactive job hunt for
you and write the results to a file. It complements the bot: the Python script is
your daily autopilot, the skill is for when you want to dig deeper by hand.

Replace the `<<PLACEHOLDERS>>` with your own profile, drop it in your project,
and run it.

---

## 📂 What's in here

```
job_search.py                       the bot — search, score, rank, send
job-search.md                       Claude Code skill template (English)
job-search.ar.md                    Claude Code skill template (Arabic)
README.md / README.ar.md            this guide, in English and Arabic
setup_scheduler.ps1                 one-command Windows daily scheduler
requirements.txt                    three dependencies
.env.example                        credential template
.github/workflows/
  └── daily-job-search.yml          free daily runs on GitHub Actions
```

---

## ❓ Troubleshooting

**Nothing arrived in Telegram**
→ Did you message your bot first? Telegram blocks bots from starting conversations.

**`ERROR: Missing values in .env`**
→ Your `.env` is missing, or still has the `your_..._here` placeholders in it.

**"LinkedIn returned 429"**
→ You're being rate-limited. Wait a few minutes. Don't run it in a loop.

**It found 0 new jobs**
→ Usually correct behaviour — it only reports jobs it hasn't sent in the last 7
days, and only ones posted in the last 3 days. To see everything again, delete
`seen_jobs.json`.

**Loads of irrelevant jobs**
→ Your `ROLE_SCORES` keywords are too broad. Make the titles more specific.

---

## ⚖️ Notes

This bot reads LinkedIn's **public, logged-out** job listings — the same pages
anyone sees without an account. It makes roughly 50 requests a day, which is
gentler than browsing by hand. Be sensible: don't crank up the frequency, and
don't run it in a loop.

Provided as-is for personal job hunting. LinkedIn can change their page structure
at any time, which would need the parser in `parse_card()` updated.

---

## 📜 License

MIT — do whatever you want with it. If it lands you a job, I'd love to hear about it.
