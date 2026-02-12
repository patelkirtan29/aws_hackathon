"""
Gmail OAuth2 Authentication Setup
Run this once to generate token.json with Gmail permissions
"""

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
import os

# Gmail API scopes
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

def authenticate_gmail():
    """Authenticate and save Gmail credentials to token.json"""
    creds = None
    
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES
            )
            creds = flow.run_local_server(port=0)
        
        # Save credentials for next run
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    
    print("✅ Gmail authentication successful!")

if __name__ == "__main__":
    authenticate_gmail()
