# job_agent.py
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

from linkup_job import linkup_search
from linkedin_referrals import find_referrals
from storage import load_db, save_db, upsert_application, add_referrals, export_csv

# Google Contacts (OAuth) — optional
from contacts_google import contacts_matching_company

# Gmail scan
from gmail_reader import fetch_recent_messages

# Interview parsing
from interview_parser import parse_interview_details

# Calendar push (your file is named calender_push.py)
from calendar_push import create_event


# Optional helpers from storage.py (if present)
try:
    from storage import has_scheduled_interview, add_interview_event
except Exception:
    has_scheduled_interview = None
    add_interview_event = None


# ---------------------------
# Small helpers
# ---------------------------
def _safe_filename(s: str) -> str:
    s = (s or "").strip().replace(" ", "_").replace("/", "_")
    return "".join(c for c in s if c.isalnum() or c in ("_", "-", "."))[:80]


def _first_line(s: str, max_len: int = 140) -> str:
    s = (s or "").strip().split("\n")[0].strip()
    if len(s) > max_len:
        s = s[:max_len].rsplit(" ", 1)[0] + "..."
    return s


def _guess_company_with_linkup(subject: str, sender: str) -> str:
    """
    Best-effort: identify company when parser says Unknown.
    LIMITED + optional so you don't burn API calls.
    """
    q = (
        'Identify the COMPANY NAME for this recruiting/interview email. '
        f'Subject: "{subject}". Sender: "{sender}". '
        "Return only the company name (1-3 words)."
    )
    resp = linkup_search(q)

    ans = ""
    if isinstance(resp, dict):
        ans = (resp.get("answer") or "").strip()
    else:
        ans = (getattr(resp, "answer", "") or "").strip()

    ans = _first_line(ans, max_len=40)
    # simple cleanup
    ans = ans.strip(" .:-")
    if not ans or len(ans) > 40:
        return "Unknown"
    return ans


class JobIntelligenceAgent:
    def __init__(self):
        self.prep_docs_dir = Path("interview_prep_docs")
        self.prep_docs_dir.mkdir(exist_ok=True)

    # ---------------------------
    # LINKUP: recent + applicant-focused queries
    # ---------------------------
    def build_queries(self, company: str, role: str) -> List[str]:
        # keep short, "recent bias" but readable
        return [
            f"{company} latest announcements launches earnings hiring last 30 days",
            f"{company} current projects roadmap AI initiatives last 30 days",
            f"{company} {role} interview process rounds coding system design 2025 2026",
        ]

    def bullets_from_answer(self, answer_text: str, max_bullets: int = 6) -> List[str]:
        if not answer_text:
            return []

        raw_lines = [ln.strip() for ln in answer_text.split("\n") if ln.strip()]
        bullets: List[str] = []

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
            if len(clean) > 190:
                clean = clean[:190].rsplit(" ", 1)[0].rstrip() + "..."

            bullets.append(clean)
            if len(bullets) >= max_bullets:
                break

        if not bullets:
            trimmed = " ".join(answer_text.split())
            if len(trimmed) > 190:
                trimmed = trimmed[:190].rsplit(" ", 1)[0].rstrip() + "..."
            bullets = [trimmed]

        return bullets

    def normalize_sources(self, resp: Any) -> List[Dict[str, str]]:
        # dict response
        if isinstance(resp, dict):
            srcs = resp.get("sources") or []
            out: List[Dict[str, str]] = []
            for s in srcs:
                if isinstance(s, dict):
                    out.append(
                        {
                            "title": (s.get("name") or s.get("title") or "Source").strip(),
                            "url": (s.get("url") or "").strip(),
                            "snippet": (s.get("snippet") or "").strip(),
                        }
                    )
            return out

        # pydantic / object response
        srcs = getattr(resp, "sources", None) or []
        out: List[Dict[str, str]] = []
        for s in srcs:
            out.append(
                {
                    "title": (getattr(s, "name", None) or getattr(s, "title", None) or "Source").strip(),
                    "url": (getattr(s, "url", "") or "").strip(),
                    "snippet": (getattr(s, "snippet", "") or "").strip(),
                }
            )
        return out

    def pick_top_sources(self, sources: List[Dict[str, str]], max_sources: int = 3) -> List[Dict[str, str]]:
        # remove noisy aggregators
        filtered = []
        for s in sources:
            url = (s.get("url") or "")
            if "news.google.com" in url:
                continue
            if not url.startswith("http"):
                continue
            filtered.append(s)
        return filtered[:max_sources]

    # ---------------------------
    # Job postings biased to last 7 days
    # ---------------------------
    def fetch_recent_job_postings(self, company: str, role: str, max_posts: int = 5) -> List[Dict[str, str]]:
        query = (
            f'{company} "{role}" (job OR opening OR "job posting") '
            f'("last 7 days" OR "this week" OR "posted" OR 2026 OR 2025) '
            f'(site:jobs OR site:careers OR site:greenhouse.io OR site:lever.co OR site:myworkdayjobs.com OR site:workdayjobs.com)'
        )

        resp = linkup_search(query)
        sources = self.normalize_sources(resp)

        postings: List[Dict[str, str]] = []
        seen = set()

        for s in sources:
            url = (s.get("url") or "").strip()
            if not url or url in seen:
                continue

            url_l = url.lower()
            if not any(k in url_l for k in ["job", "jobs", "careers", "greenhouse", "lever", "workday"]):
                continue

            seen.add(url)
            postings.append(
                {
                    "title": s.get("title") or f"{role} @ {company}",
                    "url": url,
                    "snippet": (s.get("snippet") or "")[:180],
                    "fetched_at": datetime.now().isoformat(),
                }
            )

            if len(postings) >= max_posts:
                break

        return postings

    def run_research(self, company: str, role: str) -> Dict[str, Any]:
        queries = self.build_queries(company, role)
        results: List[Dict[str, Any]] = []

        for q in queries:
            resp = linkup_search(q)  # IMPORTANT: no kwargs
            answer = resp.get("answer", "") if isinstance(resp, dict) else (getattr(resp, "answer", "") or "")
            sources = self.normalize_sources(resp)

            results.append(
                {
                    "query": q,
                    "answer_bullets": self.bullets_from_answer(answer, max_bullets=5),
                    "top_sources": self.pick_top_sources(sources, max_sources=3),
                }
            )

        recent_jobs = self.fetch_recent_job_postings(company, role, max_posts=5)

        return {"company": company, "role": role, "results": results, "recent_jobs": recent_jobs}

    def format_candidate_brief(self, bundle: Dict[str, Any]) -> str:
        company = bundle["company"]
        role = bundle["role"]

        merged_bullets: List[str] = []
        all_sources: List[Dict[str, str]] = []
        for r in bundle["results"]:
            merged_bullets.extend(r["answer_bullets"])
            all_sources.extend(r["top_sources"])

        # dedupe bullets
        seen = set()
        final_bullets: List[str] = []
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
        final_links: List[Dict[str, str]] = []
        for s in all_sources:
            url = s.get("url", "")
            if not url or url in used:
                continue
            used.add(url)
            final_links.append(s)
            if len(final_links) >= 3:
                break

        lines: List[str] = []
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
        lines.append("🧑‍💻 Recent job postings (last 7 days bias; max 5):")
        recent_jobs = bundle.get("recent_jobs") or []
        if recent_jobs:
            for j in recent_jobs[:5]:
                lines.append(f"- {j.get('title','Job posting')} — {j.get('url','')}")
        else:
            lines.append("- None found (try role wording: 'SWE' vs 'Software Engineer').")

        lines.append("")
        lines.append("🎯 Candidate next steps (10 minutes):")
        lines.append("- Read the 3 links above")
        lines.append(f"- Write 2 'Why {company} now?' points from the highlights")
        lines.append("- Prepare: 2 coding patterns + 1 system-design topic")

        return "\n".join(lines)

    # ---------------------------
    # MODE 1: Job research pipeline
    # ---------------------------
    def process_job(self, company: str, role: str) -> Dict[str, Any]:
        print("\n" + "=" * 70)
        print("🎯 JOB APPLICATION PROCESSING")
        print("=" * 70)
        print(f"Company: {company}")
        print(f"Role: {role}\n")

        print("1️⃣  Running Linkup research (recent-focused, candidate-friendly)...")
        bundle = self.run_research(company, role)
        print("   ✓ Research complete\n")

        print("2️⃣  Writing candidate brief (bullets + last-7-days postings)...")
        brief = self.format_candidate_brief(bundle)

        doc_path = self.prep_docs_dir / f"prep_{_safe_filename(company)}_{_safe_filename(role)}.txt"
        doc_path.write_text(brief)
        print(f"   ✓ Created: {doc_path}\n")

        print("3️⃣  Checking your contacts first (Google Contacts via OAuth)...")
        try:
            known_people = contacts_matching_company(company, max_hits=5)
        except Exception as e:
            known_people = []
            print(f"   ⚠ Contacts not available: {e}")

        if known_people:
            print("   ✅ Found people you already know (top 5):")
            for p in known_people:
                print(f"   - {p['name']} — {p['email']}")
        else:
            print("   - No matching contacts found (or contacts not connected).")

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

        # Persist to local DB (JSON) and CSV
        db = load_db()
        app = upsert_application(db, company, role)

        # IMPORTANT: your storage/export_csv must include these columns or it will crash.
        # If storage.py doesn't include notes_file in fieldnames, either add it there
        # or comment out this line.
        app["notes_file"] = str(doc_path)

        app["internal_contacts"] = known_people
        app["recent_job_postings"] = bundle.get("recent_jobs", [])

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
            "recent_job_posts_found": len(bundle.get("recent_jobs", [])),
        }

    # ---------------------------
    # MODE 2: Inbox scan → categorize → optionally push to calendar
    # ---------------------------
    def scan_inbox_and_push_interviews(self, max_emails: int = 50, dry_run: bool = True) -> Dict[str, Any]:
        print("\n" + "=" * 70)
        print("📩 INBOX SCAN → SUMMARY (Interview / Assessment)")
        print("=" * 70)
        print("Account used: Gmail OAuth popup")
        print(f"Scan window: last 30 days (max {max_emails} emails)\n")

        gmail_query = (
            'newer_than:30d '
            '('
            '"phone screen" OR "technical screen" OR "final round" OR onsite OR '
            '(interview OR recruiter OR hiring OR "hiring manager" OR "talent acquisition") OR '
            '(availability OR schedule OR scheduling OR reschedule OR "calendar invite") OR '
            '(assessment OR "online assessment" OR oa OR hackerrank OR codility OR karat)'
            ') '
            '-subject:(webinar OR digest OR newsletter OR shuttle OR rent OR alumni OR subscription OR cleaning OR loan OR amortization OR netbanking) '
            '-from:(no-reply OR noreply)'
        )

        emails = fetch_recent_messages(max_results=max_emails, query=gmail_query)
        print(f"Fetched {len(emails)} emails.\n")

        # Optional: resolve Unknown company via Linkup (limit)
        RESOLVE_UNKNOWN_COMPANY = False  # set True if you want it
        MAX_RESOLVES = 5
        resolved = 0

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

        db = load_db()
        created = 0

        for e in emails:
            parsed = parse_interview_details(e)
            if not parsed.get("is_interview"):
                continue

            stage = parsed.get("stage") or "Unclassified"
            stage_counts[stage] = stage_counts.get(stage, 0) + 1

            subject = e.get("subject", "(no subject)")
            sender = e.get("from", "")
            company = parsed.get("company", "Unknown")

            if RESOLVE_UNKNOWN_COMPANY and company == "Unknown" and resolved < MAX_RESOLVES:
                guessed = _guess_company_with_linkup(subject, sender)
                if guessed and guessed != "Unknown":
                    company = guessed
                    resolved += 1

            item = {
                "stage": stage,
                "company": company,
                "subject": subject,
                "from": sender,
                "due_hint": parsed.get("due_hint", ""),
                "start_iso": parsed.get("start_iso"),
                "meeting_link": parsed.get("meeting_link") or "",
                "message_id": e.get("message_id"),
            }

            # calendar-ready if it has a datetime OR meeting link
            if item["start_iso"] or item["meeting_link"]:
                calendar_ready.append(item)
            else:
                action_needed.append(item)

        # Print summary
        print("📊 INTERVIEW SUMMARY\n")
        for k in ["Assessment", "Phone Screen", "Technical Interview", "Onsite / Final", "Recruiter / Scheduling", "Unclassified"]:
            print(f"{k} ({stage_counts.get(k,0)})")
        print("\n" + "=" * 70)

        def _print_list(title: str, items: List[Dict[str, Any]], limit: int = 12):
            print(f"\n{title} (showing up to {limit})")
            if not items:
                print("• (none)")
                return
            for it in items[:limit]:
                due = f" — {it['due_hint']}" if it.get("due_hint") else ""
                when = f" — {it['start_iso']}" if it.get("start_iso") else ""
                print(f"• [{it['stage']}] {it['company']}: {it['subject']}{due}{when}")

        _print_list("🟡 Action needed / not scheduled yet", action_needed, limit=12)
        _print_list("✅ Calendar-ready (can be scheduled)", calendar_ready, limit=12)

        # Create events (if not dry-run)
        if not dry_run and calendar_ready:
            for it in calendar_ready:
                # require datetime to create an event
                if not it.get("start_iso"):
                    continue

                mid = it.get("message_id")
                if has_scheduled_interview and mid and has_scheduled_interview(db, mid):
                    continue

                title = f"{it['stage']}: {it['company']}"
                desc = (
                    f"Company: {it['company']}\n"
                    f"Stage: {it['stage']}\n"
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
                    print(f"\n⚠ Failed to create event for: {it['subject']} — {ex}")
                    continue

                app = upsert_application(db, it["company"], "Interview/Assessment")
                app.setdefault("interviews", [])

                interview_obj = {
                    "message_id": mid,
                    "subject": it["subject"],
                    "stage": it["stage"],
                    "company": it["company"],
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

        print("\n" + "=" * 70)
        print(f"Calendar events created: {created} (dry_run={dry_run})")
        print("=" * 70)

        return {
            "found_action_needed": len(action_needed),
            "found_calendar_ready": len(calendar_ready),
            "created": created,
            "stage_counts": stage_counts,
        }


if __name__ == "__main__":
    agent = JobIntelligenceAgent()

    while True:
        mode = input("\nChoose mode: (1) Job Research  (2) Scan Inbox→Calendar  (exit): ").strip().lower()
        if mode == "exit":
            break

        if mode == "2":
            dry = input("Dry run? (y/n): ").strip().lower() == "y"
            agent.scan_inbox_and_push_interviews(max_emails=50, dry_run=dry)
            continue

        company = input("Company: ").strip()
        role = input("Role: ").strip()
        agent.process_job(company, role)
