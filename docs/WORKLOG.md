# What We've Done — Implementation Log

A running log of all work completed on the Speedbots Content Generation Agent
(the web-app + CrewAI pipeline in `/home/haritha_13/content_agent`).

## Current Status (as of this log)

- Working end-to-end Flask web app at http://127.0.0.1:5001
- 6-agent CrewAI pipeline generating SEO blogs on cloud LLM (`gpt-oss:20b-cloud`)
- Strict internal-link policy (box-only links; empty box = zero links)
- AI image generation agent (Pollinations.ai, no key)
- Formatted HTML download (bold headings + clickable links)
- Desktop mirror copy at `/mnt/c/Users/haris/Desktop/content_agent` kept in sync

---

## 1. Required setup & config

- Created Python venv `.venv`; installed `crewai[tools]==1.14.7`, `pyyaml`, `flask 3.1.3`, `python-dotenv`, `pillow`, `requests`.
- Configured `.env` for **cloud LLM**:
  - `MODE=cloud`, `MODEL=gpt-oss:20b-cloud`, `API_BASE=https://ollama.com/v1`, `OLLAMA_API_KEY=...`
- `default_llm()` in `crew.py` picks cloud Ollama when `MODE=cloud` (or when `OLLAMA_API_KEY` + `API_BASE` are set), then standard cloud providers, then localhost Ollama.
- Always run with `PYTHONPATH=src` so CrewAI module resolution works.

## 2. Article formula fixes

- **Fixed `{TOPIC}` template bug** — tasks used `{TOPIC}` which was never interpolated; replaced with `{keyword}` everywhere.
- **Adopted the 9 natural headings** (user-approved variety) with word-count targets:
  `WHAT IS {keyword}` → `THE HIDDEN COST OF MANUAL PROCESSES` → `BEFORE AND AFTER: HOW AUTOMATION CHANGES YOUR WORKFLOW` → `HOW TO GET STARTED IN 6 STEPS` → `WHAT YOU PAY VS WHAT YOU SAVE` → `STAYING IN CONTROL: RISKS AND SAFEGUARDS` → `REAL RESULTS FROM {country} BUSINESSES` → `FREQUENTLY ASKED QUESTIONS` → `START AUTOMATING YOUR PROCESSES`.
- Writing task now outputs **plain text** (no markdown symbols), ALL CAPS headings on their own line, SEO TITLE / META DESCRIPTION / CTA BUTTONS block at the top.

## 3. Flask web app (built from scratch)

- `webapp/app.py` routes:
  - `/` (form: keyword, country, optional internal-links box)
  - `/generate` (POST, spawns background thread, returns job id)
  - `/status/<id>` + `/api/status/<id>` (progress via polling)
  - `/result/<id>` (rendered blog: bold headings, highlighted clickable links, hero image, Download HTML)
  - `/download/<id>`, `/image/<id>`
- Jobs tracked in an in-memory `JOBS` dict (daemon thread). **Note:** jobs are lost on Flask restart.
- **Bugs fixed during web-app work:**
  - *"Blog was not created"* — crew writes relative `output/...` paths against CWD, but the app ran from `webapp/`; fixed with `os.chdir(BASE_DIR)` at startup. Removed stray `webapp/output/`.
  - *Download returned raw text* with no formatting — see §6 (HTML download).

## 4. Internal-link handling

- `main.py run()` accepts `internal_links`; inputs include `{internal_links}`.
- `tasks.yaml` writes the CUSTOM LINKS RULE into strategy / writing / SEO tasks:
  - non-empty box → use ONLY those links, verbatim casing, no additions;
  - empty box → NO internal links at all (the earlier "strategy fallback" was removed at the user's request).
- **Post-processing `_ensure_internal_links`** (always runs after the crew):
  1. **Normalize** — full URLs rewritten to exact user casing; relative `/path` → `https://speedbots.com/path`.
  2. **Strip** — any internal URL / slug-like relative path not in the allowed list is removed (prose like `Tally / Zoho`, `₹25,000/month` is preserved).
  3. **Inject** — every allowed link missing from the body is added as `Internal link N: Learn more about this at <url>`.
- Removal of the earlier `_enforce_only_allowed_links` guard (was only running when links given).

## 5. AI image generation agent (new)

- New tool: `src/content_agent/tools/image_generator.py` → **Pollinations.ai** (`https://image.pollinations.ai/prompt/<prompt>`), free, no API key; saves under `output/images/`.
- **Fixed extension bug:** Pollinations returns JPEG for many prompts → tool now forces the file extension to match the actual response content-type (so `{slug}.jpg`, not a `.png` holding JPEG bytes).
- New agent `image_artist` + `image_task` in `agents.yaml` / `tasks.yaml` / `crew.py` (crew is now 6 agents, 6 tasks). Task runs after research, before writing; agent writes a detailed no-text prompt and saves `output/images/{keyword_slug}.png`.
- Web app: `_generate` captures the generated image, cleans stale images each run; `/image/<job_id>` serves it; `result.html` shows the hero image.

## 6. HTML download fix

- `/download/<job_id>` previously served the **raw .txt** (no formatting).
- Now builds a formatted HTML document from the same `blog_filter` used on the result page:
  - bold ALL-CAPS headings (`<strong>`)
  - clickable highlighted internal links
  - `<title>` taken from the blog's SEO TITLE
- Downloaded as `<slug>.html`, `Content-Type: text/html`; button relabelled **Download HTML**.

## 7. Rendering (`blog_filter`)

- Converts plain-text blog → HTML: bold headings (ALL-CAPS lines plus `SEO TITLE:`/`META DESCRIPTION:`/`CTA BUTTONS:`/`SEO REPORT`), clickable links.
- **Fixed nested-anchor bug:** links are replaced with `\u0000` placeholders first, then turned into anchors, so a link on a heading line never ends up inside `<strong>` twice / inside another `<a>`.
- **Fixed trailing-punctuation-in-URL bug:** URLs followed by `.` `,` `)` etc. render the punctuation *outside* the anchor (`…bank-reconciliation.` → link ends at `bank-reconciliation`, period after).

## 8. On-page SEO verification (measured)

Scorecard for the latest blogs (auto-measured):

| Blog | Title ≤60 | Meta 150–160 | Exact-phrase density | Links | FAQ |
|---|---|---|---|---|---|
| ai-bank-reconciliation | 57 PASS | 157 PASS | 0.38% | 5 | ok |
| ai-invoice-processing | 56 PASS | 172 (long) | 0.51% | 5 | ok |
| expense-management-automation | 63 FAIL | 151 PASS | 0.31% | 0* | 18 |
| ai-automation-for-coimbatore | 64 FAIL | 144 (short) | 0.31% | 1 | 7 |

\* empty links box → intentionally 0.

Known gaps: exact-phrase density lands ~0.3–0.5% (target ≥1%) and word counts are
~700–1030 vs the 2000–3000 target. These are **content-length/SEO opportunities**, not bugs.

## 9. End-to-end verification runs (all passed)

- **Custom links** ("AI invoice processing" / Singapore, box = `Accounting-Automation` + `Ai-Invoicing-Automation`):
  final blog had only those 2 links, case-exact (3× + 2×); image generated.
- **Empty box** ("expense management automation" / Malaysia): blog had **0 internal links**; image `expense-management-automation.jpg` correct JPEG; result page 0 link anchors + 1 hero image.
- **HTML download** (test client): `expense-management-automation.html` with 12 bold headings; `ai-invoice-processing.html` with 5 clickable anchors; both HTTP 200 with correct headers.
- **Repaired** the earlier link-less `ai-automation-for-coimbatore.txt` (links injected).

## 10. Recurring operational notes

- Restart Flask by killing the port-5001 PID, NOT `pkill` (self-match hangs the shell).
- Logs: `/tmp/flask_app.log`.
- Desktop copy synced after each change (`main.py`, `crew.py`, `agents.yaml`, `tasks.yaml`, `image_generator.py`, `webapp/app.py`, templates, outputs).
- `JOBS` is in-memory → old `/result`/`/download` links die on restart but the blog/image files persist under `output/`.