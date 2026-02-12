from datetime import datetime
from typing import Optional
from pydantic import BaseModel

from langchain_ollama import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser

from googleapiclient.discovery import build
from utils.auth import get_calendar_credentials

class CalendarEvent(BaseModel):
    summary: str
    description: Optional[str] = None
    location: Optional[str] = None
    startDateTime: str
    startTimeZone: str
    endDateTime: str
    endTimeZone: str

def extract_event(text: str, timezone: str, current_date: str) -> CalendarEvent:
    llm = OllamaLLM(
        model="llama3",
        temperature=0
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a precise calendar assistant. Output valid JSON only."),
        ("human", f"""
            Extract a calendar event from the text below and return ONLY valid JSON.

            Text: "{text}"

            Current date: {current_date}
            Timezone: {timezone}

            Return JSON with these exact fields (string values):
            - summary: event title
            - description: event description (or null)
            - location: event location (or null)
            - startDateTime: ISO-8601 datetime
            - startTimeZone: timezone string
            - endDateTime: ISO-8601 datetime
            - endTimeZone: timezone string

            Output ONLY the JSON object, no other text.
        """)
    ])

    parser = PydanticOutputParser(pydantic_object=CalendarEvent)
    chain = prompt | llm | parser

    return chain.invoke({
        "text": text,
        "timezone": timezone,
        "current_date": current_date
    })

def get_calendar_service():
    creds = get_calendar_credentials()
    return build("calendar", "v3", credentials=creds)

def create_event(event: CalendarEvent):
    service = get_calendar_service()
    
    google_event = {
        "summary": event.summary,
        "description": event.description,
        "location": event.location,
        "start": {
            "dateTime": event.startDateTime,
            "timeZone": event.startTimeZone,
        },
        "end": {
            "dateTime": event.endDateTime,
            "timeZone": event.endTimeZone,
        },
    }

    created_event = service.events().insert(
        calendarId="primary",
        body=google_event
    ).execute()

    return created_event.get("htmlLink")

if __name__ == "__main__":
    USER_INPUT = "Team sync tomorrow at 10am for 30 minutes, online"
    TIMEZONE = "America/New_York"

    event = extract_event(
        text=USER_INPUT,
        timezone=TIMEZONE,
        current_date=datetime.now().strftime("%Y-%m-%d")
    )

    print("\n🧠 Extracted event:")
    print(event.model_dump_json(indent=2))

    link = create_event(event)
    print(f"\n✅ Event created: {link}")
