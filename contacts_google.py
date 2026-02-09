# contacts_google.py
from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Optional

from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

# Read-only contacts scope (People API)
SCOPES = ["https://www.googleapis.com/auth/contacts.readonly"]  # :contentReference[oaicite:5]{index=5}

CREDENTIALS_FILE = Path("credentials.json")  # downloaded from Google Cloud Console
TOKEN_FILE = Path("token.json")              # created automatically after first login


def get_people_service():
    """
    Creates an authenticated People API service using OAuth for installed apps.
    Token is cached locally in token.json.
    """
    creds: Optional[Credentials] = None

    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_FILE.exists():
                raise FileNotFoundError(
                    "credentials.json not found. Download OAuth Desktop credentials and place it in project root."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)  # opens browser for consent :contentReference[oaicite:6]{index=6}

        TOKEN_FILE.write_text(creds.to_json())

    return build("people", "v1", credentials=creds)


def fetch_contacts(max_contacts: int = 500) -> List[Dict[str, str]]:
    """
    Returns contacts as a list of dicts: {name, email}
    """
    service = get_people_service()

    # people.connections.list provides user's contacts :contentReference[oaicite:7]{index=7}
    resp = (
        service.people()
        .connections()
        .list(
            resourceName="people/me",
            pageSize=min(max_contacts, 1000),
            personFields="names,emailAddresses",
        )
        .execute()
    )

    connections = resp.get("connections", []) or []
    out: List[Dict[str, str]] = []

    for person in connections:
        names = person.get("names", []) or []
        emails = person.get("emailAddresses", []) or []

        name = names[0].get("displayName") if names else ""
        email = emails[0].get("value") if emails else ""

        if email:
            out.append({"name": name or email, "email": email})

    return out


def contacts_matching_company(company: str, max_hits: int = 10) -> List[Dict[str, str]]:
    """
    Heuristic match:
    - Prefer email domains like @google.com, @amazon.com etc
    - Also match if company word appears in email domain
    """
    company_key = company.lower().strip().replace(" ", "")
    contacts = fetch_contacts()

    ranked = []
    for c in contacts:
        email = c["email"].lower()
        score = 0

        # domain-based match (best signal)
        if "@" in email:
            domain = email.split("@", 1)[1]
            if company_key in domain.replace(".", ""):
                score += 100

            # common big-tech: 'google' -> google.com, 'microsoft' -> microsoft.com
            if company_key in domain:
                score += 60

        if score > 0:
            ranked.append((score, c))

    ranked.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in ranked[:max_hits]]
