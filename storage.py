# storage.py
import json
from pathlib import Path
from datetime import datetime
import csv

DB_PATH = Path("job_applications.json")
CSV_PATH = Path("job_applications.csv")

def load_db():
    if DB_PATH.exists():
        try:
            return json.loads(DB_PATH.read_text())
        except Exception:
            return []
    return []

def save_db(rows):
    DB_PATH.write_text(json.dumps(rows, indent=2))

def upsert_application(rows, company, role):
    # find latest entry for company+role, else create
    for r in reversed(rows):
        if r.get("company") == company and r.get("role") == role:
            return r
    new_row = {
        "company": company,
        "role": role,
        "created_at": datetime.now().isoformat(),
        "referral_targets": [],
        "notes_file": "",
    }
    rows.append(new_row)
    return new_row

def add_referrals(app_entry, candidates):
    """
    candidates: list of {name, linkedin_url, context}
    """
    existing = {c.get("linkedin_url") for c in (app_entry.get("referral_targets") or [])}
    added = 0
    for c in candidates:
        url = c.get("linkedin_url")
        if not url or url in existing:
            continue
        app_entry.setdefault("referral_targets", []).append(c)
        existing.add(url)
        added += 1
    return added

def export_csv(rows):
    # Flatten key fields for spreadsheet view
    fields = ["company", "role", "created_at", "referral_count", "referral_urls", "referral_reasons"]

    with CSV_PATH.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            refs = r.get("referral_targets") or []
            w.writerow({
                "company": r.get("company", ""),
                "role": r.get("role", ""),
                "created_at": r.get("created_at", ""),
                "notes_file": r.get("notes_file", ""),
                "referral_count": len(refs),
                "referral_urls": " | ".join([c.get("linkedin_url","") for c in refs][:10]),
                "referral_reasons": " | ".join([(x.get("reason","")) for x in refs[:10]]),

            })
def has_scheduled_interview(rows, message_id: str) -> bool:
    for r in rows:
        for ev in r.get("interviews", []):
            if ev.get("message_id") == message_id:
                return True
    return False

def add_interview_event(app, event_obj: dict):
    app.setdefault("interviews", []).append(event_obj)
