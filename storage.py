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

def export_csv(db, csv_path="job_applications.csv"):
    """
    Export a clean, candidate-friendly CSV.
    Avoid nested JSON fields (referrals/interviews/contacts) to prevent schema errors.
    """
    import csv

    rows = []
    for app in db:
        referrals = app.get("referrals", []) or []
        interviews = app.get("interviews", []) or []
        contacts = app.get("internal_contacts", []) or []
        jobs = app.get("recent_job_postings", []) or []

        rows.append({
            "company": app.get("company", ""),
            "role": app.get("role", ""),
            "last_updated": app.get("last_updated", app.get("created_at", "")),
            "notes_file": app.get("notes_file", ""),
            "recent_job_posts_count": len(jobs),
            "referrals_count": len(referrals),
            "known_contacts_count": len(contacts),
            "interviews_scheduled_count": len(interviews),
        })

    fieldnames = [
        "company",
        "role",
        "last_updated",
        "notes_file",
        "recent_job_posts_count",
        "referrals_count",
        "known_contacts_count",
        "interviews_scheduled_count",
    ]

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)

def has_scheduled_interview(rows, message_id: str) -> bool:
    for r in rows:
        for ev in r.get("interviews", []):
            if ev.get("message_id") == message_id:
                return True
    return False

def add_interview_event(app, event_obj: dict):
    app.setdefault("interviews", []).append(event_obj)
