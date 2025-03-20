import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from django.conf import settings

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
]
IMPERSONATE_USER = "contact@hdiplatform.in"
credentials = service_account.Credentials.from_service_account_file(
    settings.GOOGLE_SERVICE_ACCOUNT_CRED, scopes=SCOPES
)
credentials = credentials.with_subject(IMPERSONATE_USER)

calendar_service = build("calendar", "v3", credentials=credentials)


def create_meet_and_calendar_invite(
    interviewer_email, candidate_email, start_time, end_time
):
    event = {
        "summary": f"Interview of {candidate_email} with {interviewer_email}",
        "description": """ 
        - Please join the Interview at least 3 mins before.  
        - Please keep the video on during the entire interview.  
        - Please check your speaker/microphone properly before the interview.  
        - Please ensure a quiet place to avoid any background noise.  
        - Please ensure you have the appropriate IDE for machine coding.  
        - The Interviewer's video will be off to maintain confidentiality.  
        - If the interviewer does not join within 9 minutes from the scheduled time, the interview will be postponed, and you will receive an email with rescheduling details.  
        """,
        "start": {
            "dateTime": start_time.isoformat(),
            "timeZone": "Asia/Kolkata",
        },
        "end": {
            "dateTime": end_time.isoformat(),
            "timeZone": "Asia/Kolkata",
        },
        "attendees": [
            {"email": interviewer_email},
            {"email": candidate_email},
        ],
        "conferenceData": {
            "createRequest": {
                "requestId": f"meet-{start_time.timestamp()}",
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        },
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "email", "minutes": 24 * 60},
                {"method": "popup", "minutes": 10},
            ],
        },
        "transparency": "transparent",
    }

    event = (
        calendar_service.events()
        .insert(
            calendarId="interview@hdiplatform.in",
            body=event,
            conferenceDataVersion=1,  # to generate meet link
        )
        .execute()
    )

    return event.get("hangoutLink"), event.get("id")


def get_meeting_info(event_id):
    event = (
        calendar_service.events().get(calendarId="primary", eventId=event_id).execute()
    )
    return event
