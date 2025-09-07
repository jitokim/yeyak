"""
Usage:
  export SEOUL_API_KEY=...   # required
  python fetch_reservations.py
Outputs:
  - seoul_education_all.json
  - seoul_education_v12.json
  - seoul_education_v123.json
  - seoul_education_summary.csv
"""

from __future__ import annotations

import csv
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests


def _load_env_from_dotenv(path: str = ".env") -> None:
    """Lightweight .env loader: sets os.environ for KEY=VALUE lines.
    Does not override already-set environment variables."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if not s or s.startswith("#"):
                    continue
                if "=" not in s:
                    continue
                key, val = s.split("=", 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = val
    except FileNotFoundError:
        pass


API_BASE = (
    "http://openapi.seoul.go.kr:8088/{api_key}/json/"
    "ListPublicReservationEducation/{start}/{end}/"
)

PAGE_SIZE = 1000
TIMEOUT_SECS = 20
MAX_RETRIES = 3


# Fields to include for compact outputs
COMPACT_FIELDS: List[str] = [
    "SVCID",
    "SVCNM",
    "SVCSTATNM",
    "AREANM",
    "USETGTINFO",
    "SVCURL",
    "RCPTBGNDT",
    "RCPTENDDT",
    "SVCOPNBGNDT",
    "SVCOPNENDDT",
    "PLACENM",
]


@dataclass
class Row:
    SVCID: str = ""
    SVCNM: str = ""
    SVCSTATNM: str = ""
    AREANM: str = ""
    USETGTINFO: str = ""
    SVCURL: str = ""
    RCPTBGNDT: str = ""
    RCPTENDDT: str = ""
    SVCOPNBGNDT: str = ""
    SVCOPNENDDT: str = ""
    PLACENM: str = ""

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Row":
        # Defensive parsing with default empty strings for missing keys
        return Row(**{k: str(d.get(k) or "") for k in COMPACT_FIELDS})

    def to_compact_dict(self) -> Dict[str, str]:
        return {k: getattr(self, k) for k in COMPACT_FIELDS}


def parse_dt(s: str) -> Optional[datetime]:
    """Parse common timestamp formats. Return None on failure.

    Examples seen include:
    - "2025-08-25 10:00:00.0"
    - "2025-08-25 10:00:00"
    - "2025-08-25"
    - occasionally compact forms like "20250825100000"
    """
    if not s:
        return None
    s = s.strip()
    fmts = [
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%Y%m%d%H%M%S",
        "%Y%m%d",
    ]
    for fmt in fmts:
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            pass
    return None


def sort_key(row: Dict[str, Any]) -> datetime:
    dt = parse_dt((row.get("RCPTBGNDT") or "")) or parse_dt((row.get("SVCOPNBGNDT") or ""))
    return dt or datetime.max


def contains_any(haystack: str, needles: List[str]) -> bool:
    s = haystack or ""
    return any(n in s for n in needles)


def build_url(api_key: str, start: int, end: int) -> str:
    return API_BASE.format(api_key=api_key, start=start, end=end)


def fetch_page(session: requests.Session, url: str) -> Dict[str, Any]:
    """Fetch a single page with retries on 5xx and connection errors.

    Raises RuntimeError on final failure or 4xx responses.
    """
    backoff = 1.0
    last_exc: Optional[Exception] = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = session.get(url, timeout=TIMEOUT_SECS)
            status = resp.status_code
            if 200 <= status < 300:
                try:
                    return resp.json()
                except Exception as e:
                    # Parsing failure: retry unless last attempt
                    last_exc = e
                    if attempt == MAX_RETRIES:
                        break
                    time.sleep(backoff)
                    backoff *= 2
                    continue
            elif 500 <= status < 600:
                # Retry on 5xx
                if attempt == MAX_RETRIES:
                    raise RuntimeError(f"Server error {status} for URL: {url}")
                time.sleep(backoff)
                backoff *= 2
                continue
            else:
                # 4xx or other non-retryable
                raise RuntimeError(f"HTTP {status} for URL: {url}")
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            last_exc = e
            if attempt == MAX_RETRIES:
                break
            time.sleep(backoff)
            backoff *= 2
    if last_exc:
        raise RuntimeError(f"Failed to fetch after retries: {last_exc}")
    raise RuntimeError("Failed to fetch after retries")


def extract_payload(data: Dict[str, Any]) -> Tuple[int, List[Dict[str, Any]]]:
    """Extract total count and rows from API payload.

    If keys missing, treat as empty rows with count=0 for that page context.
    """
    key = "ListPublicReservationEducation"
    obj = data.get(key) if isinstance(data, dict) else None
    if not isinstance(obj, dict):
        return 0, []
    total = obj.get("list_total_count")
    try:
        total_count = int(total)
    except Exception:
        total_count = 0 if total is None else 0
    rows = obj.get("row")
    if not isinstance(rows, list):
        rows_list: List[Dict[str, Any]] = []
    else:
        rows_list = [r for r in rows if isinstance(r, dict)]
    return total_count, rows_list


def filter_rows(rows: Iterable[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Apply filters returning (filtered_v12, filtered_v123)."""
    areas = {"강남구", "서초구", "송파구"}
    statuses = {"접수중", "안내중"}
    needles = ["유아", "제한없음", "가족"]

    v12: List[Dict[str, Any]] = []
    v123: List[Dict[str, Any]] = []

    for r in rows:
        areanm = str(r.get("AREANM") or "")
        svcstat = str(r.get("SVCSTATNM") or "")
        usetgt = str(r.get("USETGTINFO") or "")

        cond1 = areanm in areas
        cond2 = svcstat in statuses
        if cond1 and cond2:
            v12.append(r)
            if contains_any(usetgt, needles):
                v123.append(r)

    return v12, v123


def project_compact(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for r in rows:
        row = Row.from_dict(r)
        out.append(row.to_compact_dict())
    return out


def write_json(path: str, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def write_csv_summary(path: str, rows: Iterable[Dict[str, Any]]) -> None:
    # Only rows from v12, with these columns
    cols = [
        "SVCID",
        "SVCNM",
        "SVCSTATNM",
        "AREANM",
        "USETGTINFO",
        "SVCURL",
        "RCPTBGNDT",
        "RCPTENDDT",
    ]
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=cols)
        writer.writeheader()
        for r in rows:
            writer.writerow({c: str(r.get(c) or "") for c in cols})


def main() -> int:
    # Load .env for local runs (no-op if missing). Does not override existing env.
    _load_env_from_dotenv()

    api_key = os.environ.get("SEOUL_API_KEY", "").strip()
    if not api_key:
        print("ERROR: Missing SEOUL_API_KEY environment variable.", file=sys.stderr)
        return 2

    session = requests.Session()

    start = 1
    end = PAGE_SIZE
    url = build_url(api_key, start, end)
    try:
        data = fetch_page(session, url)
    except Exception as e:
        print(f"ERROR: Initial fetch failed: {e}", file=sys.stderr)
        return 3

    total_count, first_rows = extract_payload(data)
    if total_count <= 0:
        # Still proceed with whatever we got from the first page
        print("Discovered total count: 0 (proceeding defensively)")
    else:
        print(f"Discovered total count: {total_count}")

    all_rows: List[Dict[str, Any]] = []
    if first_rows:
        all_rows.extend(first_rows)
    print(f"Fetched page: {start}-{end} -> {len(first_rows)} rows")

    # Compute remaining pages based on total_count if available; otherwise continue until an empty page
    if total_count > 0:
        total_pages = (total_count + PAGE_SIZE - 1) // PAGE_SIZE
        # Already fetched page 1
        for p in range(2, total_pages + 1):
            start = (p - 1) * PAGE_SIZE + 1
            end = p * PAGE_SIZE
            url = build_url(api_key, start, end)
            try:
                data = fetch_page(session, url)
            except Exception as e:
                print(f"ERROR: Fetch failed for {start}-{end}: {e}", file=sys.stderr)
                return 3
            _, rows = extract_payload(data)
            print(f"Fetched page: {start}-{end} -> {len(rows)} rows")
            if not rows:
                # Treat empty page as end of data
                break
            all_rows.extend(rows)
    else:
        # We don't know how many pages; continue until empty page observed
        p = 2
        while True:
            start = (p - 1) * PAGE_SIZE + 1
            end = p * PAGE_SIZE
            url = build_url(api_key, start, end)
            try:
                data = fetch_page(session, url)
            except Exception as e:
                print(f"ERROR: Fetch failed for {start}-{end}: {e}", file=sys.stderr)
                return 3
            _, rows = extract_payload(data)
            print(f"Fetched page: {start}-{end} -> {len(rows)} rows")
            if not rows:
                break
            all_rows.extend(rows)
            p += 1

    # Sort all rows by the specified key
    all_rows_sorted = sorted(all_rows, key=sort_key)

    # Filter
    filtered_v12, filtered_v123 = filter_rows(all_rows_sorted)

    # Compact versions for v12 and v123
    v12_compact = project_compact(filtered_v12)
    v123_compact = project_compact(filtered_v123)

    # Sort compact lists by RCPTBGNDT ascending for CSV; they already follow all_rows_sorted
    v12_sorted_for_csv = sorted(v12_compact, key=lambda r: sort_key(r))

    # Write outputs (renamed for clarity)
    write_json("seoul_education_all.json", all_rows_sorted)
    write_json("seoul_education_v12.json", v12_compact)
    write_json("seoul_education_v123.json", v123_compact)
    write_csv_summary("seoul_education_summary.csv", v12_sorted_for_csv)

    # Final logs
    print(f"Final counts -> all: {len(all_rows_sorted)}, v12: {len(v12_compact)}, v123: {len(v123_compact)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
