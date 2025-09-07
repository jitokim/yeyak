# Seoul Public Reservation (Education) — Daily Email

Fetches Seoul OA-2271 (Public Reservation Education) data, filters by conditions, and emails a daily summary via GitHub Actions.

## Setup
- Create a Gmail App Password (requires 2FA).
- Add GitHub Actions secrets under Settings → Secrets and variables → Actions:
  - `SEOUL_API_KEY`: Your Seoul OpenAPI key
  - `MAIL_USERNAME`: Your Gmail address (e.g., example@gmail.com)
  - `MAIL_PASSWORD`: Your Gmail App Password
  - Recipient is configured via `.env` → `MAIL_TO` (non-secret)

### .env
Create a `.env` file (not committed; see `.gitignore`) with:
```
MAIL_TO=gounbada13@kakao.com
SEOUL_API_KEY=
MAIL_USERNAME=
MAIL_PASSWORD=
```
Keep real secrets out of Git. In CI, set Secrets; locally, you may export or fill `.env`.

## Run locally
```bash
touch .env  # then edit as above
# Scripts auto-load .env (does not override existing env)
export SEOUL_API_KEY=YOUR_KEY  # or fill it in .env locally (DO NOT commit)
pip install -r requirements.txt
python fetch_reservations.py
python compose_email.py | less
```

Outputs (repo root):
- `seoul_education_all.json` — All rows (sorted)
- `seoul_education_v12.json` — Filtered by (1)&(2)
- `seoul_education_v123.json` — Filtered by (1)&(2)&(3)
- `seoul_education_summary.csv` — Compact summary from v12

## GitHub Actions
Workflow: `.github/workflows/daily-email.yml`

Triggers:
- Schedule: `0 0 * * *` (09:00 KST)
- Manual: workflow_dispatch

Email uses `dawidd6/action-send-mail@v3` with SMTP (`smtp.gmail.com:465`).
Workflow loads `.env` and resolves env with Secrets priority (Secrets override `.env`).
Locally, scripts auto-load `.env` so you can just run them without manual export (except secrets if you prefer not to store them in `.env`).

## Troubleshooting
- 401/403: Check `SEOUL_API_KEY` validity.
- Gmail auth errors: Ensure App Password and port 465 SSL.
- Empty results: Filters may be restrictive or dataset window may affect RCPT dates.
