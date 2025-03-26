import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from django.conf import settings

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/drive",
]
IMPERSONATE_USER = "interview@hdiplatform.in"
credentials = service_account.Credentials.from_service_account_file(
    settings.GOOGLE_SERVICE_ACCOUNT_CRED, scopes=SCOPES
)
credentials = credentials.with_subject(IMPERSONATE_USER)

calendar_service = build("calendar", "v3", credentials=credentials)
drive_service = build("drive", "v3", credentials=credentials)


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
            calendarId="primary",
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


def download_file(file_id, mime_type=None):
    if mime_type:
        request = drive_service.files().export_media(fileId=file_id, mimeType=mime_type)
    else:
        request = drive_service.files().get_media(fileId=file_id)
    return request.execute()


def download_from_google_drive(interview_id, event_id):
    event_info = get_meeting_info(event_id)
    attachments = event_info.get("attachments", [])

    downloaded_files = []

    for attachment in attachments:
        file_id, fil_type, file_name = (
            attachment["fileId"],
            attachment["mimeType"],
            attachment["title"],
        )
        if "video" in fil_type:
            data = download_file(file_id)
            downloaded_files.append(
                {"type": "video", "data": data, "name": f"{event_id}.mp4"}
            )
        elif "Transcript" in file_name:
            data = download_file(file_id, mime_type="text/plain")
            downloaded_files.append(
                {"type": "transcript", "data": data, "name": f"{event_id}.txt"}
            )

    return (
        {"interview_id": interview_id, "files": downloaded_files}
        if downloaded_files
        else {}
    )


# keep below funcation for testing purpose
def list_all_files():
    results = drive_service.files().list().execute()
    files = results.get("files", [])
    if not files:
        print("❌ No files found.")
        return []
    for file in files:
        print(f"📂 {file['name']} (ID: {file['id']})")
    return files
