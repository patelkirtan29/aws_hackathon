from __future__ import annotations

"""
Job Intelligence Agent
Modes:
(1) Job Research  -> recent highlights + links + job postings + past questions (CSV + auto-fetch if enabled)
(2) Scan Inbox->Calendar -> keeps your existing email scan summary logic
"""

# This prevents UnicodeEncodeError when printing on Windows terminals.
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import urllib.parse
from datetime import datetime
from typing import Dict, Any, List, Tuple

from linkup_job import linkup_search
from gmail_reader import fetch_recent_messages
from interview_parser import parse_interview_details

try:
    from calendar_push import create_event
except Exception:
    create_event = None

from past_questions import get_past_questions


# -----------------------------
# Helpers
# -----------------------------

def _as_dict(res: Any) -> Dict[str, Any]:
    """
    Linkup SDK may return a dict OR a Pydantic-like model.
    Normalize to a plain dict so .get() works everywhere.
    """
    if res is None:
        return {}
    if isinstance(res, dict):
        return res

    # Pydantic v2
    if hasattr(res, "model_dump"):
        try:
            return res.model_dump()
        except Exception:
            pass

    # Pydantic v1
    if hasattr(res, "dict"):
        try:
            return res.dict()
        except Exception:
            pass

    # last resort: attribute copy
    out: Dict[str, Any] = {}
    for k in ("answer", "sources", "query_used", "error", "message"):
        if hasattr(res, k):
            out[k] = getattr(res, k)
    return out


def fetch_recent_emails(days: int = 30, max_results: int = 50) -> List[Dict[str, Any]]:
    """
    Wrapper over gmail_reader.fetch_recent_messages() to match the old signature.
    Uses Gmail query newer_than:Xd to reduce scanning.
    """
    query = f"newer_than:{days}d"
    return fetch_recent_messages(max_results=max_results, query=query)


# =========================================================
# Job Intelligence Agent
# =========================================================

class JobIntelligenceAgent:
    # =====================================================
    # =============== JOB RESEARCH MODE ===================
    # =====================================================

    def process_job(self, company: str, role: str) -> str:
        print("\n" + "=" * 70)
        print("🎯 JOB APPLICATION PROCESSING")
        print("=" * 70)
        print(f"Company: {company}")
        print(f"Role: {role}\n")

        print("1️⃣  Running Linkup research (recent-focused)...")
        bundle = self.build_research_bundle(company, role)
        print("   ✓ Research complete\n")

        print("2️⃣  Writing candidate brief (highlights + links + jobs + past questions)...")
        brief = self.format_candidate_brief(bundle)

        print("\n" + brief)

        # Save to file
        safe_company = company.replace(" ", "_")
        safe_role = role.replace(" ", "_")
        filename = f"prep_{safe_company}_{safe_role}.txt"

        with open(filename, "w", encoding="utf-8") as f:
            f.write(brief)

        print(f"\n💾 Saved brief to: {filename}")

        print("\n" + "=" * 70)
        print("JOB RESEARCH COMPLETE")
        print("=" * 70)

        return filename

    def build_research_bundle(self, company: str, role: str) -> Dict[str, Any]:
        queries = [
            f"{company} latest news last 30 days",
            f"{company} {role} interview experience",
            f"{company} {role} hiring update 2026",
        ]

        results: List[Dict[str, Any]] = []
        for q in queries:
            raw = linkup_search(q)               # your normalized output from linkup_job.py
            res = _as_dict(raw)
            results.append({
                "query": q,
                "answer_bullets": self.extract_bullets(res),
                "top_sources": (res.get("sources") or [])[:3],
            })

        job_search = _as_dict(linkup_search(f"{company} {role} job posting last 7 days"))
        recent_jobs = (job_search.get("sources") or [])[:5]

        return {
            "company": company,
            "role": role,
            "results": results,
            "recent_jobs": recent_jobs,
        }

    def extract_bullets(self, res: Any) -> List[str]:
        res = _as_dict(res)
        text = (res.get("answer") or "").strip()

        lines: List[str] = []
        for l in text.split("\n"):
            s = l.strip().lstrip("-•").strip()
            if len(s) >= 25:
                lines.append(s)
        return lines[:6]

    # -----------------------------------------------------
    # Interview themes + plans
    # -----------------------------------------------------

    def public_interview_themes(self) -> Dict[str, List[str]]:
        return {
            "coding_topics": ["dp", "arrays", "strings", "hashmap", "stack/queue", "binary search", "trees", "graphs"],
            "system_design": ["queues/streams", "auth"],
            "behavioral": ["collaboration", "execution", "ownership"],
        }

    def prep_plan_7_day(self) -> List[str]:
        return [
            "Day 1: dp + arrays (2 medium problems)",
            "Day 2: strings + hashmap (2 medium problems)",
            "Day 3: stack/queue (2 medium) + review mistakes",
            "Day 4: binary search (2 medium) + 1 timed set (45–60 min)",
            "Day 5: System Design — queues/streams + auth (write 1 full design doc)",
            "Day 6: System Design — caching + API + data model + scaling checklist",
            "Day 7: Mock interview (coding + behavioral). Behavioral: collaboration, execution, ownership",
        ]

    def best_interview_links(self, company: str, role: str) -> List[str]:
        query = urllib.parse.quote_plus(f"{company} {role}")
        return [
            f"LeetCode Discuss — https://leetcode.com/discuss/?query={query}",
            f"GeeksforGeeks — https://www.google.com/search?q=site:geeksforgeeks.org+{query}+interview+questions",
            "System Design Primer (GitHub) — https://github.com/donnemartin/system-design-primer",
        ]

    def build_30_day_study_plan(self, role: str) -> List[str]:
        r = (role or "").lower()

        if "ai" in r or "ml" in r:
            return [
                "Week 1: Linear Algebra + Probability + ML fundamentals",
                "Week 2: Supervised learning + Feature engineering + Model evaluation",
                "Week 3: Deep Learning (CNN/RNN/Transformers) + PyTorch practice",
                "Week 4: ML System Design (serving, scaling, monitoring) + 3 mock interviews",
            ]

        if "backend" in r:
            return [
                "Week 1: Arrays, Strings, Hashmaps (15 problems)",
                "Week 2: Trees, Graphs, DP (15 problems)",
                "Week 3: Backend fundamentals (REST, DB indexing, caching, auth)",
                "Week 4: Distributed system design + 3 mock interviews",
            ]

        if "frontend" in r:
            return [
                "Week 1: JavaScript fundamentals + closures + async",
                "Week 2: React internals + state management + performance",
                "Week 3: Frontend system design (SSR, caching, APIs)",
                "Week 4: Build 1 production project + 3 mock interviews",
            ]

        if "data" in r:
            return [
                "Week 1: SQL advanced (joins, window functions)",
                "Week 2: Statistics + probability + A/B testing",
                "Week 3: Python data pipelines (pandas, numpy)",
                "Week 4: Case studies + ML basics + mocks",
            ]

        return [
            "Week 1: Arrays, Strings, Hashmaps (15 problems)",
            "Week 2: Trees, Graphs, DP (15 problems)",
            "Week 3: System Design fundamentals + caching + scaling",
            "Week 4: Timed mocks (coding + behavioral)",
        ]

    # -----------------------------------------------------
    # Candidate brief formatting
    # -----------------------------------------------------

    def format_candidate_brief(self, bundle: Dict[str, Any]) -> str:
        company = bundle["company"]
        role = bundle["role"]

        merged_bullets: List[str] = []
        all_sources: List[Dict[str, str]] = []
        for r in bundle["results"]:
            merged_bullets.extend(r.get("answer_bullets") or [])
            all_sources.extend(r.get("top_sources") or [])

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
            url = (s.get("url") or "").strip()
            if not url or url in used:
                continue
            used.add(url)
            final_links.append(s)
            if len(final_links) >= 3:
                break

        # Past questions — never crash if CSV is messy
        try:
            past_qs = get_past_questions(
                company,
                role,
                csv_path="past_questions.csv",
                limit=8,
                auto_fetch_if_missing=True,
            )
            past_qs_error = ""
        except Exception as e:
            past_qs = []
            past_qs_error = str(e)

        themes = self.public_interview_themes()
        plan_7 = self.prep_plan_7_day()
        plan_30 = self.build_30_day_study_plan(role)
        best_links = self.best_interview_links(company, role)

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
            # Always provide clickable links even when LinkUp sources are empty
            q = urllib.parse.quote_plus(f"{company} {role}")
            fallback_links = [
                ("Google News", f"https://www.google.com/search?q={urllib.parse.quote_plus(company)}+latest+news&tbm=nws"),
                ("LinkedIn Jobs", f"https://www.linkedin.com/jobs/search/?keywords={q}"),
                ("Indeed", f"https://www.indeed.com/jobs?q={q}"),
            ]
            for title, url in fallback_links:
                lines.append(f"- {title} — {url}")

        lines.append("")
        lines.append("🧑‍💻 Recent job postings (last 7 days bias; max 5):")
        recent_jobs = bundle.get("recent_jobs") or []
        if recent_jobs:
            for j in recent_jobs[:5]:
                lines.append(f"- {j.get('title','Job posting')} — {j.get('url','')}")
        else:
            lines.append("- None found (try role synonyms like 'SWE' / 'Software Engineer').")

        lines.append("")
        lines.append("🧠 Past interview questions (from your CSV; auto-fetched if missing):")
        if past_qs:
            for row in past_qs:
                stage = row.get("stage", "Mixed")
                topic = row.get("topic", "General")
                diff = row.get("difficulty", "Unknown")
                q = (row.get("question") or "").strip()
                src = (row.get("source") or "").strip()
                lines.append(f"- [{stage}] {topic} ({diff}): {q} — {src}")
        else:
            lines.append("- No questions found.")
            if past_qs_error:
                lines.append(f"  (debug: past_questions error: {past_qs_error})")

        lines.append("")
        lines.append("🧠 Interview themes (from public sources):")
        lines.append(f"• Coding topics: {', '.join(themes['coding_topics'])}")
        lines.append(f"• System design: {', '.join(themes['system_design'])}")
        lines.append(f"• Behavioral themes: {', '.join(themes['behavioral'])}")

        lines.append("")
        lines.append("📅 7-day prep plan (auto-generated):")
        for d in plan_7:
            lines.append(f"• {d}")

        lines.append("")
        lines.append("📅 30-day study plan (role-specific):")
        for w in plan_30:
            lines.append(f"• {w}")

        lines.append("")
        lines.append("🔗 Best interview links (read 2–3):")
        for l in best_links[:4]:
            lines.append(f"• {l}")

        return "\n".join(lines)

    # =====================================================
    # ============== EMAIL SCAN MODE ======================
    # =====================================================

    def scan_inbox_and_push_interviews(self, max_emails: int = 50, dry_run: bool = True):
        print("\n" + "=" * 70)
        print("📩 INBOX SCAN → SUMMARY (Interview / Assessment)")
        print("=" * 70)

        emails = fetch_recent_emails(days=30, max_results=max_emails)
        print(f"Fetched {len(emails)} emails.\n")

        summary = {
            "Assessment": [],
            "Phone Screen": [],
            "Technical Interview": [],
            "Onsite / Final": [],
            "Recruiter / Scheduling": [],
            "Unclassified": [],
        }

        calendar_ready: List[Tuple[str, str]] = []
        created = 0

        for e in emails:
            parsed = parse_interview_details(e)
            if not parsed.get("is_interview"):
                continue

            stage = parsed.get("stage") or "Unclassified"
            company = parsed.get("company") or "Unknown"
            subject = e.get("subject") or ""
            entry = f"{company}: {subject}"

            summary.setdefault(stage, []).append(entry)

            start_iso = parsed.get("start_iso")
            if start_iso:
                calendar_ready.append((entry, start_iso))

                if (not dry_run) and create_event:
                    try:
                        create_event(
                            title=f"{company} — {stage}",
                            start_iso=start_iso,
                            description=subject,
                            meeting_link=parsed.get("meeting_link") or "",
                        )
                        created += 1
                    except Exception:
                        pass

        print("📊 INTERVIEW SUMMARY\n")
        for k in ["Assessment", "Phone Screen", "Technical Interview", "Onsite / Final", "Recruiter / Scheduling", "Unclassified"]:
            v = summary.get(k, [])
            print(f"{k} ({len(v)})")

        print("\n" + "=" * 70)
        print("\n🟡 Action needed / not scheduled yet (showing up to 12)")
        shown = 0
        for k in ["Assessment", "Phone Screen", "Technical Interview", "Onsite / Final", "Recruiter / Scheduling", "Unclassified"]:
            for item in summary.get(k, [])[:12]:
                if shown >= 12:
                    break
                print(f"• [{k}] {item}")
                shown += 1

        print("\n✅ Calendar-ready (can be scheduled) (showing up to 12)")
        if calendar_ready:
            for entry, t in calendar_ready[:12]:
                print(f"• {entry} — {t}")
        else:
            print("• (none)")

        print("\n" + "=" * 70)
        print(f"Calendar events created: {created} (dry_run={dry_run})")
        print("=" * 70)


if __name__ == "__main__":
    agent = JobIntelligenceAgent()

    while True:
        mode = input("\nChoose mode: (1) Job Research  (2) Scan Inbox->Calendar  (exit): ").strip().lower()

        if mode in ("exit", "q", "quit"):
            print("Bye 👋")
            break

        if mode == "2":
            dry = input("Dry run? (y/n): ").strip().lower() == "y"
            agent.scan_inbox_and_push_interviews(dry_run=dry)
            continue

        if mode == "1":
            company = input("Company: ").strip()
            role = input("Role: ").strip()
            agent.process_job(company, role)
            continue

        print("Invalid option. Type 1, 2, or exit.")
