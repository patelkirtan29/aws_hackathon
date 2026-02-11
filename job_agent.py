# job_agent.py
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from linkup_job import linkup_search
from linkedin_referrals import find_referrals
from storage import load_db, save_db, upsert_application, add_referrals, export_csv

from contacts_google import contacts_matching_company

from gmail_reader import fetch_recent_messages
from interview_parser import parse_interview_details
from calendar_push import create_event  # ✅ correct filename


try:
    from storage import has_scheduled_interview, add_interview_event
except Exception:
    has_scheduled_interview = None
    add_interview_event = None


class JobIntelligenceAgent:
    def __init__(self):
        self.prep_docs_dir = Path("interview_prep_docs")
        self.prep_docs_dir.mkdir(exist_ok=True)

    # ---------------------------
    # MODE 2: Inbox → readable summary (+ optional calendar push)
    # ---------------------------
    def scan_inbox_and_push_interviews(self, max_emails: int = 50, dry_run: bool = False):
        print("\n" + "=" * 70)
        print("📩 INBOX SCAN → INTERVIEW SUMMARY")
        print("=" * 70)
        print("Account used: Gmail OAuth popup")
        print(f"Scan window: last 30 days (max {max_emails} emails)\n")

        gmail_query = (
            'newer_than:30d ('
            '"online assessment" OR assessment OR "phone screen" OR "technical screen" OR '
            '"final round" OR onsite OR interview OR recruiter OR hiring OR "hiring manager" OR '
            '"talent acquisition" OR availability OR schedule OR scheduling OR reschedule OR "calendar invite"'
            ') '
            '-subject:(webinar OR digest OR newsletter OR shuttle OR rent OR alumni OR subscription OR cleaning OR community OR "lane closure") '
            '-from:(no-reply OR noreply)'
        )

        emails = fetch_recent_messages(max_results=max_emails, query=gmail_query)
        print(f"Fetched {len(emails)} emails.\n")

        db = load_db()

        stage_counts: Dict[str, int] = {
            "Assessment": 0,
            "Phone Screen": 0,
            "Technical Interview": 0,
            "Onsite / Final": 0,
            "Recruiter / Scheduling": 0,
            "Unclassified": 0,
        }

        action_needed: List[Dict[str, Any]] = []
        calendar_ready: List[Dict[str, Any]] = []

        for e in emails:
            parsed = parse_interview_details(e)
            if not parsed.get("is_interview"):
                continue

            stage = parsed.get("stage") or "Unclassified"
            if stage not in stage_counts:
                stage = "Unclassified"
            stage_counts[stage] += 1

            item = {
                "company": parsed.get("company", "Unknown"),
                "stage": stage,
                "subject": e.get("subject", "(no subject)"),
                "from": e.get("from", ""),
                "due_hint": parsed.get("due_hint", ""),
                "start_iso": parsed.get("start_iso"),
                "meeting_link": parsed.get("meeting_link", ""),
                "message_id": e.get("message_id"),
            }

            # calendar-ready only if real datetime extracted OR meeting link + clear scheduling stage
            if item["start_iso"] or (item["meeting_link"] and stage in ["Recruiter / Scheduling", "Phone Screen", "Technical Interview", "Onsite / Final"]):
                calendar_ready.append(item)
            else:
                action_needed.append(item)

        # Pretty print summary
        print("📊 INTERVIEW SUMMARY (last 30 days)")
        print("")
        for k in ["Assessment", "Phone Screen", "Technical Interview", "Onsite / Final", "Recruiter / Scheduling", "Unclassified"]:
            print(f"{k} ({stage_counts[k]})")
        print("")

        # Human-readable items
        def _print_items(title: str, items: List[Dict[str, Any]], limit: int = 10):
            if not items:
                return
            print(f"✅ {title} (showing up to {limit})")
            for it in items[:limit]:
                company = it["company"]
                stage = it["stage"]
                due = f" — {it['due_hint']}" if it.get("due_hint") else ""
                when = f" — {it['start_iso']}" if it.get("start_iso") else ""
                print(f"• [{stage}] {company}: {it['subject']}{due}{when}")
                if it.get("meeting_link"):
                    print(f"   link: {it['meeting_link']}")
            print("")

        _print_items("Action needed / not scheduled yet", action_needed, limit=12)
        _print_items("Calendar-ready (can be scheduled)", calendar_ready, limit=12)

        # Calendar push (only for calendar-ready with start_iso)
        created = 0
        if not dry_run:
            for it in calendar_ready:
                if not it.get("start_iso"):
                    continue

                mid = it.get("message_id")
                if has_scheduled_interview and mid and has_scheduled_interview(db, mid):
                    continue

                title = f"{it['stage']}: {it['company']}"
                desc = (
                    f"Subject: {it['subject']}\n"
                    f"From: {it['from']}\n\n"
                    f"Meeting link: {it.get('meeting_link','')}\n"
                ).strip()

                try:
                    ev = create_event(
                        title=title,
                        start_iso=it["start_iso"],
                        duration_mins=60,
                        description=desc,
                        location=it.get("meeting_link", ""),
                        calendar_id="primary",
                    )
                except Exception as ex:
                    print(f"⚠ Failed to create event for: {it['subject']} — {ex}")
                    continue

                # store
                app = upsert_application(db, it["company"], it["stage"])
                app.setdefault("interviews", [])
                interview_obj = {
                    "message_id": mid,
                    "company": it["company"],
                    "stage": it["stage"],
                    "subject": it["subject"],
                    "start_iso": it["start_iso"],
                    "meeting_link": it.get("meeting_link", ""),
                    "calendar_event_id": ev.get("id"),
                    "calendar_event_link": ev.get("htmlLink"),
                    "created_at": datetime.now().isoformat(),
                }
                if add_interview_event:
                    add_interview_event(app, interview_obj)
                else:
                    app["interviews"].append(interview_obj)

                created += 1

            save_db(db)
            export_csv(db)

        print("=" * 70)
        print(f"Calendar events created: {created} (dry_run={dry_run})")
        print("=" * 70)


if __name__ == "__main__":
    agent = JobIntelligenceAgent()

    while True:
        mode = input("\nChoose mode: (1) Job Research  (2) Inbox Summary  (exit): ").strip().lower()
        if mode == "exit":
            break

        if mode == "2":
            dry = input("Dry run? (y/n): ").strip().lower() == "y"
            agent.scan_inbox_and_push_interviews(max_emails=50, dry_run=dry)
            continue

        # Mode 1 can stay as your existing job research flow (not pasted here)
        company = input("Company: ").strip()
        role = input("Role: ").strip()
        print("Mode 1 not included in this snippet — keep your existing process_job() if needed.")
