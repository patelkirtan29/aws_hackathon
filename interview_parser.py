# interview_parser.py
import re
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

# ----------------------------
# Noise filters
# ----------------------------
NEGATIVE_SUBJECT_KEYWORDS = [
    "webinar", "digest", "newsletter", "shuttle", "tracking", "rent", "alumni",
    "subscription", "cleaning", "consultation", "appointment only",
    "skills employers", "live now", "community notice", "lane closure"
]

NEGATIVE_FROM_KEYWORDS = [
    "amenify", "apartment", "leasing", "community", "lane", "shuttle", "alumni",
    "subscription", "cleaning", "donotreply", "no-reply", "noreply"
]

# ----------------------------
# Recruiting & stage cues
# ----------------------------
RECRUITING_CUES = [
    "interview", "phone screen", "screening", "technical", "coding interview",
    "hiring", "hiring manager", "recruiter", "talent acquisition", "talent",
    "next steps", "application", "candidate", "selection process",
    "assessment", "online assessment", "oa", "take home", "take-home",
    "hackerrank", "codility", "karat", "testgorilla", "hirevue"
]

ROLE_WORDS = [
    "engineer", "developer", "intern", "analyst", "manager", "designer",
    "software", "frontend", "backend", "full stack", "data", "ml", "ai"
]

STAGE_RULES = [
    ("Assessment", [
        "assessment", "online assessment", "oa", "coding test", "online test",
        "hackerrank", "hacker rank", "codility", "karat", "testgorilla", "hirevue",
        "take-home", "take home", "assignment"
    ]),
    ("Phone Screen", [
        "phone screen", "phone screening", "recruiter call", "hr call",
        "initial call", "intro call", "screening call"
    ]),
    ("Technical Interview", [
        "technical interview", "technical screen", "coding interview",
        "engineer interview", "pair programming", "live coding", "dsa round"
    ]),
    ("Onsite / Final", [
        "onsite", "on-site", "final round", "loop interview", "panel interview",
        "virtual onsite", "super day"
    ]),
    ("Recruiter / Scheduling", [
        "availability", "schedule", "scheduling", "reschedule", "calendar",
        "invite", "invitation", "confirm your time", "confirming", "time works"
    ]),
]

SCHEDULING_CUES = [
    "availability", "schedule", "scheduling", "reschedule", "calendar invite",
    "calendar", "invite", "invitation", "confirm", "time works"
]

# Meeting links
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

def _build_text(email: Dict[str, Any]) -> str:
    subject = (email.get("subject") or "").strip()
    snippet = (email.get("snippet") or "").strip()
    body = (email.get("body") or "").strip()
    return f"{subject}\n{snippet}\n{body}"

def _is_noise(email_from: str, subject: str) -> bool:
    s = (subject or "").lower()
    f = (email_from or "").lower()
    if any(k in s for k in NEGATIVE_SUBJECT_KEYWORDS):
        return True
    if any(k in f for k in NEGATIVE_FROM_KEYWORDS):
        return True
    return False

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

def _has_recruiting_intent(text: str) -> bool:
    t = text.lower()
    has_rec = any(k in t for k in RECRUITING_CUES)
    has_sched = any(k in t for k in SCHEDULING_CUES)
    has_role = any(k in t for k in ROLE_WORDS)
    # must be recruiting OR (scheduling + role) to avoid “community notice schedule” type mail
    return has_rec or (has_sched and has_role)

def _parse_datetime(text: str) -> Optional[str]:
    """
    Safe/rough datetime parse:
    - If we find a day+month+time, return it.
    - If only month+day, return None (not calendar-ready).
    - Never crashes.
    """
    now = datetime.now()
    t = text.lower()

    # Month Day at HH:MM AM/PM
    m = re.search(
        r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+(\d{1,2})\b.*?\b(\d{1,2}):(\d{2})\s*(am|pm)\b",
        t, flags=re.IGNORECASE | re.DOTALL
    )
    if m:
        mon = m.group(1)[:4].lower()
        day = int(m.group(2))
        hh = int(m.group(3))
        mm = int(m.group(4))
        ampm = m.group(5).upper()
        month = MONTH_MAP.get(mon[:3], None)
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

    # MM/DD HH:MM AM/PM
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

    # If we only see "Feb 10" (no time), DO NOT create a datetime guess.
    return None

def extract_company(email: Dict[str, Any]) -> str:
    subject = (email.get("subject") or "")
    sender = (email.get("from") or "")
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
        "workday.com": "Workday",
        "greenhouse.io": "Greenhouse",
        "lever.co": "Lever",
    }

    m = re.search(r"@([A-Za-z0-9\.-]+\.[A-Za-z]{2,})", sender)
    if m:
        dom = m.group(1).lower()
        for k, v in domain_map.items():
            if k in dom:
                return v

    # “at Google”, “from Microsoft”
    m = re.search(r"\b(at|from)\s+([A-Z][A-Za-z0-9&\.\- ]{2,})\b", subject)
    if m:
        cand = m.group(2).strip()
        if len(cand) <= 35:
            return cand

    for c in ["Amazon", "Google", "Microsoft", "Meta", "Apple", "Tesla", "Cisco", "TCS"]:
        if c.lower() in text:
            return c

    return "Unknown"

def extract_due_date_hint(text: str) -> str:
    t = text.lower()

    # due in X days
    m = re.search(r"\bdue\s+in\s+(\d+)\s+day", t)
    if m:
        return f"due in {m.group(1)} days"

    # due by/on <Month Day>
    m = re.search(r"\bdue\s+(by|on)\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+(\d{1,2})\b", t)
    if m:
        return f"due {m.group(2).title()} {m.group(3)}"

    m = re.search(r"\bdeadline[:\s]+(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+(\d{1,2})\b", t)
    if m:
        return f"due {m.group(1).title()} {m.group(2)}"

    return ""

def parse_interview_details(email: Dict[str, Any]) -> Dict[str, Any]:
    subject = (email.get("subject") or "").strip()
    email_from = (email.get("from") or "").strip()
    text = _build_text(email)

    # Hard-noise rejection
    if _is_noise(email_from, subject):
        return {"is_interview": False}

    # Must show recruiting intent
    if not _has_recruiting_intent(text):
        return {"is_interview": False}

    meeting_link = _find_meeting_link(text)
    start_iso = _parse_datetime(text)  # only if real time found
    stage = classify_stage(text)
    company = extract_company(email)
    due_hint = extract_due_date_hint(text)

    # We count as "interview-ish" if:
    # - stage is known recruiting stage OR meeting link exists OR due hint exists
    interviewish = (stage != "Unclassified") or bool(meeting_link) or bool(due_hint)

    if not interviewish:
        return {"is_interview": False}

    return {
        "is_interview": True,
        "stage": stage,
        "company": company,
        "due_hint": due_hint,
        "start_iso": start_iso,
        "meeting_link": meeting_link,
    }
