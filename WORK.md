# Codex Prompt for `fetch_reservations.py`

**Instruction to Codex:**

Write a production-ready **Python 3.10** script named **`fetch_reservations.py`** that:

## 0) Purpose
- Calls the **Seoul Public Reservation OpenAPI (OA-2271)** endpoint and **downloads ALL rows** using pagination.
- Filters the rows into **two separate outputs**:
  - **v12**: rows satisfying conditions (1) and (2)
  - **v123**: rows satisfying conditions (1), (2), and (3)
- Saves results to JSON files and a compact CSV summary.
- Designed for running in CI (e.g., GitHub Actions): robust logging, exit codes, and retry.

## 1) Inputs & Environment
- Base URL (JSON):  
  `http://openapi.seoul.go.kr:8088/{API_KEY}/json/ListPublicReservationEducation/{start}/{end}/`
- **API key** comes from environment variable **`SEOUL_API_KEY`**. If missing or empty, print a clear error and exit(2).
- **Page size** = 1000. Use start=1,end=1000, then 1001..2000, … until all fetched.
- Use **requests** with:
  - timeout 20s
  - up to 3 retries with exponential backoff on 5xx or connection errors.

## 2) Data model & JSON shape
- Top-level key: `ListPublicReservationEducation`
- Keys:
  - `list_total_count` (int) — total rows
  - `row` (array) — data items
- Each row contains (at least) these fields:
  - `AREANM`, `SVCSTATNM`, `USETGTINFO`, plus others like `SVCID`, `SVCNM`, `SVCURL`, `RCPTBGNDT`, `RCPTENDDT`, etc.
- If the API occasionally returns an object without `row` or with empty `row`, treat it as empty page, not an error.

## 3) Filters
Implement **three** conditions exactly:

1) `AREANM` is one of: **"강남구", "서초구", "송파구"**  
2) `SVCSTATNM` is one of: **"접수중", "안내중"**  
3) `USETGTINFO` (string) **contains** any of:
   - `"유아"`, `"제한없음"`, `"가족"`
   - Contains = simple substring search (case-sensitive Korean OK). Null or missing should be treated as empty string (thus not matching).

Build two filtered lists:
- **filtered_v12** = rows satisfying (1) & (2)
- **filtered_v123** = rows satisfying (1) & (2) & (3)

## 4) Outputs
Write the following files in the current working directory:

1) **`reservation_all.json`**  
   - Entire concatenated array of all rows (no wrapper object).  
   - Sorted by `RCPTBGNDT` ascending; if absent, fallback to `SVCOPNBGNDT`; if both absent, keep original order.

2) **`reservation_v12.json`**  
   - Array of objects that pass (1)&(2).
   - Keep only useful fields to keep file small:  
     `["SVCID","SVCNM","SVCSTATNM","AREANM","USETGTINFO","SVCURL","RCPTBGNDT","RCPTENDDT","SVCOPNBGNDT","SVCOPNENDDT","PLACENM"]`

3) **`reservation_v123.json`**  
   - Same schema as v12 but filtered with (1)&(2)&(3).

4) **`reservation_summary.csv`**  
   - Columns:  
     `SVCID,SVCNM,SVCSTATNM,AREANM,USETGTINFO,SVCURL,RCPTBGNDT,RCPTENDDT`  
   - Include **only** rows from **v12** (not v123), sorted by `RCPTBGNDT` ascending.

### Formatting rules
- JSON files must be UTF-8, pretty-printed with indent=2, ensure_ascii=False.
- CSV must be UTF-8 with header, comma-separated, quote fields as needed.

## 5) Logging & CLI behavior
- Print concise progress logs to stdout:
  - total count discovered
  - page ranges fetched
  - final counts for: all, v12, v123
- Non-zero exit codes:
  - 2: configuration error (missing API key)
  - 3: HTTP or parsing failures after retries
- On success, exit(0).

## 6) Implementation details
- Use **`dataclasses`** for a `Row` type where fields are optional strings. Parsing should be defensive (missing keys → empty string).
- Implement a helper `parse_dt(s)` to normalize timestamps like `"2025-08-25 10:00:00.0"` into Python `datetime` (timezone-naive is fine). If parse fails, return `None`.
- Sorting key function:
  ```
  def sort_key(row):
      return (parse_dt(row.get("RCPTBGNDT") or "")
              or parse_dt(row.get("SVCOPNBGNDT") or "")
              or datetime.max)
  ```
- Implement substring matching for condition (3) using a simple function:
  ```
  def contains_any(haystack: str, needles: list[str]) -> bool:
      s = (haystack or "")
      return any(n in s for n in needles)
  ```
- Ensure network errors and non-200 responses are retried up to 3 times; then fail with clear message.

## 7) Small example in docstring
At the top of the script include a docstring with a quickstart:

```
Usage:
  export SEOUL_API_KEY=...   # required
  python fetch_reservations.py
Outputs:
  - reservation_all.json
  - reservation_v12.json
  - reservation_v123.json
  - reservation_summary.csv
```

## 8) Code quality
- Type hints throughout.
- No external deps beyond `requests` (from std GitHub Actions runner).
- Keep functions small and testable.

**End of instruction.**
