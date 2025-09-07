from __future__ import annotations

import json
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional


V12_PATH = "seoul_education_v12.json"
V123_PATH = "seoul_education_v123.json"


def _load_env_from_dotenv(path: str = ".env") -> None:
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
                if key and key not in __import__("os").environ:
                    __import__("os").environ[key] = val
    except FileNotFoundError:
        pass


def parse_dt(s: str) -> Optional[datetime]:
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
    return (
        parse_dt(str(row.get("RCPTBGNDT") or ""))
        or parse_dt(str(row.get("SVCOPNBGNDT") or ""))
        or datetime.max
    )


def load_list(path: str) -> List[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise ValueError("JSON root is not a list")
        # Ensure dicts
        return [d for d in data if isinstance(d, dict)]
    except FileNotFoundError:
        print(f"ERROR: Missing file {path}", file=sys.stderr)
        sys.exit(3)
    except Exception as e:
        print(f"ERROR: Failed to load {path}: {e}", file=sys.stderr)
        sys.exit(3)


def trunc(s: str, n: int) -> str:
    s = s or "-"
    return s if len(s) <= n else s[: max(0, n - 1)] + "…"


def line_for(row: Dict[str, Any]) -> str:
    areanm = trunc(str(row.get("AREANM") or "-"), 10)
    svcnm = trunc(str(row.get("SVCNM") or "-"), 40)
    svcstat = trunc(str(row.get("SVCSTATNM") or "-"), 10)
    rcpbgn = trunc(str(row.get("RCPTBGNDT") or "-"), 19)
    rcpend = trunc(str(row.get("RCPTENDDT") or "-"), 19)
    svcid = str(row.get("SVCID") or "-")
    link = (
        f"https://yeyak.seoul.go.kr/web/reservation/selectReservView.do?rsv_svc_id={svcid}"
        if svcid != "-"
        else "-"
    )
    return (
        f"- [{areanm}] {svcnm} ({svcstat}) | "
        f"접수: {rcpbgn} ~ {rcpend} | 링크: {link}"
    )


def section(title: str, rows: List[Dict[str, Any]]) -> str:
    out: List[str] = []
    out.append(title)
    out.append("")
    out.append(f"총 {len(rows)}건")
    out.append("")
    if not rows:
        out.append("해당 조건에 맞는 항목이 없습니다.")
        return "\n".join(out)
    # Sort and take top 10
    rows_sorted = sorted(rows, key=sort_key)[:10]
    for r in rows_sorted:
        out.append(line_for(r))
    return "\n".join(out)


def main() -> int:
    # Load .env for local preview (harmless if missing)
    _load_env_from_dotenv()
    v12 = load_list(V12_PATH)
    v123 = load_list(V123_PATH)

    parts: List[str] = []
    parts.append("서울시 공공서비스예약 - 일일 알림")
    parts.append("")
    parts.append(section("[v12] 조건 (1)&(2)", v12))
    parts.append("")
    parts.append("-----")
    parts.append("")
    parts.append(section("[v123] 조건 (1)&(2)&(3)", v123))

    body = "\n".join(parts)
    print(body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
