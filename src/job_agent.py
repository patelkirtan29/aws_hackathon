
from dotenv import load_dotenv
import json
from datetime import datetime
from pathlib import Path
import os
load_dotenv()

try:
    from linkup import LinkupClient
except Exception:
    LinkupClient = None

class JobIntelligenceAgent:
    def __init__(self):
        api_key = os.getenv("LINKUP_API_KEY")

        if api_key and LinkupClient:
            try:
                self.linkup = LinkupClient(api_key=api_key)
                print("✓ Linkup client initialized")
            except Exception as e:
                print(f"WARNING: failed to initialize Linkup client: {e}")
                self.linkup = None
        else:
            self.linkup = None

        self.storage_path = Path("output/jobs.txt")
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.applications = []
        self._load_jobs()

    def _load_jobs(self):
        if not self.storage_path.exists():
            return
        with open(self.storage_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    self.applications.append(json.loads(line.strip()))
                except:
                    pass

    def _save_job(self, job):
        with open(self.storage_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(job) + "\n")

    def fetch_recent_jobs(self, company, role, max_results=10):
        """Fetch recent job-related sources using Linkup and return normalized job entries.
        Falls back gracefully if Linkup client is not available.
        """
        if not self.linkup:
            print("Linkup client unavailable — cannot fetch real-time jobs")
            return []
        
        query = f"{company} {role} recent job postings"
        print(f"   ↪ Running Linkup search: {query}")
        try:
            resp = self.linkup.search(
                query=query,
                depth="deep",
                output_type="sourcedAnswer",
                max_results=max_results
            )
        except Exception as e:
            print(f"   ⚠ Linkup search error: {e}")
            return []

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
        for existing in self.applications:
            if job.get("url") and existing.get("url") and existing["url"] == job["url"]:
                return False
            if (not job.get("url") and
                existing.get("company") == job.get("company") and
                existing.get("role") == job.get("role") and
                existing.get("title") == job.get("title")):
                return False

        self.applications.append(job)
        self._save_job(job)
        return True