from mcp.dispatcher import execute_booking_side_effects, execute_cancel_side_effects

print("Starting LIVE Google API Test...\n")

print("1. Booking an appointment (Writing to Calendar, Sheets, and Gmail Draft)...")
book_res = execute_booking_side_effects(
    topic="System Integration Test", 
    code="SYS-T123", 
    date="Monday, 31 Dec 2026", 
    time="1:00 PM",
    waitlist=False
)

if book_res.all_success:
    print("✅ Booking successful!")
    print(f"  Calendar Event ID: {book_res.calendar_result.event_id}")
    print(f"  Sheets Note ID: {book_res.notes_result.note_id}")
    print(f"  Gmail Draft ID: {book_res.email_result.draft_id}")
else:
    print("❌ Booking failed:", book_res.errors)
    exit(1)

print("\n2. Canceling the appointment (Deleting from Calendar, Appending Cancel row to Sheet)...")
cancel_res = execute_cancel_side_effects(book_res.calendar_result.event_id, "SYS-T123")

if cancel_res.all_success:
    print("✅ Cancellation successful! Event removed from Calendar and new 'Cancelled' row added to Sheet.")
else:
    print("❌ Cancellation failed:", cancel_res.errors)

print("\nNote: Please check your Gmail 'Drafts' folder. You will see a real unread draft email waiting for your approval!")
