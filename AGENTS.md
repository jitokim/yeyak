# Agent Guide for This Repo

Scope: Entire repository.

## Goals
- Fetch Seoul OA-2271 (Public Reservation Education) data daily, filter into v12 and v123, and email a concise summary with JSON attachments via GitHub Actions.

## Tech & Conventions
- Language: Python 3.10+ (CI uses 3.10).
- Dependencies: `requests` only (see `requirements.txt`). No extra libs.
- Encoding: UTF-8 everywhere. JSON dumps use `ensure_ascii=False` and `indent=2`.
- Filenames (outputs):
  - `seoul_education_all.json`
  - `seoul_education_v12.json`
  - `seoul_education_v123.json`
  - `seoul_education_summary.csv`
- Dataset: OA-2271 (`ListPublicReservationEducation`) with `list_total_count` and `row`.

## Filters
1) `AREANM` in {"강남구", "서초구", "송파구"}
2) `SVCSTATNM` in {"접수중", "안내중"}
3) `USETGTINFO` contains any of {"유아", "제한없음", "가족"}

Build lists: v12 = (1)&(2), v123 = (1)&(2)&(3).

## Files
- `fetch_reservations.py`: Pagination, retries, filtering, writes outputs listed above. Reads API key from `SEOUL_API_KEY`.
- `compose_email.py`: Reads `seoul_education_v12.json` and `seoul_education_v123.json`, prints a plain‑text body to stdout with up to 10 items per section, sorted by `RCPTBGNDT`.
- `.github/workflows/daily-email.yml`: Cron + manual workflow. Sends email with Gmail SMTP. Attaches v12/v123 JSON files.
- `requirements.txt`: `requests` only.
- `README.md`: Local run and secret setup instructions.
- `.env`: Untracked local env file (gitignored). Use for non-secrets like `MAIL_TO`; avoid committing secrets. In CI, prefer GitHub Secrets for `SEOUL_API_KEY`, `MAIL_USERNAME`, `MAIL_PASSWORD`.

## Coding Style
- Keep functions small and testable. Use type hints.
- Defensive parsing: missing JSON fields → empty strings.
- Date parsing via helper that accepts common formats; return `None` on failure.
- Retry on 5xx/connection errors with exponential backoff (max 3 attempts).

## Local Development
- Scripts auto-load `.env` in CWD without overriding existing env.
- Either export `SEOUL_API_KEY` manually or place it in uncommitted `.env`.
- Run: `python fetch_reservations.py` and preview: `python compose_email.py | less`.

## CI Notes
- Workflow prefers GitHub Secrets for `SEOUL_API_KEY`, `MAIL_USERNAME`, `MAIL_PASSWORD`; falls back to values loaded from `.env` if Secrets are not set.
- Email action: `dawidd6/action-send-mail@v3` with Gmail SMTP (465 SSL).
- Workflow loads `.env` and resolves env with Secrets priority. `MAIL_TO` comes from `.env`.
