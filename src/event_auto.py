# import datetime
from email_reader import get_email_content, get_gmail_service, list_unread_emails
from ai import extract_event, create_event  # your previous calendar file
from datetime import datetime

current_date = datetime.now().strftime("%Y-%m-%d")

service = get_gmail_service()
messages = list_unread_emails(service, max_results=5)

if not messages:
    print("No unread emails found.")
else:
    for msg in messages:
        try:
            content = get_email_content(service, msg["id"])
            # Combine subject and body for better event extraction
            email_text = f"Subject: {content['subject']}\n\nBody: {content['body'][:500]}"
            
            event = extract_event(email_text, timezone="America/New_York", current_date=current_date)
            
            # Only create event if summary is not empty
            if event.summary and event.summary.strip():
                link = create_event(event)
                print(f"✅ Created calendar event: {link}")
                print(f"   Event: {event.summary}")
                break
        except Exception as e:
            print(f"⚠️  Could not extract event from email: {str(e)[:100]}")
            continue

print("Done!")