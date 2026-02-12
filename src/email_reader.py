"""
Email Reader using Gmail API + Python

Features:
- Reads unread emails
- Fetches subject, sender, snippet, and body
- Can integrate with AI later for event/task extraction
"""

import base64
from googleapiclient.discovery import build
from bs4 import BeautifulSoup
from utils.auth import get_gmail_credentials

# =========================
# Gmail service
# =========================
def get_gmail_service():
    """
    Authenticate using token_gmail.json (OAuth2) and return Gmail API service
    """
    creds = get_gmail_credentials()
    service = build("gmail", "v1", credentials=creds)
    return service

# =========================
# Fetch emails
# =========================
def list_unread_emails(service, max_results=5):
    """
    Get unread emails from inbox
    """
    results = service.users().messages().list(
        userId="me",
        labelIds=["INBOX", "UNREAD"],
        maxResults=max_results
    ).execute()

    messages = results.get("messages", [])
    return messages

# =========================
# Read email content
# =========================
def get_email_content(service, msg_id):
    """
    Get subject, sender, and body of an email
    """
    message = service.users().messages().get(userId="me", id=msg_id, format="full").execute()
    headers = message.get("payload", {}).get("headers", [])
    subject = next((h["value"] for h in headers if h["name"] == "Subject"), "")
    sender = next((h["value"] for h in headers if h["name"] == "From"), "")

    # Extract body
    parts = message.get("payload", {}).get("parts", [])
    body = ""

    if parts:
        for part in parts:
            if part.get("mimeType") == "text/plain":
                data = part["body"].get("data", "")
                body = base64.urlsafe_b64decode(data.encode("UTF-8")).decode("UTF-8")
            elif part.get("mimeType") == "text/html":
                data = part["body"].get("data", "")
                html = base64.urlsafe_b64decode(data.encode("UTF-8")).decode("UTF-8")
                # Convert HTML to text
                body = BeautifulSoup(html, "html.parser").get_text()
    else:
        # Single part email
        data = message.get("payload", {}).get("body", {}).get("data", "")
        if data:
            body = base64.urlsafe_b64decode(data.encode("UTF-8")).decode("UTF-8")

    return {
        "subject": subject,
        "from": sender,
        "body": body
    }

if __name__ == "__main__":
    service = get_gmail_service()
    messages = list_unread_emails(service, max_results=1)

    if not messages:
        print("No unread emails found.")
    else:
        for i, msg in enumerate(messages, 1):
            email_content = get_email_content(service, msg["id"])
            print(f"\n--- Email {i} ---")
            print(f"From: {email_content['from']}")
            print(f"Subject: {email_content['subject']}")
            print(f"Body:\n{email_content['body'][:500]}...")  # First 500 chars
