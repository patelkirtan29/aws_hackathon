# job_agent.py
from __future__ import annotations

import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from linkup_job import linkup_search
from linkedin_referrals import find_referrals
from storage import load_db, save_db, upsert_application, add_referrals, export_csv

# Google Contacts (OAuth)
from contacts_google import contacts_matching_company

# Gmail → Interview extraction → Calendar push
from gmail_reader import fetch_recent_messages
from interview_parser import parse_interview_details

# ✅ IMPORTANT: file name is calendar_push.py
from calendar_push import create_event

# Optional storage helpers (if you added them to storage.py)
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
    # LINKUP: recent + applicant-focused queries
    # ---------------------------
    def build_queries(self, company: str, role: str) -> List[str]:
        recent = '"last 30 days" OR "last month" OR 2026 OR 2025 OR latest OR recent'
        return [
            f'{company} announcements earnings launches hiring {recent}',
            f'{company} projects roadmap AI agents infrastructure {recent}',
            f'{company} {role} interview process rounds coding system design behavioral {recent}',
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
        out = []
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
        filtered = []
        for s in sources:
            url = s.get("url", "")
            if "news.google.com" in url:
                continue
            filtered.append(s)
        return filtered[:max_sources]

    # ---------------------------
    # NEW: Recent job postings (last 7 days bias; Linkup)
    # ---------------------------
    def fetch_recent_job_postings(self, company: str, role: str, max_posts: int = 5) -> List[Dict[str, str]]:
        query = (
            f'{company} "{role}" (job OR opening OR "job posting") ("last 7 days" OR "this week" OR 2026 OR 2025) '
            f'(site:careers OR site:jobs OR site:greenhouse.io OR site:lever.co OR site:workdayjobs.com OR site:myworkdayjobs.com)'
        )

        resp = linkup_search(query)
        sources = self.normalize_sources(resp)

        postings: List[Dict[str, str]] = []
        seen = set()

        for s in sources:
            url = s.get("url", "")
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

    # ---------------------------
    # Interview themes extraction (public sources via Linkup)
    # ---------------------------
    CODING_TOPIC_MAP = {
        "arrays": [r"\barray\b", r"\btwo pointer", r"\bsliding window\b", r"\bprefix sum\b", r"\bsubarray\b"],
        "strings": [r"\bstring\b", r"\banagram\b", r"\bsubstring\b", r"\bpalindrome\b"],
        "hashmap": [r"\bhash\b", r"\bhashmap\b", r"\bdictionary\b", r"\bset\b"],
        "stack/queue": [r"\bstack\b", r"\bqueue\b", r"\bmonotonic\b"],
        "heap": [r"\bheap\b", r"\bpriority queue\b"],
        "binary search": [r"\bbinary search\b", r"\blower bound\b", r"\bupper bound\b"],
        "trees": [r"\btree\b", r"\bbinary tree\b", r"\bbst\b", r"\btraversal\b"],
        "graphs": [r"\bgraph\b", r"\bdfs\b", r"\bbfs\b", r"\bdijkstra\b", r"\btopological\b"],
        "dp": [r"\bdp\b", r"\bdynamic programming\b", r"\bknapsack\b"],
        "greedy": [r"\bgreedy\b"],
        "backtracking": [r"\bbacktracking\b", r"\bpermutation\b", r"\bcombination\b"],
    }

    SYSTEM_DESIGN_TOPICS = {
        "rate limiter": [r"rate limit", r"token bucket", r"leaky bucket"],
        "caching": [r"\bcache\b", r"redis", r"memcached"],
        "queues/streams": [r"kafka", r"pubsub", r"pub/sub", r"queue", r"stream"],
        "db design": [r"schema", r"index", r"partition", r"shard", r"replica"],
        "storage/cdn": [r"\bcdn\b", r"object storage", r"\bs3\b", r"blob storage"],
        "auth": [r"oauth", r"authentication", r"authorization", r"jwt"],
        "observability": [r"logging", r"metrics", r"tracing", r"monitoring"],
    }

    BEHAVIORAL_THEMES = {
        "ownership": [r"ownership", r"end[- ]to[- ]end", r"\bowned\b"],
        "collaboration": [r"cross[- ]functional", r"collaborat", r"stakeholder"],
        "ambiguity": [r"ambiguous", r"unclear", r"no direction", r"figured out"],
        "conflict": [r"conflict", r"disagree", r"pushback"],
        "execution": [r"delivered", r"shipped", r"deadline", r"trade[- ]off"],
        "failure/learning": [r"failed", r"mistake", r"learned", r"postmortem"],
    }

    def _count_topics(self, text: str, topic_map: dict) -> Counter:
        t = (text or "").lower()
        counts = Counter()
        for topic, patterns in topic_map.items():
            for pat in patterns:
                if re.search(pat, t, flags=re.IGNORECASE):
                    counts[topic] += 1
        return counts

    def _combine_text_from_sources(self, answer: str, sources: List[Dict[str, str]]) -> str:
        parts = [answer or ""]
        for s in sources or []:
            parts.append(s.get("title", "") or "")
            parts.append(s.get("snippet", "") or "")
            parts.append(s.get("url", "") or "")
        return "\n".join(parts)

    def fetch_interview_question_themes(self, company: str, role: str) -> Dict[str, Any]:
        q_role = role.replace("/", " ")
        queries = [
            f'{company} {q_role} interview questions leetcode phone screen',
            f'{company} {q_role} technical interview questions data structures algorithms',
            f'{company} {q_role} system design interview questions',
            f'{company} {q_role} recruiter screen behavioral interview questions',
        ]

        all_sources: List[Dict[str, str]] = []
        all_text = ""

        for q in queries:
            resp = linkup_search(q)
            if isinstance(resp, dict):
                answer = resp.get("answer") or ""
            else:
                answer = getattr(resp, "answer", "") or ""

            sources = self.normalize_sources(resp)
            all_sources.extend(self.pick_top_sources(sources, max_sources=3))
            all_text += "\n" + self._combine_text_from_sources(answer, sources)

        coding = self._count_topics(all_text, self.CODING_TOPIC_MAP)
        sysd = self._count_topics(all_text, self.SYSTEM_DESIGN_TOPICS)
        beh = self._count_topics(all_text, self.BEHAVIORAL_THEMES)

        return {
            "queries": queries,
            "coding_topics": [t for t, _ in coding.most_common(8)],
            "system_design_topics": [t for t, _ in sysd.most_common(5)],
            "behavioral_themes": [t for t, _ in beh.most_common(5)],
            "top_links": all_sources[:5],
        }

    def build_7_day_prep_plan(self, themes: Dict[str, Any]) -> List[str]:
        coding = themes.get("coding_topics") or []
        sysd = themes.get("system_design_topics") or []
        beh = themes.get("behavioral_themes") or []

        c = (coding + ["arrays", "strings", "hashmap", "trees", "graphs", "dp"])[:6]
        s = (sysd + ["caching", "db design", "queues/streams"])[:3]
        b = (beh + ["ownership", "collaboration", "ambiguity"])[:3]

        return [
            f"Day 1: {c[0]} + {c[1]} (2 medium problems)",
            f"Day 2: {c[2]} + {c[3]} (2 medium problems)",
            f"Day 3: {c[4]} (2 medium) + review mistakes",
            f"Day 4: {c[5]} (2 medium) + 1 timed set (45–60 min)",
            f"Day 5: System Design — {s[0]} + {s[1]} (write 1 full design doc)",
            f"Day 6: System Design — {s[2]} + API + data model + scaling checklist",
            f"Day 7: Mock interview (coding + behavioral). Behavioral: {', '.join(b)}",
        ]

    # ---------------------------
    # Run Linkup research bundle (3 queries) + jobs + themes + plan
    # ---------------------------
    def run_research(self, company: str, role: str) -> Dict[str, Any]:
        queries = self.build_queries(company, role)
        results: List[Dict[str, Any]] = []

        for q in queries:
            resp = linkup_search(q)

            if isinstance(resp, dict):
                answer = resp.get("answer") or ""
            else:
                answer = getattr(resp, "answer", "") or ""

            sources = self.normalize_sources(resp)

            results.append(
                {
                    "query": q,
                    "answer_bullets": self.bullets_from_answer(answer, max_bullets=5),
                    "top_sources": self.pick_top_sources(sources, max_sources=3),
                }
            )

        recent_jobs = self.fetch_recent_job_postings(company, role, max_posts=5)
        themes = self.fetch_interview_question_themes(company, role)
        prep_plan = self.build_7_day_prep_plan(themes)

        return {
            "company": company,
            "role": role,
            "queries": queries,
            "results": results,
            "recent_jobs": recent_jobs,
            "themes": themes,
            "prep_plan": prep_plan,
        }

    # ---------------------------
    # Candidate brief (bullets + top links + jobs + themes + plan)
    # ---------------------------
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
            lines.append("- None found (try 'SWE' vs 'Software Engineer', or add location).")

        themes = bundle.get("themes") or {}
        prep_plan = bundle.get("prep_plan") or []

        lines.append("")
        lines.append("🧠 Interview themes (from public sources):")
        ct = themes.get("coding_topics") or []
        st = themes.get("system_design_topics") or []
        bt = themes.get("behavioral_themes") or []
        lines.append(f"- Coding topics: {', '.join(ct[:8]) if ct else '—'}")
        lines.append(f"- System design: {', '.join(st[:5]) if st else '—'}")
        lines.append(f"- Behavioral themes: {', '.join(bt[:5]) if bt else '—'}")

        lines.append("")
        lines.append("📅 7-day prep plan (auto-generated):")
        if prep_plan:
            for p in prep_plan:
                lines.append(f"- {p}")
        else:
            lines.append("- (No plan generated)")

        lines.append("")
        lines.append("🔗 Best interview links (read 2–3):")
        top_links = themes.get("top_links") or []
        if top_links:
            used = set()
            for s in top_links[:5]:
                url = s.get("url", "")
                if not url or url in used:
                    continue
                used.add(url)
                lines.append(f"- {s.get('title','Source')} — {url}")
        else:
            lines.append("- None found.")

        return "\n".join(lines)

    # ---------------------------
    # MODE 1: Job research pipeline
    # ---------------------------
    def process_job(self, company: str, role: str):
        print("\n" + "=" * 70)
        print("🎯 JOB APPLICATION PROCESSING")
        print("=" * 70)
        print(f"Company: {company}")
        print(f"Role: {role}\n")

        print("1️⃣  Running Linkup research (recent-focused + interview themes)...")
        bundle = self.run_research(company, role)
        print("   ✓ Research complete\n")

        print("2️⃣  Writing candidate brief (highlights + postings + themes + plan)...")
        brief = self.format_candidate_brief(bundle)

        safe_company = company.strip().replace(" ", "_")
        safe_role = role.strip().replace(" ", "_").replace("/", "_")
        doc_path = self.prep_docs_dir / f"prep_{safe_company}_{safe_role}.txt"
        doc_path.write_text(brief)
        print(f"   ✓ Created: {doc_path}\n")

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

        db = load_db()
        app = upsert_application(db, company, role)
        app["notes_file"] = str(doc_path)
        app["internal_contacts"] = known_people
        app["recent_job_postings"] = bundle.get("recent_jobs", [])
        app["themes"] = bundle.get("themes", {})
        app["prep_plan"] = bundle.get("prep_plan", [])

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
    # MODE 2: Inbox → Calendar (uses your parser + schedules only when start_iso exists)
    # ---------------------------
    def scan_inbox_and_push_interviews(self, max_emails: int = 50, dry_run: bool = False):
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
            '(assessment OR "online assessment" OR oa OR hackerrank OR codility OR karat OR codesignal OR hirevue)'
            ') '
            '-subject:(webinar OR digest OR newsletter OR shuttle OR rent OR alumni OR subscription OR cleaning OR loan OR netbanking OR downtime) '
            '-from:(no-reply OR noreply)'
        )

        emails = fetch_recent_messages(max_results=max_emails, query=gmail_query)
        print(f"Fetched {len(emails)} emails.\n")

        stage_counts: Dict[str, int] = {}
        action_needed = []
        calendar_ready = []

        db = load_db()
        created = 0

        for e in emails:
            parsed = parse_interview_details(e)
            if not parsed.get("is_interview"):
                continue

            stage = parsed.get("stage") or "Unclassified"
            company = parsed.get("company") or "Unknown"
            subject = (e.get("subject") or "").strip()

            stage_counts[stage] = stage_counts.get(stage, 0) + 1

            item = {
                "stage": stage,
                "company": company,
                "subject": subject,
                "start_iso": parsed.get("start_iso"),
                "meeting_link": parsed.get("meeting_link") or "",
                "message_id": e.get("message_id"),
                "from": e.get("from") or "",
                "snippet": e.get("snippet") or "",
            }

            if item["start_iso"]:
                calendar_ready.append(item)
            else:
                action_needed.append(item)

        # Print summary
        print("📊 INTERVIEW SUMMARY\n")
        for k in ["Assessment", "Phone Screen", "Technical Interview", "Onsite / Final", "Recruiter / Scheduling", "Unclassified"]:
            print(f"{k} ({stage_counts.get(k, 0)})")

        print("\n" + "=" * 70)

        print("\n🟡 Action needed / not scheduled yet (showing up to 12)")
        if action_needed:
            for it in action_needed[:12]:
                print(f"• [{it['stage']}] {it['company']}: {it['subject']}")
        else:
            print("• (none)")

        print("\n✅ Calendar-ready (can be scheduled) (showing up to 12)")
        if calendar_ready:
            for it in calendar_ready[:12]:
                print(f"• [{it['stage']}] {it['company']}: {it['subject']} — {it['start_iso']}")
        else:
            print("• (none)")

        # Create events
        if not dry_run and calendar_ready:
            for it in calendar_ready:
                mid = it.get("message_id")
                if has_scheduled_interview and mid and has_scheduled_interview(db, mid):
                    continue

                title = f"{it['stage']}: {it['company']} — {it['subject']}"
                description = (
                    f"From: {it.get('from','')}\n"
                    f"Company: {it.get('company','')}\n"
                    f"Stage: {it.get('stage','')}\n"
                    f"Subject: {it.get('subject','')}\n\n"
                    f"Snippet:\n{it.get('snippet','')}\n\n"
                    f"Meeting link:\n{it.get('meeting_link','')}\n"
                ).strip()

                try:
                    ev = create_event(
                        title=title,
                        start_iso=it["start_iso"],
                        duration_mins=60,
                        description=description,
                        location=it.get("meeting_link", ""),
                        calendar_id="primary",
                    )
                except Exception as ex:
                    print(f"\n⚠ Failed to create event for: {it['subject']} — {ex}")
                    continue

                app = upsert_application(db, it.get("company") or "Inbox", it.get("stage") or "Interview")
                app.setdefault("interviews", [])

                interview_obj = {
                    "message_id": mid,
                    "subject": it.get("subject"),
                    "start_iso": it.get("start_iso"),
                    "meeting_link": it.get("meeting_link"),
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

        return {"created": created, "summary": stage_counts}


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
