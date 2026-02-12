# linkedin_referrals.py
import re
from urllib.parse import urlparse
from linkup_job import linkup_search

LINKEDIN_PROFILE_PATTERNS = [
    r"https?://(?:www\.)?linkedin\.com/in/[^\s\)\]]+",
    r"https?://(?:www\.)?linkedin\.com/pub/[^\s\)\]]+",
]

def _extract_linkedin_urls(text: str):
    urls = []
    for pat in LINKEDIN_PROFILE_PATTERNS:
        urls.extend(re.findall(pat, text))
    return list(dict.fromkeys(urls))

def _normalize(url: str) -> str:
    try:
        u = urlparse(url)
        return f"{u.scheme}://{u.netloc}{u.path}".rstrip("/")
    except Exception:
        return url

def _shorten(text: str, n: int = 160) -> str:
    if not text:
        return ""
    t = " ".join(text.split())  # collapse whitespace
    if len(t) <= n:
        return t
    return t[:n].rsplit(" ", 1)[0].rstrip() + "..."

def _collect_candidates(sources):
    people = []
    seen = set()

    for s in sources:
        title = (s.get("title", "") or "").strip()
        snippet = (s.get("snippet", "") or "").strip()
        url = (s.get("url", "") or "").strip()

        blob = f"{title}\n{snippet}\n{url}"
        for li in _extract_linkedin_urls(blob):
            li = _normalize(li)
            if li in seen:
                continue
            seen.add(li)

            # Candidate-friendly "reason"
            reason = title
            if "recruit" in snippet.lower() or "talent" in snippet.lower():
                reason = "Recruiter / Talent"
            elif "software engineer" in (title + " " + snippet).lower():
                reason = "Software Engineer at company"

            people.append({
                "name": title or "LinkedIn profile",
                "linkedin_url": li,
                "reason": reason,
                "context": _shorten(snippet, 180),   # ✅ short context only
            })

    return people



def find_referrals(company: str, role: str, max_people: int = 8):
    queries = [
    f'site:linkedin.com/in "{company}" recruiter OR "talent acquisition" OR sourcer',
    f'site:linkedin.com/in "{company}" "{role}"',
    f'site:linkedin.com/in "{company}" "engineering manager" "{role}"',
]


    all_sources = []
    for q in queries:
        resp = linkup_search(q)

        # Case 1: our wrapper returned a dict fallback
        if isinstance(resp, dict):
            srcs = resp.get("sources", []) or []
            # Ensure dict format
            for s in srcs:
                if isinstance(s, dict):
                    all_sources.append({
                        "title": s.get("name") or s.get("title") or "Source",
                        "url": s.get("url") or "",
                        "snippet": s.get("snippet") or "",
                    })
            continue

        # Case 2: real Linkup object (pydantic model)
        srcs = getattr(resp, "sources", None) or []
        for s in srcs:
            all_sources.append({
                "title": getattr(s, "name", None) or getattr(s, "title", None) or "Source",
                "url": getattr(s, "url", "") or "",
                "snippet": getattr(s, "snippet", "") or "",
            })

    candidates = _collect_candidates(all_sources)
    return candidates[:max_people]

