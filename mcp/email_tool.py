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
        # No 'To' header — this is a draft for advisor review, not a sent email
        message['Subject'] = subject

        # base64url encode the message
        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        create_message = {'message': {'raw': encoded_message}}

        draft = service.users().drafts().create(userId='me', body=create_message).execute()
        draft_id = draft.get('id')
        # Update mock for tests
        _drafts_mock[draft_id] = DraftMock(id=draft_id, subject=subject, body=body, to=advisor_email, waitlist=waitlist)
        return EmailResult(success=True, draft_id=draft_id)

    except Exception as e:
        return EmailResult(success=False, error=str(e))


def send_client_confirmation_email(
    to_email: str,
    topic: str,
    code: str,
    date: str,
    time: str,
) -> EmailResult:
    """Send a booking confirmation email directly to the client."""
    try:
        service = get_gmail_service()
        subject = f"Booking Confirmed: {topic} ({code})"
        body = f"""
Hello,

Your appointment booking is confirmed.

Booking Details:
  Booking Code: {code}
  Topic: {topic}
  Date: {date}
  Time: {time} IST

Please keep this booking code for future reference.

Regards,
Advisor Appointment Scheduler
        """.strip()

        message = EmailMessage()
        message["To"] = to_email
        message["Subject"] = subject
        message.set_content(body)

        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        send_body = {"raw": encoded_message}

        sent = service.users().messages().send(userId="me", body=send_body).execute()
        message_id = sent.get("id")
        _drafts_mock[message_id] = DraftMock(
            id=message_id,
            subject=subject,
            body=body,
            to=to_email,
            waitlist=False,
            status="SENT",
            approval_gated=False,
        )
        return EmailResult(success=True, draft_id=message_id)
    except Exception as e:
        return EmailResult(success=False, error=str(e))

# --- Helper functions for tests/mock management ---
_drafts_mock = {}

@dataclass
class DraftMock:
    id: str
    subject: str
    body: str
    to: str
    status: str = "DRAFT"
    approval_gated: bool = True
    waitlist: bool = False

def get_draft(draft_id: str) -> Optional[DraftMock]:
    """Checks mock drafts."""
    return _drafts_mock.get(draft_id)

def reset_drafts():
    _drafts_mock.clear()
