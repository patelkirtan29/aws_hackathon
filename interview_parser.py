# interview_parser.py
import re
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

# ----------------------------
# Strong negatives (kill false positives)
# ----------------------------
HARD_NEGATIVE_KEYWORDS = [
    "loan", "amortization", "emi", "netbanking", "downtime", "valued customer",
    "chase auto", "budget", "credit card", "statement", "subscription",
    "newsletter", "digest", "webinar", "cleaning", "alumni", "shuttle",
    "lane closure", "community notice", "workshop", "wargame"
]

# ----------------------------
# Recruiting anchors (must-have signals)
# ----------------------------
ATS_DOMAINS = [
    "greenhouse.io", "lever.co", "icims.com", "smartrecruiters.com",
    "myworkdayjobs.com", "successfactors", "taleo.net",
    # workday variants
    "workday.com", "workdayjobs.com"
]

ASSESSMENT_PROVIDERS = [
    "hackerrank", "codility", "karat", "codesignal", "testgorilla",
    "mettl", "hirevue", "pymetrics"
]

RECRUITING_STRONG = [
    "application", "candidate", "position", "role", "job", "job posting",
    "interview", "phone screen", "technical screen", "hiring manager", "recruiter",
    "talent acquisition", "next steps", "assessment", "online assessment", "oa"
]

SCHEDULING_WORDS = [
    "availability", "schedule", "scheduling", "reschedule",
    "calendar invite", "invite", "invitation", "confirm"
]

ROLE_WORDS = [
    "engineer", "developer", "intern", "analyst", "software", "frontend",
    "backend", "full stack", "data", "ml", "ai"
]

STAGE_RULES = [
    ("Assessment", ["assessment", "online assessment", "oa"] + ASSESSMENT_PROVIDERS + ["take-home", "take home", "assignment"]),
    ("Phone Screen", ["phone screen", "recruiter call", "hr call", "screening call"]),
    ("Technical Interview", ["technical interview", "technical screen", "coding interview", "live coding", "pair programming"]),
    ("Onsite / Final", ["onsite", "on-site", "final round", "loop interview", "panel interview", "super day"]),
    ("Recruiter / Scheduling", SCHEDULING_WORDS),
]

MEETING_LINK_PATTERNS = [
    r"https?://meet\.google\.com/[a-z\-]+",
    r"https?://[a-z0-9.-]*zoom\.us/j/\d+",
    r"https?://teams\.microsoft\.com/l/meetup-join/[^\s]+",
    r"https?://[a-z0-9.-]*webex\.com/[^\s]+",
]

MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12
}

# ----------------------------
# helpers
# ----------------------------
def _from_domain(email_from: str) -> str:
    m = re.search(r"@([A-Za-z0-9\.-]+\.[A-Za-z]{2,})", email_from or "")
    return (m.group(1).lower() if m else "")

def _looks_like_job_process(email_from: str, text: str) -> bool:
    dom = _from_domain(email_from)
    t = (text or "").lower()

    # ATS email domains
    if any(d in dom for d in ATS_DOMAINS):
        return True

    # assessment providers
    if any(p in dom for p in ASSESSMENT_PROVIDERS) or any(p in t for p in ASSESSMENT_PROVIDERS):
        return True

    return False

def _build_text(email: Dict[str, Any]) -> str:
    subject = (email.get("subject") or "").strip()
    snippet = (email.get("snippet") or "").strip()
    body = (email.get("body") or "").strip()
    email_from = (email.get("from") or "").strip()
    return f"FROM:\n{email_from}\nSUBJECT:\n{subject}\nSNIPPET:\n{snippet}\nBODY:\n{body}"

def classify_stage(text: str) -> str:
    t = text.lower()
    for stage, keys in STAGE_RULES:
        if any(k in t for k in keys):
            return stage
    return "Unclassified"

def _find_meeting_link(text: str) -> str:
    for pat in MEETING_LINK_PATTERNS:
        m = re.search(pat, text, flags=re.IGNORECASE)
        if m:
            return m.group(0)
    return ""

def _parse_datetime(text: str) -> Optional[str]:
    now = datetime.now()
    t = text.lower()

    # Feb 10 3:00 PM
    m = re.search(
        r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+(\d{1,2})\b.*?\b(\d{1,2}):(\d{2})\s*(am|pm)\b",
        t, flags=re.IGNORECASE | re.DOTALL
    )
    if m:
        mon = m.group(1).lower()[:4]
        day = int(m.group(2))
        hh = int(m.group(3))
        mm = int(m.group(4))
        ampm = m.group(5).upper()

        month = MONTH_MAP.get(mon[:3])
        if not month:
            return None

        if ampm == "PM" and hh != 12:
            hh += 12
        if ampm == "AM" and hh == 12:
            hh = 0

        try:
            dt = datetime(now.year, month, day, hh, mm)
        except ValueError:
            return None

        if dt < now - timedelta(days=180):
            return None
        return dt.isoformat()

    # 02/10 3:00 PM (MM/DD)
    m = re.search(
        r"\b(\d{1,2})/(\d{1,2})\b.*?\b(\d{1,2}):(\d{2})\s*(am|pm)\b",
        t, flags=re.IGNORECASE | re.DOTALL
    )
    if m:
        month = int(m.group(1))
        day = int(m.group(2))
        hh = int(m.group(3))
        mm = int(m.group(4))
        ampm = m.group(5).upper()

        if ampm == "PM" and hh != 12:
            hh += 12
        if ampm == "AM" and hh == 12:
            hh = 0

        try:
            dt = datetime(now.year, month, day, hh, mm)
        except ValueError:
            return None

        if dt < now - timedelta(days=180):
            return None
        return dt.isoformat()

    return None

def extract_company(email: Dict[str, Any]) -> str:
    subject = (email.get("subject") or "")
    sender = (email.get("from") or "")
    dom = _from_domain(sender)
    text = f"{subject} {sender}".lower()

    domain_map = {
        "amazon.com": "Amazon",
        "amazon.jobs": "Amazon",
        "google.com": "Google",
        "xwf.google.com": "Google",
        "microsoft.com": "Microsoft",
        "meta.com": "Meta",
        "apple.com": "Apple",
        "tcs.com": "TCS",
    }
    for k, v in domain_map.items():
        if k in dom:
            return v

    # "X is hiring"
    m = re.search(r"\b([A-Z][A-Za-z0-9&\.\- ]{2,})\s+is\s+hiring\b", subject)
    if m:
        cand = m.group(1).strip()
        if len(cand) <= 35:
            return cand

    for c in ["Amazon", "Google", "Microsoft", "Meta", "Apple", "Tesla", "Cisco", "TCS"]:
        if c.lower() in text:
            return c

    return "Unknown"

def extract_due_date_hint(text: str) -> str:
    t = text.lower()

    m = re.search(r"\bdue\s+in\s+(\d+)\s+day", t)
    if m:
        return f"due in {m.group(1)} days"

    m = re.search(r"\bdue\s+(by|on)\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+(\d{1,2})\b", t)
    if m:
        return f"due {m.group(2).title()} {m.group(3)}"

    m = re.search(r"\bdeadline[:\s]+(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+(\d{1,2})\b", t)
    if m:
        return f"due {m.group(1).title()} {m.group(2)}"

    return ""

def _confidence_score(text: str, email_from: str) -> int:
    t = text.lower()
    dom = _from_domain(email_from)

    # hard negatives kill it immediately
    if any(k in t for k in HARD_NEGATIVE_KEYWORDS):
        return -999

    score = 0

    # ATS domains
    if any(d in dom for d in ATS_DOMAINS) or any(d in t for d in ATS_DOMAINS):
        score += 4

    # assessment providers
    if any(p in dom for p in ASSESSMENT_PROVIDERS) or any(p in t for p in ASSESSMENT_PROVIDERS):
        score += 4

    # strong recruiting phrases (count lightly)
    score += sum(1 for k in RECRUITING_STRONG if k in t) // 2

    # role words help avoid random “schedule”
    if any(r in t for r in ROLE_WORDS):
        score += 1

    # meeting links or time are strong
    if _find_meeting_link(text):
        score += 3
    if _parse_datetime(text):
        score += 3

    return score

def parse_interview_details(email: Dict[str, Any]) -> Dict[str, Any]:
    email_from = (email.get("from") or "").strip()
    text = _build_text(email)

    score = _confidence_score(text, email_from)
    if score < 2:
        return {"is_interview": False}

    meeting_link = _find_meeting_link(text)
    start_iso = _parse_datetime(text)
    stage = classify_stage(text)
    company = extract_company(email)
    due_hint = extract_due_date_hint(text)

    # ✅ HARD GATE: if company is Unknown, only keep it if it's ATS/provider-based
    if company == "Unknown" and not _looks_like_job_process(email_from, text):
        return {"is_interview": False}

    return {
        "is_interview": True,
        "stage": stage,
        "company": company,
        "due_hint": due_hint,
        "start_iso": start_iso,
        "meeting_link": meeting_link,
        "score": score,
    }

