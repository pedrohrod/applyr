<div align="center">

# 🚀 applyr

**Stop applying manually. Let AI do it for you.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED.svg)](https://www.docker.com/)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](https://github.com/pedrohrod/applyr/pulls)

applyr scrapes jobs from LinkedIn and Gupy, scores each one against your resume with AI, generates a tailored cover letter, and applies automatically — all inside a Docker container.

[⚡ Getting Started](#setup) · [⚙️ Configuration](#configuration) · [🤝 Contributing](#contributing) · [🗺️ Roadmap](#roadmap)

</div>

---

## 🧠 How it works

```
🔍 Scrapers (LinkedIn · Gupy)
        ↓
🚫 Filters (blacklist, level, type, date)
        ↓
🤖 AI Match score (0–100)
        ↓  score ≥ threshold
✍️  Tailored cover letter
        ↓
📨 Auto-apply (Playwright)
        ↓
📊 Tracking (SQLite + CSV)
```

---

## ✨ Features

- 🔍 **Multi-platform scraping** — LinkedIn Easy Apply and Gupy out of the box
- 🤖 **AI-powered matching** — scores each job against your resume (0–100) before applying
- ✍️ **Tailored cover letters** — generated per job, not a template
- 💬 **Smart form filling** — AI answers screening questions based on your profile
- 🚫 **Blacklists & filters** — skip companies, titles, locations, experience levels you don't want
- 🔌 **Provider-agnostic AI** — works with Anthropic, OpenAI, Gemini, or Ollama (local/free)
- 📊 **Full tracking** — every application logged to SQLite and exportable as CSV
- 🐳 **Docker-ready** — one command to run, no environment setup headaches

---

## 📋 Requirements

- 🐳 [Docker](https://docs.docker.com/get-docker/) and Docker Compose
- 💼 LinkedIn and/or Gupy account
- 🔑 API key for one of the supported AI providers

---

## ⚡ Setup

```bash
git clone https://github.com/pedrohrod/applyr.git
cd applyr

cp .env.example .env
```

---

## ⚙️ Configuration

### 1. 🔑 Environment variables (`.env`)

```env
# AI provider: anthropic | openai | gemini | ollama
LLM_PROVIDER=anthropic
LLM_MODEL=                          # leave empty to use the provider default
LLM_API_URL=http://localhost:11434  # only required for ollama

ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=...

LINKEDIN_EMAIL=you@email.com
LINKEDIN_PASSWORD=yourpassword
GUPY_EMAIL=you@email.com
GUPY_PASSWORD=yourpassword
```

### 2. 🤖 Supported AI providers

| Provider | Default model | Required variable |
|---|---|---|
| `anthropic` | `claude-haiku-4-5-20251001` | `ANTHROPIC_API_KEY` |
| `openai` | `gpt-4o-mini` | `OPENAI_API_KEY` |
| `gemini` | `gemini-1.5-flash` | `GEMINI_API_KEY` |
| `ollama` | `llama3` | `LLM_API_URL` (no key needed) |

Switch providers by changing `LLM_PROVIDER` in `.env` — no code changes required.

### 3. 🔍 Job search preferences (`config/settings.yaml`)

```yaml
job_search:
  keywords:
    - "Software Engineer"
    - "Backend Developer"
  locations:
    - "Brazil"
  remote: true
  hybrid: true
  onsite: false

  experience_level:
    entry: true
    mid_senior_level: true

  job_types:
    full_time: true
    contract: true

  date_posted: "month"   # all_time | month | week | 24_hours

filters:
  company_blacklist:
    - "Acme Corp"
  title_blacklist:
    - "Director"
  apply_once_at_company: true

matching:
  threshold: 70           # minimum score (0–100) to apply

application:
  max_per_session: 50
  attach_cover_letter: true
```

### 4. 👤 Candidate profile (`config/profile.yaml`)

Fill in your real data. This file drives:
- 🤖 AI match scoring against job descriptions
- ✍️ Personalized cover letter generation
- 💬 Automatic answers to screening questions in application forms

Key fields:

```yaml
personal:
  name: "Your Name"
  email: "you@email.com"

salary_expectations:
  range: "USD 80,000 - 120,000"

availability:
  notice_period: "Immediately"

legal_authorization:
  us_work_authorization: "Yes"

work_preferences:
  remote_work: "Yes"
  open_to_relocation: "Yes"
  willing_to_undergo_background_checks: "Yes"
```

### 5. 📄 Resume

Place your resume PDF in the `resume/` folder:

```bash
cp /path/to/your/resume.pdf resume/resume.pdf
```

---

## 🐳 Running

```bash
docker compose up --build
```

Run in the background:

```bash
docker compose up --build -d
docker compose logs -f
```

---

## 📊 Output

After each run, results are saved in `data/`:

| File | Contents |
|---|---|
| `data/applications.db` | SQLite database with full application history |
| `data/applications.csv` | Exportable spreadsheet of all applications |
| `logs/applyr.log` | Detailed execution log |

CSV columns: `date`, `company`, `title`, `platform`, `score`, `url`, `cover_letter`

---

## 🌐 Supported platforms

| Platform | Scraping | Auto-apply |
|---|---|---|
| LinkedIn Easy Apply | ✅ | ✅ |
| Gupy | ✅ | ✅ |
| Greenhouse / Lever / Workday | 🔜 | 🔜 |
| Indeed | 🔜 | 🔜 |

---

## 🗂️ Project structure

```
applyr/
├── config/
│   ├── settings.yaml       # search filters, threshold, limits
│   └── profile.yaml        # your personal and professional data
├── resume/
│   └── resume.pdf          # your resume (add here)
├── src/
│   ├── ai/
│   │   ├── llm_provider.py     # provider abstraction (Anthropic, OpenAI, Gemini, Ollama)
│   │   ├── matcher.py          # resume ↔ job match scoring
│   │   ├── cover_letter.py     # per-job cover letter generation
│   │   ├── question_answerer.py # screening question answering
│   │   └── resume_parser.py    # PDF text extraction
│   ├── scrapers/
│   │   ├── linkedin.py         # LinkedIn scraper
│   │   └── gupy.py             # Gupy scraper
│   ├── applicator/
│   │   ├── linkedin.py         # LinkedIn Easy Apply bot
│   │   └── gupy.py             # Gupy application bot
│   ├── tracker/
│   │   └── db.py               # SQLite + CSV tracking
│   └── orchestrator.py         # main workflow orchestrator
├── data/                   # auto-generated
├── logs/                   # auto-generated
├── Dockerfile
├── docker-compose.yml
└── main.py
```

---

## 🗺️ Roadmap

- [ ] 🌐 Greenhouse / Lever / Workday portal support
- [ ] 📈 Web dashboard to visualize application history
- [ ] 🧬 Resume auto-tailoring per job (keyword injection)
- [ ] 📧 Email follow-up scheduling
- [ ] 🌍 Multi-language support for non-English job boards
- [ ] 🔍 Indeed scraper + auto-apply
- [ ] 🧪 Test suite

---

## 🤝 Contributing

Contributions are very welcome! Here's how to get started:

1. 🍴 Fork the repository
2. 🌿 Create a feature branch (`git checkout -b feature/new-platform`)
3. 💾 Commit your changes (`git commit -m 'feat: add Indeed scraper'`)
4. 📤 Push to your branch (`git push origin feature/new-platform`)
5. 🔁 Open a Pull Request

**💡 Ideas for contribution:**
- Add scrapers for new platforms (Indeed, Glassdoor, Workday, Lever, Greenhouse)
- Improve the AI matching prompt
- Add tests
- Improve bot detection resistance
- Build a CLI interface

Please open an [issue](https://github.com/pedrohrod/applyr/issues) first for major changes so we can discuss the approach.

---

## ⚠️ Disclaimer

This project automates actions on third-party platforms. Use responsibly:

- Respect the daily limits configured in `settings.yaml`
- Review `profile.yaml` carefully before running — automatic answers are based on that data
- Excessive automation may trigger bot detection and account restrictions

---

## 📄 License

[MIT](LICENSE) © 2026 Pedro Henrique
