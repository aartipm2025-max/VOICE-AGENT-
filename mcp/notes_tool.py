from dataclasses import dataclass
from typing import Optional
from config import GOOGLE_SPREADSHEET_ID
from mcp.google_auth import get_sheets_service
import uuid

@dataclass
class NoteResult:
    success: bool
    note_id: Optional[str] = None
    error: Optional[str] = None

@dataclass
class BookingNote:
    note_id: str
    date: str
    topic: str
    slot: str
    code: str
    status: str
    calendar_event_id: Optional[str] = None

def append_booking_note(
    date: str,
    topic: str,
    slot: str,
    code: str,
    status: str = "Tentative",
    calendar_event_id: Optional[str] = None,
) -> NoteResult:
    """Appends a real row to Google Sheets."""
    try:
        service = get_sheets_service()
        note_id = f"note-{str(uuid.uuid4())[:8]}"
        
        # Row format: Note ID, Date, Topic, Slot, Booking Code, Status, Event ID
        values = [
            [note_id, date, topic, slot, code, status, calendar_event_id or ""]
        ]
        body = {'values': values}
        
        service.spreadsheets().values().append(
            spreadsheetId=GOOGLE_SPREADSHEET_ID,
            range="A:G",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body=body
        ).execute()

        # Update mock for tests
        _notes_mock.append(BookingNote(
            note_id=note_id, date=date, topic=topic, slot=slot, code=code, status=status, calendar_event_id=calendar_event_id
        ))

        return NoteResult(success=True, note_id=note_id)
    except Exception as e:
        return NoteResult(success=False, error=str(e))


def get_note_by_code(code: str) -> Optional[BookingNote]:
    """Finds the booking note row. Checks mock for tests first."""
    # Check mock for tests
    for note in reversed(_notes_mock):
        if note.code == code:
            return note

    try:
        service = get_sheets_service()
        result = service.spreadsheets().values().get(
            spreadsheetId=GOOGLE_SPREADSHEET_ID,
            range="A:G"
        ).execute()
        rows = result.get('values', [])
        
        # Search from latest row backwards
        for row in reversed(rows):
            if len(row) > 4 and row[4] == code:
                event_id = row[6] if len(row) > 6 else None
                return BookingNote(
                    note_id=row[0],
                    date=row[1] if len(row)>1 else "",
                    topic=row[2] if len(row)>2 else "",
                    slot=row[3] if len(row)>3 else "",
                    code=row[4],
                    status=row[5] if len(row)>5 else "",
                    calendar_event_id=event_id
                )
    except Exception:
        pass
    return None

# --- Helper functions for tests/mock management ---
_notes_mock = []

def get_all_notes():
    return _notes_mock

def reset_notes():
    _notes_mock.clear()
