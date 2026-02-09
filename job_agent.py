# job_agent.py
from datetime import datetime
from pathlib import Path

from linkup_job import linkup_search
from linkedin_referrals import find_referrals
from storage import load_db, save_db, upsert_application, add_referrals, export_csv

# Google Contacts (OAuth, no export)
from contacts_google import contacts_matching_company

# Gmail → Interview extraction → Calendar push
from gmail_reader import fetch_recent_messages
from interview_parser import parse_interview_details
from calendar_push import create_event


# --- Optional storage helpers (if you added them to storage.py) ---
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
    # Linkup query strategy: recent + applicant-focused
    # ---------------------------
    def build_queries(self, company: str, role: str):
        recent = '"last 30 days" OR "last month" OR 2026 OR 2025 OR latest OR recent'
        return [
            f'{company} announcements earnings launches hiring {recent}',
            f'{company} projects roadmap AI agents infrastructure {recent}',
            f'{company} {role} interview process rounds coding system design behavioral {recent}',
        ]

    # ---------------------------
    # Extract clean bullets from Linkup answer
    # ---------------------------
    def bullets_from_answer(self, answer_text: str, max_bullets: int = 6):
        if not answer_text:
            return []

        raw_lines = [ln.strip() for ln in answer_text.split("\n") if ln.strip()]
        bullets = []

        skip_starts = (
            "in the last", "recent", "overall", "here are", "highlights include",
            "announcements include", "recent announcements", "recent findings",
        )

        for ln in raw_lines:
            clean = ln.strip("•- \t")
            low = clean.lower()

            if any(low.startswith(s) for s in skip_starts):
                continue
            if len(clean) < 35:
                continue

            clean = " ".join(clean.split())

            if len(clean) > 200:
                clean = clean[:200].rsplit(" ", 1)[0].rstrip() + "..."

            bullets.append(clean)
            if len(bullets) >= max_bullets:
                break

        if not bullets:
            trimmed = " ".join(answer_text.split())
            if len(trimmed) > 200:
                trimmed = trimmed[:200].rsplit(" ", 1)[0].rstrip() + "..."
            bullets = [trimmed]

        return bullets

    # ---------------------------
    # Normalize sources from Linkup response
    # ---------------------------
    def normalize_sources(self, resp):
        # dict fallback
        if isinstance(resp, dict):
            srcs = resp.get("sources") or []
            out = []
            for s in srcs:
                if isinstance(s, dict):
                    out.append({
                        "title": (s.get("name") or s.get("title") or "Source").strip(),
                        "url": (s.get("url") or "").strip(),
                        "snippet": (s.get("snippet") or "").strip(),
                    })
            return out

        # object response (pydantic)
        srcs = getattr(resp, "sources", None) or []
        out = []
        for s in srcs:
            out.append({
                "title": (getattr(s, "name", None) or getattr(s, "title", None) or "Source").strip(),
                "url": (getattr(s, "url", "") or "").strip(),
                "snippet": (getattr(s, "snippet", "") or "").strip(),
            })
        return out

    def pick_top_sources(self, sources, max_sources=3):
        filtered = []
        for s in sources:
            url = s.get("url", "")
            if "news.google.com" in url:
                continue
            filtered.append(s)
        return filtered[:max_sources]

    # ---------------------------
    # Run Linkup research
    # ---------------------------
    def run_research(self, company: str, role: str):
        queries = self.build_queries(company, role)
        results = []

        for q in queries:
            resp = linkup_search(q)  # IMPORTANT: no kwargs

            # answer text
            if isinstance(resp, dict):
                answer = resp.get("answer") or ""
            else:
                answer = getattr(resp, "answer", "") or ""

            sources = self.normalize_sources(resp)

            results.append({
                "query": q,
                "answer_bullets": self.bullets_from_answer(answer, max_bullets=5),
                "top_sources": self.pick_top_sources(sources, max_sources=3),
            })

        return {"company": company, "role": role, "queries": queries, "results": results}

    # ---------------------------
    # Candidate brief formatting (bullets + links)
    # ---------------------------
    def format_candidate_brief(self, bundle):
        company = bundle["company"]
        role = bundle["role"]

        merged_bullets = []
        all_sources = []
        for r in bundle["results"]:
            merged_bullets.extend(r["answer_bullets"])
            all_sources.extend(r["top_sources"])

        # dedupe bullets
        seen = set()
        final_bullets = []
        for b in merged_bullets:
            k = b.lower()
            if k in seen:
                continue
            seen.add(k)
            final_bullets.append(b)
            if len(final_bullets) >= 6:
                break

        # dedupe links
        used = set()
        final_links = []
        for s in all_sources:
            url = s.get("url", "")
            if not url or url in used:
                continue
            used.add(url)
            final_links.append(s)
            if len(final_links) >= 3:
                break

        lines = []
        lines.append(f"RECENT JOB BRIEF — {company} ({role})")
        lines.append(f"Generated: {datetime.now().isoformat()}")
        lines.append("")
        lines.append("✅ Recent highlights (min reading, max signal):")

        if final_bullets:
            for i, b in enumerate(final_bullets, 1):
                lines.append(f"{i}. {b}")
        else:
            lines.append("- No highlights found (Linkup returned limited data).")

        lines.append("")
        lines.append("🔗 Top links (read max 3):")
        if final_links:
            for s in final_links:
                lines.append(f"- {s.get('title','Source')} — {s.get('url','')}")
        else:
            lines.append("- No links available.")

        lines.append("")
        lines.append("🎯 Candidate next steps (10 minutes):")
        lines.append("- Read the 3 links above")
        lines.append(f"- Write 2 'Why {company} now?' points from the bullets")
        lines.append("- Prepare: 2 coding patterns + 1 system-design topic")

        return "\n".join(lines)

    # ---------------------------
    # JOB RESEARCH MODE
    # ---------------------------
    def process_job(self, company, role):
        print("\n" + "=" * 70)
        print("🎯 JOB APPLICATION PROCESSING")
        print("=" * 70)
        print(f"Company: {company}")
        print(f"Role: {role}\n")

        # 1) Linkup research
        print("1️⃣  Running Linkup research (recent-focused, candidate-friendly)...")
        bundle = self.run_research(company, role)
        print("   ✓ Research complete\n")

        # 2) Prep doc
        print("2️⃣  Writing candidate brief (bullets only)...")
        brief = self.format_candidate_brief(bundle)

        safe_company = company.strip().replace(" ", "_")
        safe_role = role.strip().replace(" ", "_").replace("/", "_")
        doc_path = self.prep_docs_dir / f"prep_{safe_company}_{safe_role}.txt"
        doc_path.write_text(brief)
        print(f"   ✓ Created: {doc_path}\n")

        # 3) Contacts-first referrals (Google Contacts via OAuth)
        print("3️⃣  Checking your contacts first (Google Contacts via OAuth)...")
        try:
            known_people = contacts_matching_company(company, max_hits=5)
        except Exception as e:
            known_people = []
            print(f"   ⚠ Contacts not available: {e}")

        if known_people:
            print("   ✅ Found people you already know (ranked by company/email domain match):")
            for p in known_people:
                print(f"   - {p['name']} — {p['email']}")
        else:
            print("   - No matching contacts found (or contacts not connected).")

        # 4) LinkedIn referral targets via Linkup (backup targets)
        print("\n4️⃣  Finding referral targets (LinkedIn via Linkup)...")
        candidates = find_referrals(company, role, max_people=8)

        if candidates:
            print("   Top referral targets:")
            for c in candidates[:5]:
                reason = c.get("reason", "Potential referral")
                print(f"   - {c.get('name','LinkedIn profile')} ({reason})")
                print(f"     {c.get('linkedin_url','')}")
        else:
            print("   - No referral profiles found (try another company/role).")

        # 5) Save to “sheet” (JSON + CSV)
        db = load_db()
        app = upsert_application(db, company, role)
        app["notes_file"] = str(doc_path)
        app["internal_contacts"] = known_people  # stored locally only

        added = add_referrals(app, candidates)

        save_db(db)
        export_csv(db)

        print(f"\n5️⃣  ✓ Added {added} new referral profiles")
        print("    ✓ Spreadsheet updated: job_applications.csv\n")

        print("=" * 70)
        print("JOB PROCESSING COMPLETE!")
        print("=" * 70)

        return {
            "company": company,
            "role": role,
            "prep_doc": str(doc_path),
            "referrals_added": added,
            "internal_contacts_found": len(known_people),
        }

    # ---------------------------
    # INBOX → CALENDAR MODE (demo-simple)
    # ---------------------------
    def scan_inbox_and_push_interviews(self, company_hint: str = "", max_emails: int = 50, dry_run: bool = False):
        print("\n" + "=" * 70)
        print("📩 INBOX SCAN → CALENDAR (Interview Scheduling)")
        print("=" * 70)
        print("Account used: the Gmail account you authorize in the OAuth browser popup.")
        print(f"Scan limit: last 14 days, up to {max_emails} emails.\n")

        gmail_query = (
            'newer_than:14d (interview OR "phone screen" OR "technical screen" OR recruiter OR schedule OR invitation)'
        )
        emails = fetch_recent_messages(max_results=max_emails, query=gmail_query)

        print(f"Fetched {len(emails)} emails matching Gmail query:\n  {gmail_query}\n")

        db = load_db()
        created_count = 0
        found_count = 0

        for e in emails:
            parsed = parse_interview_details(e)
            if not parsed.get("is_interview"):
                continue

            found_count += 1

            # demo-simple: only schedule if we can parse a datetime
            if not parsed.get("start_iso"):
                print(f"⚠ Skipping (no datetime parsed): {e.get('subject','(no subject)')}")
                continue

            mid = e.get("message_id")
            if has_scheduled_interview and mid and has_scheduled_interview(db, mid):
                continue

            subject = e.get("subject", "Interview")
            meeting_link = parsed.get("meeting_link") or ""
            start_iso = parsed["start_iso"]

            title = f"Interview: {subject}"
            description = (
                f"From: {e.get('from','')}\n"
                f"Subject: {subject}\n\n"
                f"Snippet:\n{e.get('snippet','')}\n\n"
                f"Meeting link:\n{meeting_link}\n"
            ).strip()

            print(f"🧠 Detected interview email:")
            print(f"   - Subject: {subject}")
            print(f"   - When:   {start_iso}")
            if meeting_link:
                print(f"   - Link:   {meeting_link}")

            if dry_run:
                print("   (dry_run=True) → Not creating calendar event.\n")
                continue

            try:
                ev = create_event(
                    title=title,
                    start_iso=start_iso,
                    duration_mins=60,
                    description=description,
                    location=meeting_link,
                    calendar_id="primary",
                )
            except Exception as ex:
                print(f"⚠ Failed to create calendar event: {ex}\n")
                continue

            # Store into your local DB under a bucket
            app = upsert_application(db, company_hint or "Inbox Interviews", "Interview")
            app.setdefault("interviews", [])

            interview_obj = {
                "message_id": mid,
                "subject": subject,
                "start_iso": start_iso,
                "meeting_link": meeting_link,
                "calendar_event_id": ev.get("id"),
                "calendar_event_link": ev.get("htmlLink"),
                "created_at": datetime.now().isoformat(),
            }

            if add_interview_event:
                add_interview_event(app, interview_obj)
            else:
                # fallback: just append locally (still works)
                app["interviews"].append(interview_obj)

            created_count += 1
            print(f"✅ Calendar event created.")
            if ev.get("htmlLink"):
                print(f"   Event link: {ev['htmlLink']}")
            print()

        save_db(db)
        export_csv(db)

        print("=" * 70)
        print(f"DONE — Found {found_count} interview-ish emails; created {created_count} calendar events.")
        print("=" * 70)

        return {"found": found_count, "created": created_count}


if __name__ == "__main__":
    agent = JobIntelligenceAgent()

    while True:
        mode = input("\nChoose mode: (1) Job Research  (2) Scan Inbox→Calendar  (exit): ").strip().lower()
        if mode == "exit":
            break

        if mode == "2":
            company_hint = input("Company hint (optional, e.g., Google): ").strip()
            dry = input("Dry run? (y/n): ").strip().lower() == "y"
            agent.scan_inbox_and_push_interviews(company_hint=company_hint, max_emails=50, dry_run=dry)
            continue

        # default: mode 1
        company = input("Company: ").strip()
        role = input("Role: ").strip()
        agent.process_job(company, role)
