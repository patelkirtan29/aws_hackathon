"""
Unified OAuth2 Authentication for Google APIs
Handles both Gmail and Google Calendar credentials with separate tokens
"""

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
import os
import json

# Define scopes for each service
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar"]

def authenticate(service_name, scopes, token_file="token.json"):
    """
    Generic authentication function for Google APIs
    
    Args:
        service_name: Name of the service (gmail, calendar)
        scopes: List of OAuth2 scopes
        token_file: Path to save credentials
    
    Returns:
        Credentials object
    """
    creds = None
    
    if os.path.exists(token_file):
        try:
            creds = Credentials.from_authorized_user_file(token_file, scopes)
        except:
            creds = None
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", scopes
            )
            creds = flow.run_local_server(port=0)
        
        # Save credentials
        with open(token_file, "w") as token:
            token.write(creds.to_json())
    
    return creds

def get_gmail_credentials(token_file="token_gmail.json"):
    """Get Gmail API credentials"""
    return authenticate("gmail", GMAIL_SCOPES, token_file)

def get_calendar_credentials(token_file="token_calendar.json"):
    """Get Google Calendar API credentials"""
    return authenticate("calendar", CALENDAR_SCOPES, token_file)

if __name__ == "__main__":
    print("Setting up Gmail authentication...")
    get_gmail_credentials()
    print("✅ Gmail authentication successful!")
    
    print("\nSetting up Calendar authentication...")
    get_calendar_credentials()
    print("✅ Calendar authentication successful!")
