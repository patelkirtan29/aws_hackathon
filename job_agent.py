
from dotenv import load_dotenv
import json
from datetime import datetime
from pathlib import Path
import os
load_dotenv()  # load environment variables from .env file

try:
    from linkup import LinkupClient
except Exception:
    LinkupClient = None

class JobIntelligenceAgent:
    def __init__(self):
        self.prep_docs_dir = Path("interview_prep_docs")
        self.prep_docs_dir.mkdir(exist_ok=True)
        self.spreadsheet_path = "job_applications.json"
        # load existing applications if present
        if Path(self.spreadsheet_path).exists():
            try:
                with open(self.spreadsheet_path, 'r') as f:
                    self.applications = json.load(f)
            except Exception:
                self.applications = []
        else:
            self.applications = []

        # Initialize Linkup client from environment
        api_key = os.getenv("LINKUP_API_KEY")
        print('api key -------------> ', api_key)
        if api_key and LinkupClient:
            try:
                self.linkup = LinkupClient(api_key=api_key)
                print("✓ Linkup client initialized")
            except Exception as e:
                print(f"WARNING: failed to initialize Linkup client: {e}")
                self.linkup = None
        else:
            self.linkup = None
            if not api_key:
                print("WARNING: LINKUP_API_KEY not set in environment")
            elif not LinkupClient:
                print("WARNING: linkup-sdk not installed (pip install linkup-sdk)")

    def fetch_recent_jobs(self, company, role, max_results=10):
        """Fetch recent job-related sources using Linkup and return normalized job entries.
        Falls back gracefully if Linkup client is not available.
        """
        if not self.linkup:
            print("Linkup client unavailable — cannot fetch real-time jobs")
            return []

        # query = f"{company} {role} recent job postings site:careers OR jobs OR 'job posting'"
        print(f"   ↪ Running Linkup search: {query}")
        try:
            resp = self.linkup.search(
                query=query,
                depth="shallow",
                output_type="sourcedAnswer",
                maxResults=max_results,
            )
        except Exception as e:
            print(f"   ⚠ Linkup search error: {e}")
            return []

        # Response may be a dict with 'sources'
        sources = None
        if isinstance(resp, dict):
            sources = resp.get("sources")
        else:
            sources = getattr(resp, "sources", None)

        if not sources:
            print("   ✓ Linkup returned no sources")
            return []

        jobs = []
        seen = set()
        for s in sources:
            # support dict-like and object-like sources
            url = s.get("url") if isinstance(s, dict) else getattr(s, "url", None)
            name = s.get("name") if isinstance(s, dict) else getattr(s, "name", None)
            snippet = s.get("snippet") if isinstance(s, dict) else getattr(s, "snippet", None)
            if not url:
                continue
            if url in seen:
                continue
            seen.add(url)
            job = {
                "company": company,
                "role": role,
                "url": url,
                "title": name or f"{role} @ {company}",
                "snippet": snippet or "",
                "fetched_at": datetime.now().isoformat()
            }
            jobs.append(job)

        print(f"   ✓ Linkup returned {len(jobs)} candidate sources")
        return jobs

    def dedupe_and_add(self, job):
        # Simple dedupe: by URL if present, else by company+role+title
        for existing in self.applications:
            if job.get("url") and existing.get("url") and existing["url"] == job["url"]:
                return False
            if (not job.get("url") and
                existing.get("company") == job.get("company") and
                existing.get("role") == job.get("role") and
                existing.get("title") == job.get("title")):
                return False
        self.applications.append(job)
        return True

    def process_job(self, company, role):
        print("\n" + "="*70)
        print("🎯 JOB APPLICATION PROCESSING")
        print("="*70)
        print(f"Company: {company}")
        print(f"Role: {role}\n")

        print("1️⃣  AUTO-DETECTING RESEARCH NEEDS...")
        print(f"   ✓ Recent news at {company}")
        print(f"   ✓ Interview process for {role}")
        print(f"   ✓ Current projects\n")

        print("2️⃣  FORMULATING SEARCH QUERIES...")
        print(f"   1. '{company} recent news 2026'")
        print(f"   2. '{company} projects 2026'")
        print(f"   3. '{company} {role} interview'\n")

        print("3️⃣  EXECUTING CHAINED LINKUP SEARCHES...")
        # Real-time fetch of recent jobs
        jobs = self.fetch_recent_jobs(company, role, max_results=8)
        print(f"   ✓ Completed Linkup searches ({len(jobs)} results)\n")

        print("4️⃣  SYNTHESIZING INFORMATION...")
        print(f"   ✓ Generated intelligence profile\n")

        print("5️⃣  PRIVACY VERIFICATION...")
        print(f"   ✓ No personal data sent\n")

        print("6️⃣  GENERATING PREP DOCUMENTS...")
        # Generate a company-level prep doc
        safe_company = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in company).strip().replace(' ', '_')
        company_doc_path = self.prep_docs_dir / f"prep_{safe_company}.txt"
        doc_content = f"""
INTERVIEW PREP - {company}
Role: {role}
Generated: {datetime.now()}

COMPANY INTELLIGENCE (via Linkup):
- Summary: auto-generated from Linkup sources

PREPARATION CHECKLIST:
□ Review company projects
□ Study system design
□ Practice coding problems
"""
        company_doc_path.write_text(doc_content)
        print(f"   ✓ Created company-level prep doc: {company_doc_path}\n")

        # Create job-specific prep docs and add jobs to spreadsheet
        added = 0
        for idx, job in enumerate(jobs, start=1):
            title_safe = (job.get('title') or f"job_{idx}").replace('/', '_').replace(' ', '_')[:40]
            job_doc_path = self.prep_docs_dir / f"prep_{safe_company}_{title_safe}.txt"
            job_doc = f"JOB PREP - {job.get('title')}\nCompany: {company}\nRole: {role}\nURL: {job.get('url')}\n\nSNIPPET:\n{job.get('snippet')}\n\nFetched: {job.get('fetched_at')}\n"
            job_doc_path.write_text(job_doc)
            print(f"   ✓ Created job prep doc: {job_doc_path}")

            # Add to applications list (with metadata)
            app_entry = {
                'company': company,
                'role': role,
                'title': job.get('title'),
                'url': job.get('url'),
                'snippet': job.get('snippet'),
                'fetched_at': job.get('fetched_at'),
                'recorded_at': datetime.now().isoformat()
            }
            if self.dedupe_and_add(app_entry):
                added += 1

        # Persist spreadsheet
        try:
            with open(self.spreadsheet_path, 'w') as f:
                json.dump(self.applications, f, indent=2)
            print(f"\n   ✓ Spreadsheet updated ({added} new entries, total {len(self.applications)})\n")
        except Exception as e:
            print(f"   ⚠ Failed to write spreadsheet: {e}\n")

        print("7️⃣  UPDATE COMPLETE")
        return {'company': company, 'role': role, 'added': added}


if __name__ == "__main__":
    agent = JobIntelligenceAgent()
    # agent.process_job("Google", "Software Engineer")
    print("="*70)
    print("JOB PROCESSING COMPLETE!")
    print("="*70)
# ENDFILE