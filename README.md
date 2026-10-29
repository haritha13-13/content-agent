# Content Generation Agent

A CrewAI multi-agent system that generates SEO-optimized blog posts for **Speedbots** — an AI automation company — exposed through a **Flask web app** with a custom internal-link policy and an AI image-generation agent.

Built on **CrewAI 1.14.7**, Python 3.12, `gpt-oss:20b-cloud` (cloud Ollama endpoint).

## How It Works

6 agents run in sequence. Each task's output feeds into the next:

```
User input (keyword + country + internal links box)
        │
        ▼
1. STRATEGY PLANNER  → Title + meta description + 4 strategy links + angle
        │
        ▼
2. RESEARCH ANALYST  → Stats, workflows, pricing, regional compliance, case study
        │
        ▼
3. IMAGE ARTIST      → Generates an AI hero image via Pollinations.ai
        │
        ▼
4. CONTENT WRITER    → 2000-3000 word blog following the 9-step article formula
        │
        ▼
5. SEO OPTIMIZER    → Keyword density, title/meta validation, link rules, headings
        │
        ▼
6. QUALITY REVIEWER → Strategy compliance score, checklist
        │
        ▼
POST-PROCESSING     → Internal-link enforcement (strip / upgrade / inject), then
                      the blog is displayed with bold headings + clickable links
```

## Internal-Link Policy (strict)

The blog may contain **ONLY the links the user types in the "internal links" custom box**.

| Box content | Behavior |
|---|---|
| Links provided | Only those exact URLs may appear. Case is preserved **verbatim** (`Ai-Invoicing-Automation` stays as typed). Relative paths like `/Ai-Invoicing-Automation` are upgraded to `https://speedbots.com/Ai-Invoicing-Automation`. Any link missing from the blog body is **injected**. Any other internal link is stripped. |
| Box empty | The blog gets **no internal links at all** — every internal URL and slug-like relative path is removed. |

Enforced after the crew finishes by `_ensure_internal_links()` in `main.py`.

## Web App (Flask)

Runs at **http://127.0.0.1:5001**.

- `GET /` — input form (keyword, country, optional internal-links box)
- `POST /generate` — starts a background generation job (in-memory `JOBS`, job UUID)
- `GET /status/<job_id>` + `GET /api/status/<job_id>` — progress page / JSON polling
- `GET /result/<job_id>` — renders the final blog with bold headings + highlighted clickable links + AI hero image
- `GET /download/<job_id>` — downloads the blog as **formatted HTML** (bold headings, clickable links)
- `GET /image/<job_id>` — serves the generated hero image

### Run the app

```bash
cd /home/haritha_13/content_agent/webapp
../.venv/bin/python app.py        # listens on 0.0.0.0:5001
```

Run it detached so it survives shell timeouts:

```bash
setsid bash -c 'cd /home/haritha_13/content_agent/webapp && exec /home/haritha_13/content_agent/.venv/bin/python app.py > /tmp/flask_app.log 2>&1' < /dev/null & disown
```

Stop it by killing the PID listening on port 5001 (`ss -tlnp | grep ':5001'`).

## Image Generation Agent

- New `image_artist` agent + `image_task` in the crew (runs after research).
- Uses `ImageGenerationTool` (`src/content_agent/tools/image_generator.py`) → **Pollinations.ai** (free, no API key).
- Saves to `output/images/<slug>.png|jpg`; extension is forced from the actual response content-type (Pollinations returns JPEG for many prompts).
- Shown as the blog hero image on the result page and cleaned out at the start of each run.

## Outputs

- `output/blogs/<slug>.txt` — final blog (post-processed: links enforced)
- `output/images/<slug>.jpg` — AI hero image
- `output/reports/strategy.json` — strategy (title, meta, cluster, internal_links, angle)
- `output/reports/research.md` — statistics + regional data
- `output/reports/seo_report.txt` — SEO checks (PASS/FAIL by the SEO agent)
- `output/reports/quality_review.md` — review checklist and score

## Project Structure

```
content_agent/
├── .env                          # LLM config (cloud Ollama: MODE/MODEL/API_BASE/OLLAMA_API_KEY)
├── pyproject.toml
├── knowledge/                    # Content strategy knowledge base (YAML + TXT)
├── src/content_agent/
│   ├── config/
│   │   ├── agents.yaml           # 6 agent definitions (incl. image_artist)
│   │   └── tasks.yaml            # 6 tasks (incl. image_task), CUSTOM LINKS RULE
│   ├── tools/
│   │   ├── web_researcher.py
│   │   ├── seo_checker.py
│   │   ├── content_validator.py
│   │   ├── file_writer.py
│   │   ├── file_reader.py
│   │   └── image_generator.py    # NEW — Pollinations.ai image tool
│   ├── crew.py                   # 6 agents + tasks orchestration
│   ├── main.py                   # run(), _ensure_internal_links()
│   └── helpers.py
├── webapp/
│   ├── app.py                    # Flask app + blog_filter + download/image routes
│   ├── requirements.txt          # flask, python-dotenv
│   └── templates/{index,status,result}.html
└── output/{blogs,images,reports,social}
```

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install "crewai[tools]==1.14.7" pyyaml flask python-dotenv
# .env:
#   MODE=cloud
#   MODEL=gpt-oss:20b-cloud
#   API_BASE=https://ollama.com/v1
#   OLLAMA_API_KEY=<your key>
```

Run CLI generation: `PYTHONPATH=src python -m content_agent.main`