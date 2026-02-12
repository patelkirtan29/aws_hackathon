# gmail_reader.py
import base64
import re
from typing import List, Dict, Optional

from googleapiclient.discovery import build
from google_auth_helper import get_creds

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def _extract_text_from_payload(payload: dict) -> str:
    """
    Extract readable text from Gmail message payload.
    Prefer text/plain; fall back to snippet-like extraction.
    """
    def decode_part(part_body) -> str:
        data = part_body.get("data")
        if not data:
            return ""
        try:
            return base64.urlsafe_b64decode(data.encode("utf-8")).decode("utf-8", errors="ignore")
        except Exception:
            return ""

    mime_type = payload.get("mimeType", "")
    body = payload.get("body", {}) or {}

    # If it's directly a text body
    if mime_type == "text/plain":
        return decode_part(body)

    # Multipart: walk parts
    parts = payload.get("parts", []) or []
    text_chunks = []

    for p in parts:
        mt = p.get("mimeType", "")
        pb = p.get("body", {}) or {}

        if mt == "text/plain":
            text_chunks.append(decode_part(pb))
        elif mt.startswith("multipart/"):
            text_chunks.append(_extract_text_from_payload(p))

    return "\n".join([t for t in text_chunks if t.strip()])


def _get_header(headers: List[dict], name: str) -> str:
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def fetch_recent_messages(max_results: int = 50, query: Optional[str] = None) -> List[Dict]:
    """
    Fetch recent Gmail messages. Optionally pass Gmail search query:
    e.g. 'newer_than:14d interview OR recruiter'
    """
    creds = get_creds(GMAIL_SCOPES)
    service = build("gmail", "v1", credentials=creds)

    q = query or "newer_than:14d"
    res = service.users().messages().list(userId="me", q=q, maxResults=max_results).execute()
    msgs = res.get("messages", []) or []

    out = []
    for m in msgs:
        mid = m["id"]
        full = service.users().messages().get(userId="me", id=mid, format="full").execute()

        payload = full.get("payload", {}) or {}
        headers = payload.get("headers", []) or []

        subject = _get_header(headers, "Subject")
        from_ = _get_header(headers, "From")
        date = _get_header(headers, "Date")
        snippet = full.get("snippet", "") or ""
        body_text = _extract_text_from_payload(payload)

        # clean body a bit
        body_text = re.sub(r"\s+", " ", body_text).strip()

        out.append({
            "message_id": mid,
            "thread_id": full.get("threadId"),
            "subject": subject,
            "from": from_,
            "date": date,
            "snippet": snippet,
            "body": body_text,
        })

    return out
