# AIDoBao

AIDoBao is the backend service behind [DoBao](https://github.com/tawan-ptk/DoBao). It stores health records, turns free-text Thai notes into structured drafts, builds weekly routines, and runs Baobuddy, the in-app assistant.

The service is a FastAPI application. It runs as a Vercel Python function in production and as a local server during development.

## What it does

**Records.** Every record (meal, activity, sleep, medication, measurement, wellbeing or appointment) is versioned rather than overwritten. Edits create a new version that points to the previous one, deletions are previewed before they run, and every confirmation carries an idempotency key, so a retried request cannot save the same record twice. Drafts expire after 30 minutes.

**Journal parsing.** A deterministic Thai parser resolves dates and times ("yesterday", "16.00", "this morning") against the Asia/Bangkok calendar and splits a sentence into candidate records. A time of day is kept as a period and never turned into an invented clock time. The language model only classifies the spans the rules could not place, and the user reviews every item before anything is stored.

**Extraction.** For single-category entries the model proposes field values, but each value must quote an exact span of the user's text as evidence. Values without matching evidence are dropped, not guessed.

**Scheduling.** A constraint-based scheduler places user-selected activities into a seven-day plan around locked items such as work, travel, medication and appointments. Plans are stored with the record revision they were built from, so outdated plans can be detected and re-checked.

**Assistant.** Requests are routed before any model call:

1. Fixed intents such as greetings, "summarise today" or "what did I take today" are answered from the user's records by plain code.
2. Calorie questions use a reference table with stated serving sizes. Unknown dishes are reported as unknown rather than estimated.
3. Meal suggestions come from a curated menu list filtered by allergies and conditions. The model only chooses among the eligible items.
4. General health questions are answered from curated evidence when it covers the question. Otherwise the service searches a fixed allow-list of public health sites (Thai Ministry of Public Health, Mahidol and Chulalongkorn hospitals, MedlinePlus, NIH, CDC, WHO and similar) and answers from those results with citations.
5. Anything outside health and the app is declined.

The assistant does not diagnose, prescribe or adjust doses.

## Model integration

The service calls a hosted model through OpenRouter. The default is `google/gemini-3.8-flash`, and the model can be changed per task in the environment. It previously used a LoRA fine-tune of Typhoon 2.5 (Qwen3 4B) on Apple Silicon. That approach has been replaced with prompting:

- **Zero-shot** for health answers, using a fixed system prompt plus the retrieved evidence.
- **Few-shot** for extraction and request routing, using worked examples taken from the synthetic data originally prepared for fine-tuning (`data/knowledge/fewshot.json`, rebuilt by `scripts/build_fewshot.py`).
- **Structured outputs.** Every task that returns JSON sends a strict JSON schema, and the existing validators still check each response before it is used.
- **Provider routing.** Requests are sent only to providers that do not retain prompts for training. No account details or stored records are included in the prompts.

When no API key is configured, the service falls back to the local MLX model if the weights are present.

## Running locally

Requirements: Python 3.13. The MLX packages in `requirements.lock.txt` are needed only for the optional local model.

```sh
python3.13 -m venv .venv
.venv/bin/pip install -r requirements.txt      # or requirements.lock.txt on Apple Silicon
cp .env.example .env                           # add your keys; never commit this file
.venv/bin/python scripts/run_api.py            # http://127.0.0.1:8765
```

Without a database URL the store uses SQLite at `data/local.sqlite3`. With a Postgres URL it uses a private schema that is not exposed through the Supabase REST API. A transaction pooler is supported.

```sh
.venv/bin/python -m pytest -q                          # full test suite
.venv/bin/python scripts/check_openrouter_live.py      # small live check against the hosted model
```

## Deployment

`scripts/stage_cloud.py` copies only the files the function needs into `dist/cloud-core/`. It refuses to stage environment files, credentials, SQLite databases or model weights. The staged folder is deployed to Vercel with `vercel --prod`.

## Project layout

| Path | Purpose |
| --- | --- |
| `app/main.py` | API routes, authentication and request validation |
| `services/store.py`, `services/pg_backend.py` | Versioned record store for SQLite and Postgres |
| `services/journal.py`, `services/extraction.py` | Thai journal parsing and evidence-checked extraction |
| `services/scheduler.py` | Seven-day routine planner |
| `services/chat*.py`, `services/agent.py` | Assistant routing, presets and record-based answers |
| `services/llm.py` | OpenRouter client, schemas, few-shot prompting and trusted web search |
| `services/rag.py`, `data/knowledge/` | Curated evidence and retrieval |
| `services/nutrition.py`, `services/food_reference.py` | Energy references and portion handling |
| `tests/` | Pytest suite covering the API, parsing, scheduling and model contracts |

## Limitations

This is a student research prototype. Its outputs have not been clinically validated, and accuracy figures in `reports/` come from small synthetic test sets, not from real patients.
