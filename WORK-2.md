# Codex Prompt: Set up a GitHub Actions project that emails filtered Seoul reservation results

**Goal**  
Create a minimal, production-ready GitHub project that:
1) Fetches all rows from **Seoul OA-2271** OpenAPI via pagination.  
2) Filters results into **v12** (conditions 1&2) and **v123** (conditions 1&2&3).  
3) Sends an email **daily** with a concise summary and attaches the JSON files.  
4) Runs entirely on **GitHub Actions** (cron) with **no extra infra**.  
5) Uses **Gmail SMTP** via App Password (no Kakao/SMS).

> Assume the data shape matches the user's sample (`ListPublicReservationEducation` with `list_total_count` and `row`), and the filters are exactly as below.

---

## Filters
1) `AREANM` ∈ { **"강남구", "서초구", "송파구"** }  
2) `SVCSTATNM` ∈ { **"접수중", "안내중"** }  
3) `USETGTINFO` contains any of { **"유아", "제한없음", "가족"** } (simple substring; missing → no match)

Build two lists:
- **filtered_v12**: (1) & (2)
- **filtered_v123**: (1) & (2) & (3)

---

## Deliverables (files to generate in the repo)
- `fetch_reservations.py` — Pagination + filtering + write outputs (reuse/align with WORK.md spec).  
- `compose_email.py` — Makes a concise text summary string for email body from the filtered JSON files.  
- `.github/workflows/daily-email.yml` — The scheduled workflow to fetch, compose, and email.  
- `requirements.txt` — Minimal python deps (`requests`).  
- `README.md` — Quick start with secrets setup and manual dispatch instructions.

> The scripts must be UTF-8 and robust for CI. Use logging, proper exit codes, and fail fast on network errors after retries.

---

## Implementation details

### 1) `fetch_reservations.py`
Implement based on the **WORK.md** instruction (same behavior), with these outputs in repo root:

- `reservation_all.json` — all rows (sorted by RCPTBGNDT then SVCOPNBGNDT).  
- `reservation_v12.json` — filtered (1)&(2) with trimmed fields:  
  `["SVCID","SVCNM","SVCSTATNM","AREANM","USETGTINFO","SVCURL","RCPTBGNDT","RCPTENDDT","SVCOPNBGNDT","SVCOPNENDDT","PLACENM"]`  
- `reservation_v123.json` — same schema, filtered (1)&(2)&(3).

**Inputs**  
- Read API key from `SEOUL_API_KEY` env.  
- Base URL (JSON): `http://openapi.seoul.go.kr:8088/{API_KEY}/json/ListPublicReservationEducation/{start}/{end}/`  
- Page size: **1000** (1..1000, 1001..2000, ... until `list_total_count` covered).  
- Retries: up to 3 with exponential backoff on 5xx/connection errors. Timeout 20s.

**CLI**  
- Exit(2) if API key missing, Exit(3) on repeated HTTP failure.  
- Print total count, page ranges fetched, final counts (all, v12, v123).

### 2) `compose_email.py`
- Read `reservation_v12.json` and `reservation_v123.json`.  
- Produce a **plain-text** email body with sections:
  - Heading: `서울시 공공서비스예약 - 일일 알림`  
  - `v12` summary: total count, and up to **10** top items (sorted by RCPTBGNDT asc) with one-line bullets:
    `- [AREANM] SVCNM (SVCSTATNM) | 접수: RCPTBGNDT ~ RCPTENDDT | 링크: https://yeyak.seoul.go.kr/web/reservation/selectReservView.do?rsv_svc_id=SVCID`
  - Divider
  - `v123` summary: total count, and up to **10** items same format.
- Truncate safely if strings are too long; missing fields → `-`.  
- Print the final body text to **stdout**.  
- Exit(0) even if lists are empty; the body should still say "해당 조건에 맞는 항목이 없습니다." for each empty section.

### 3) `.github/workflows/daily-email.yml`
Create a GitHub Actions workflow that:

- **Triggers**:  
  - `schedule`: `"0 0 * * *"` (09:00 KST)  
  - `workflow_dispatch` (manual run)
- **Permissions**: `contents: write` (only if you want to commit artifacts; optional)
- **Env Secrets** (set by the user under *Settings → Secrets and variables → Actions*):  
  - `SEOUL_API_KEY` — Seoul OA-2271 API key  
  - `MAIL_USERNAME` — Gmail address (e.g., `example@gmail.com`)  
  - `MAIL_PASSWORD` — Gmail **App Password** (not login password)

**Job steps**:
1. Checkout repo.  
2. Set up Python 3.10.  
3. Install requirements (`pip install -r requirements.txt`).  
4. Run `fetch_reservations.py`. (If it fails, **stop** the job.)  
5. Run `compose_email.py` and capture its stdout to a step output `body`.  
6. Send email using `dawidd6/action-send-mail@v3`:
   - `server_address: smtp.gmail.com`
   - `server_port: 465`
   - `username: ${{ secrets.MAIL_USERNAME }}`
   - `password: ${{ secrets.MAIL_PASSWORD }}`
   - `subject: "서울시 예약: 일일 알림"`
   - `to: <your email>`
   - `from: GitHub Actions <${{ secrets.MAIL_USERNAME }}>`
   - `body: ${{ steps.compose.outputs.body }}`
   - `attachments: reservation_v12.json, reservation_v123.json`

**Example workflow content** (Codex should generate this YAML):
```yaml
name: Daily Seoul Reservation Email
on:
  schedule:
    - cron: "0 0 * * *"  # 09:00 KST
  workflow_dispatch:

permissions:
  contents: read

jobs:
  email:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.10"

      - name: Install deps
        run: pip install -r requirements.txt

      - name: Fetch reservations
        env:
          SEOUL_API_KEY: ${{ secrets.SEOUL_API_KEY }}
        run: python fetch_reservations.py

      - name: Compose email body
        id: compose
        run: |
          BODY="$(python compose_email.py)"
          # GitHub Actions multi-line output
          {
            echo "body<<'EOF'"
            echo "$BODY"
            echo "EOF"
          } >> "$GITHUB_OUTPUT"

      - name: Send email
        uses: dawidd6/action-send-mail@v3
        with:
          server_address: smtp.gmail.com
          server_port: 465
          username: ${{ secrets.MAIL_USERNAME }}
          password: ${{ secrets.MAIL_PASSWORD }}
          subject: "서울시 예약: 일일 알림"
          to: you@example.com
          from: GitHub Actions <${{ secrets.MAIL_USERNAME }}>
          body: ${{ steps.compose.outputs.body }}
          attachments: reservation_v12.json, reservation_v123.json
```

### 4) `requirements.txt`
```
requests>=2.25.0
```

### 5) `README.md`
Include:
- **Setup**  
  - Create Gmail App Password (2FA required).  
  - Add secrets: `SEOUL_API_KEY`, `MAIL_USERNAME`, `MAIL_PASSWORD`.  
- **Run locally**  
  ```bash
  export SEOUL_API_KEY=...
  pip install -r requirements.txt
  python fetch_reservations.py
  python compose_email.py | less
  ```
- **Manual dispatch** via Actions tab.  
- **Troubleshooting**  
  - 401/403: check API key.  
  - Gmail: ensure App Password; port 465 SSL.  
  - Empty results: check filters (AREANM/SVCSTATNM/USETGTINFO) and date windows.

---

## Constraints & Quality
- Python scripts must be resilient to missing keys and empty pages.  
- Logging to stdout; clear error messages.  
- No external deps beyond `requests`.  
- UTF-8 throughout; ensure_ascii=False in JSON dumps.  
- Keep functions small, typed, and testable.

**End of prompt.**
