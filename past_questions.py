# past_questions.py
from __future__ import annotations

import csv
import os
from datetime import datetime
from typing import Dict, List, Any

from linkup_job import linkup_search

CSV_HEADERS = ["company", "role", "stage", "topic", "difficulty", "question", "source", "added_at"]


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def _cell_to_str(v: Any) -> str:
    """
    DictReader can produce:
    - normal strings
    - None
    - lists (when a CSV row has extra columns -> stored under key None)
    """
    if v is None:
        return ""
    if isinstance(v, list):
        # join extra fields back into one cell
        return " ".join(str(x) for x in v if x is not None).strip()
    return str(v).strip()


def _read_csv(csv_path: str) -> List[Dict[str, str]]:
    if not os.path.exists(csv_path):
        return []

    rows: List[Dict[str, str]] = []
    with open(csv_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for r in reader:
            if not r:
                continue

            clean: Dict[str, str] = {}

            # Handle normal header keys
            for k, v in r.items():
                if k is None:
                    # extra columns (list) -> append to question field
                    extra = _cell_to_str(v)
                    if extra:
                        clean["question"] = (clean.get("question", "") + " " + extra).strip()
                    continue

                clean[k] = _cell_to_str(v)

            # Ensure all required headers exist
            for h in CSV_HEADERS:
                clean.setdefault(h, "")

            rows.append(clean)

    return rows


def _ensure_csv(csv_path: str) -> None:
    if os.path.exists(csv_path):
        return
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writeheader()


def _append_rows(csv_path: str, new_rows: List[Dict[str, str]]) -> None:
    if not new_rows:
        return

    _ensure_csv(csv_path)

    existing = _read_csv(csv_path)
    seen = set((_norm(r.get("company")), _norm(r.get("role")), _norm(r.get("question"))) for r in existing)

    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)

        for r in new_rows:
            key = (_norm(r.get("company")), _norm(r.get("role")), _norm(r.get("question")))
            if key in seen:
                continue
            seen.add(key)

            row_out = {h: _cell_to_str(r.get(h, "")) for h in CSV_HEADERS}
            writer.writerow(row_out)


def _filter_matches(rows: List[Dict[str, str]], company: str, role: str) -> List[Dict[str, str]]:
    c = _norm(company)
    r = _norm(role)

    out = []
    for row in rows:
        rc = _norm(row.get("company"))
        rr = _norm(row.get("role"))

        # partial match for flexibility
        if c and c not in rc:
            continue
        if r and r not in rr:
            continue
        out.append(row)
    return out


def _parse_questions_from_linkup(answer: str, company: str, role: str) -> List[Dict[str, str]]:
    if not answer:
        return []

    lines = [ln.strip("•- \t").strip() for ln in answer.split("\n") if ln.strip()]
    out: List[Dict[str, str]] = []

    for ln in lines:
        if len(ln) < 18:
            continue
        if len(ln) > 200:
            ln = ln[:200].rsplit(" ", 1)[0] + "..."

        # "question-ish" heuristic
        low = ln.lower()
        if "?" not in ln and not any(
            k in low for k in ["implement", "design", "explain", "difference", "time complexity", "sql", "oop", "system"]
        ):
            continue

        out.append({
            "company": company,
            "role": role,
            "stage": "Mixed",
            "topic": "Mixed",
            "difficulty": "Unknown",
            "question": ln,
            "source": "Linkup (public sources)",
            "added_at": datetime.now().isoformat(),
        })

        if len(out) >= 12:
            break

    return out


def fetch_past_questions_from_web(company: str, role: str, limit: int = 8) -> List[Dict[str, str]]:
    query = (
        f'{company} {role} interview questions '
        f'(leetcode OR "interview experience" OR geeksforgeeks OR interviewbit OR glassdoor) '
        f'(2025 OR 2026 OR recent)'
    )

    resp = linkup_search(query)

    if isinstance(resp, dict):
        answer = resp.get("answer") or ""
    else:
        answer = getattr(resp, "answer", "") or ""

    rows = _parse_questions_from_linkup(answer, company, role)
    return rows[:limit]


def get_past_questions(
    company: str,
    role: str,
    csv_path: str = "past_questions.csv",
    limit: int = 8,
    auto_fetch_if_missing: bool = True,
) -> List[Dict[str, str]]:

    rows = _read_csv(csv_path)
    matches = _filter_matches(rows, company, role)

    if matches:
        return matches[:limit]

    if not auto_fetch_if_missing:
        return []

    fetched = fetch_past_questions_from_web(company, role, limit=limit)
    if fetched:
        _append_rows(csv_path, fetched)

    rows2 = _read_csv(csv_path)
    matches2 = _filter_matches(rows2, company, role)
    return matches2[:limit]
