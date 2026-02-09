# interview_parser.py
import re
from typing import Dict, Optional
from dateutil import parser as dateparser

MEETING_LINK_RE = re.compile(
    r"(https?://[^\s]+(?:zoom\.us|google\.com/meet|teams\.microsoft\.com|webex\.com)[^\s]*)",
    re.IGNORECASE,
)

INTERVIEW_KEYWORDS = [
    "interview",
    "schedule",
    "scheduled",
    "invitation",
    "onsite",
    "on-site",
    "phone screen",
    "technical screen",
    "interview loop",
    "final round",
    "recruiter",
]

# Very simple datetime patterns that often appear in emails
DATE_HINT_RE = re.compile(
    r"(\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\b.*?\b(?:AM|PM)\b)|"
    r"(\b\d{1,2}/\d{1,2}/\d{2,4}\b.*?\b(?:AM|PM)\b)|"
    r"(\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\b.*?\b(?:AM|PM)\b)",
    re.IGNORECASE
)


def is_interview_email(subject: str, body: str) -> bool:
    text = f"{subject}\n{body}".lower()
    return any(k in text for k in INTERVIEW_KEYWORDS)


def extract_meeting_link(body: str) -> Optional[str]:
    m = MEETING_LINK_RE.search(body or "")
    return m.group(1) if m else None


def extract_datetime(body: str) -> Optional[str]:
    """
    Demo-simple:
    - find a date-ish line fragment
    - let dateutil parse it
    Returns ISO string or None
    """
    if not body:
        return None

    m = DATE_HINT_RE.search(body)
    if not m:
        return None

    fragment = next((g for g in m.groups() if g), None)
    if not fragment:
        return None

    try:
        dt = dateparser.parse(fragment, fuzzy=True)
        if not dt:
            return None
        return dt.isoformat()
    except Exception:
        return None


def parse_interview_details(email: Dict) -> Dict:
    subject = email.get("subject", "") or ""
    body = email.get("body", "") or ""
    snippet = email.get("snippet", "") or ""

    text = body if len(body) > 0 else snippet

    link = extract_meeting_link(text)
    dt_iso = extract_datetime(text)

    return {
        "is_interview": is_interview_email(subject, text),
        "start_iso": dt_iso,          # may be None
        "meeting_link": link,         # may be None
    }
