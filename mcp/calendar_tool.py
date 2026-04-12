from dataclasses import dataclass
from typing import Optional
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from config import GOOGLE_CALENDAR_ID
from mcp.google_auth import get_calendar_service

@dataclass
class CalendarHoldResult:
    success: bool
    event_id: Optional[str] = None
    error: Optional[str] = None

def parse_to_iso(date_str, time_str, duration_min=30):
    tz_info = ZoneInfo("Asia/Kolkata")
    now = datetime.now(tz_info)
    try:
        dt_str = f"{date_str} {time_str}"
        dt = datetime.strptime(dt_str, "%A, %d %B %Y %I:%M %p")
        dt = dt.replace(tzinfo=tz_info)
        start = dt.isoformat()
        end = (dt + timedelta(minutes=duration_min)).isoformat()
        return start, end
    except Exception:
        # Fallback for waitlist or unparseable input (All-Day/Tomorrow default)
        dt = (now + timedelta(days=1)).replace(hour=12, minute=0, second=0)
        dt = dt.replace(tzinfo=tz_info)
        start = dt.isoformat()
        end = (dt + timedelta(minutes=duration_min)).isoformat()
        return start, end

def create_tentative_hold(
    topic: str,
    code: str,
    date: str,
    time: str,
    duration_min: int = 30,
    waitlist: bool = False,
) -> CalendarHoldResult:
    """Creates an event on Google Calendar natively."""
    try:
        service = get_calendar_service()
        
        status_label = "[WAITLIST]" if waitlist else "[TENTATIVE]"
        title = f"{status_label} Advisor Q&A — {topic} — {code}"

        start_iso, end_iso = parse_to_iso(date, time, duration_min)

        event_body = {
            'summary': title,
            'description': f'Tentative pre-booking hold.\nSecure Booking Code: {code}',
            'start': {
                'dateTime': start_iso,
                'timeZone': 'Asia/Kolkata',
            },
            'end': {
                'dateTime': end_iso,
                'timeZone': 'Asia/Kolkata',
            },
        }

        event = service.events().insert(calendarId=GOOGLE_CALENDAR_ID, body=event_body).execute()
        return CalendarHoldResult(success=True, event_id=event.get('id'))
    except Exception as e:
        return CalendarHoldResult(success=False, error=str(e))

def cancel_calendar_hold(event_id: str) -> CalendarHoldResult:
    """Deletes an event from Google Calendar."""
    try:
        service = get_calendar_service()
        service.events().delete(calendarId=GOOGLE_CALENDAR_ID, eventId=event_id).execute()
        return CalendarHoldResult(success=True, event_id=event_id)
    except Exception as e:
        return CalendarHoldResult(success=False, error=str(e))
