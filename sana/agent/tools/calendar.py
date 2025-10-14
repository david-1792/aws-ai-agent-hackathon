from typing import Any
from strands.tools import tool

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from sana.core.auth import get_google_token, GOOGLE_SCOPES
from sana.core.context import SanaContext

class GoogleCalendarTools():
    def __init__(self) -> None:
        self.credentials: Credentials | None = None
        self.calendar: Any = None

    @property
    def tools(self) -> list:
        return [self.create_calendar_event, self.get_free_timeslots]
    
    def _authenticate(self) -> None:
        if not (access_token := SanaContext.get_google_token()):
            try:
                access_token: str = get_google_token()
                if not access_token:
                    raise Exception('get_google_token could not retrieve a token')
                SanaContext.set_google_token(access_token)
            except Exception as e:
                return f'Could not authenticate with Google: {e}'

        self.credentials = Credentials(token=access_token, scopes=GOOGLE_SCOPES)
        self.calendar = build('calendar', 'v3', credentials=self.credentials)

    @tool
    async def create_calendar_event(
        self,
        summary: str,
        description: str | None,
        start_time: str,
        end_time: str,
        timezone: str = 'UTC',
    ) -> None:
        """
        Args:
            summary (str): The summary or title of the event.
            description (str | None): The description of the event.
            start_time (str): The start time in RFC3339 format (e.g., '2023-10-01T09:00:00Z').
            end_time (str): The end time in RFC3339 format (e.g., '2023-10-01T10:00:00Z').
            timezone (str): The timezone for the event (default is 'UTC').
        """

        if not self.calendar or not self.credentials:
            self._authenticate()
            
        event = {
            'summary': summary,
            'description': description,
            'start': {
                'dateTime': start_time,
                'timeZone': timezone,
            },
            'end': {
                'dateTime': end_time,
                'timeZone': timezone,
            },
        }

        try:
            created_event = self.calendar.events().insert(calendarId='primary', body=event).execute()
            return f'Event created with id {created_event.get("id")} and link {created_event.get("htmlLink")}'
        except HttpError as e:
            return f'An error occurred: {e}'
        
    @tool
    def get_free_timeslots(
        self,
        from_time: str,
        to_time: str,
        timezone: str = 'UTC',
    ):
        """
        Args:
            from_time (str): The start time in RFC3339 format (e.g., '2023-10-01T09:00:00Z').
            to_time (str): The end time in RFC3339 format (e.g., '2023-10-01T17:00:00Z').
            timezone (str): The timezone for the query (default is 'UTC').
        """

        if not self.calendar or not self.credentials:
            self._authenticate()
            
        try:
            body: dict = {
                "timeMin": from_time,
                "timeMax": to_time,
                "timeZone": timezone,
                "items": [{"id": 'primary'}]
            }

            freebusy = self.calendar.freebusy().query(body=body).execute()
            return freebusy['calendars']['primary']['busy']
        except HttpError as e:
            return f'An error occurred: {e}'
