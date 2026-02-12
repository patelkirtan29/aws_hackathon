# calendar_push.py
from datetime import datetime, timedelta
from typing import Optional, Dict

from googleapiclient.discovery import build
from google_auth_helper import get_creds

CAL_SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


def create_event(
    title: str,
    start_iso: str,
    duration_mins: int = 60,
    description: str = "",
    location: str = "",
    calendar_id: str = "primary",
) -> Dict:
    creds = get_creds(CAL_SCOPES)
    service = build("calendar", "v3", credentials=creds)

    start_dt = datetime.fromisoformat(start_iso)
    end_dt = start_dt + timedelta(minutes=duration_mins)

    body = {
        "summary": title,
        "description": description,
        "location": location,
        "start": {"dateTime": start_dt.isoformat()},
        "end": {"dateTime": end_dt.isoformat()},
    }

    created = service.events().insert(calendarId=calendar_id, body=body).execute()
    return created
