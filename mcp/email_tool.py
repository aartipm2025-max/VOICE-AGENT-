import base64
from email.message import EmailMessage
from dataclasses import dataclass
from typing import Optional
from mcp.google_auth import get_gmail_service

@dataclass
class EmailResult:
    success: bool
    draft_id: Optional[str] = None
    error: Optional[str] = None

# We use the special "me" identifier for the currently authenticated user
DEFAULT_ADVISOR_EMAIL = "me"

def draft_advisor_email(
    topic: str,
    code: str,
    slot: str,
    date: str,
    waitlist: bool = False,
    advisor_email: str = DEFAULT_ADVISOR_EMAIL,
) -> EmailResult:
    """Creates a real RFC2822 encoded Draft in the authenticated user's Gmail."""
    try:
        service = get_gmail_service()
        
        status_label = "WAITLIST" if waitlist else "Pre-Booking"
        subject = f"[{status_label}] {topic} — {code} — {date} {slot}"
        
        booking_type = "Waitlist Request" if waitlist else "Tentative Pre-Booking"
        body = f"""
--- {booking_type} Notification ---

A new {booking_type.lower()} has been created:

  Booking Code:  {code}
  Topic:         {topic}
  Date:          {date}
  Time:          {slot}
  Type:          {booking_type}

Action Required:
  - Review the booking details
  - {"Assign a slot when available" if waitlist else "Confirm or reject the tentative hold"}
  - Approve this email to notify the client

Note: The client has been given a secure link to provide their
contact details. No personal information was collected on the call.

---
This email requires manual approval before sending.
        """.strip()

        message = EmailMessage()
        message.set_content(body)
        message['To'] = "advisor-review@example.com"  # Replace with actual target if needed
        message['Subject'] = subject

        # base64url encode the message
        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        create_message = {'message': {'raw': encoded_message}}

        draft = service.users().drafts().create(userId='me', body=create_message).execute()
        return EmailResult(success=True, draft_id=draft.get('id'))

    except Exception as e:
        return EmailResult(success=False, error=str(e))
