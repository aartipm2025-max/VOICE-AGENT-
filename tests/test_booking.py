"""
Tests for core/booking.py — Mock calendar, slot resolution, booking codes,
confirmation builder, and waitlist.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from core.booking import (
    resolve_slots, generate_booking_code, book_slot,
    build_confirmation_message, build_handoff_message,
    add_to_waitlist, get_all_available_slots, get_waitlist,
    reset_calendar,
    _parse_day_preference, _parse_time_preference, _parse_specific_date_preference,
)
from core.session import Slot, Topic


class TestMockCalendar:

    def setup_method(self):
        reset_calendar()

    def test_all_slots_returns_non_empty(self):
        slots = get_all_available_slots()
        assert len(slots) > 0

    def test_all_slots_are_weekdays(self):
        """Slots should only be on Mon-Fri."""
        from datetime import datetime
        slots = get_all_available_slots()
        for slot in slots:
            dt = datetime.strptime(slot.date, "%A, %d %B %Y")
            assert dt.weekday() < 5, f"{slot.date} is a weekend"

    def test_all_slots_have_advisor(self):
        slots = get_all_available_slots()
        for slot in slots:
            assert slot.advisor_id.startswith("ADV-")

    def test_booked_slot_removed_from_availability(self):
        slots = get_all_available_slots()
        initial_count = len(slots)
        book_slot(slots[0])
        remaining = get_all_available_slots()
        assert len(remaining) == initial_count - 1


class TestDayParsing:

    def test_monday(self):
        result = _parse_day_preference("Monday")
        assert 0 in result

    def test_friday(self):
        result = _parse_day_preference("friday afternoon")
        assert 4 in result

    def test_multiple_days(self):
        result = _parse_day_preference("Monday or Wednesday")
        assert 0 in result
        assert 2 in result

    def test_no_day_returns_none(self):
        result = _parse_day_preference("anytime works")
        assert result is None

    def test_tomorrow(self):
        result = _parse_day_preference("tomorrow")
        assert result is not None
        assert len(result) == 1

    def test_specific_date_parsing(self):
        result = _parse_specific_date_preference("20 april")
        assert result is not None
        assert "20 April" in result


class TestTimeParsing:

    def test_morning(self):
        result = _parse_time_preference("morning")
        assert result == (10, 12)

    def test_afternoon(self):
        result = _parse_time_preference("afternoon")
        assert result == (12, 17)

    def test_specific_time_pm(self):
        result = _parse_time_preference("3 PM")
        assert result is not None
        start, end = result
        assert start <= 15 <= end

    def test_specific_time_am(self):
        result = _parse_time_preference("10 AM")
        assert result is not None
        start, end = result
        assert start <= 10 <= end

    def test_no_time_returns_none(self):
        result = _parse_time_preference("anytime")
        assert result is None


class TestSlotResolution:

    def setup_method(self):
        reset_calendar()

    def test_returns_max_2_slots(self):
        slots = resolve_slots("any day")
        assert len(slots) <= 2

    def test_returns_list(self):
        slots = resolve_slots("Monday morning")
        assert isinstance(slots, list)

    def test_slots_are_slot_objects(self):
        slots = resolve_slots("any day")
        if slots:
            assert isinstance(slots[0], Slot)

    def test_morning_filter(self):
        """Morning slots should be before noon."""
        from datetime import datetime
        slots = resolve_slots("morning")
        for slot in slots:
            t = datetime.strptime(slot.time.strip(), "%I:%M %p")
            assert t.hour < 12, f"{slot.time} is not morning"

    def test_afternoon_filter(self):
        """Afternoon slots should be after noon."""
        from datetime import datetime
        slots = resolve_slots("afternoon")
        for slot in slots:
            t = datetime.strptime(slot.time.strip(), "%I:%M %p")
            assert t.hour >= 12, f"{slot.time} is not afternoon"


class TestBookingCodeGenerator:

    def setup_method(self):
        reset_calendar()

    def test_format(self):
        """Code should match XX-YZZZ pattern."""
        import re
        code = generate_booking_code()
        assert re.match(r'^[A-Z]{2}-[A-Z]\d{3}$', code), f"Bad format: {code}"

    def test_uniqueness(self):
        """100 generated codes should all be unique."""
        codes = set()
        for _ in range(100):
            code = generate_booking_code()
            assert code not in codes, f"Duplicate code: {code}"
            codes.add(code)

    def test_length(self):
        code = generate_booking_code()
        assert len(code) == 7  # XX-YZZZ = 7 chars


class TestConfirmationBuilder:

    def test_contains_topic(self):
        slot = Slot(date="Monday, 14 April 2026", time="3:00 PM", advisor_id="ADV-01")
        msgs = build_confirmation_message(Topic.KYC_ONBOARDING, slot, "NL-A742")
        combined = " ".join(msgs)
        assert "KYC/Onboarding" in combined

    def test_contains_date_and_time(self):
        slot = Slot(date="Monday, 14 April 2026", time="3:00 PM", advisor_id="ADV-01")
        msgs = build_confirmation_message(Topic.SIP_MANDATES, slot, "AB-C123")
        combined = " ".join(msgs)
        assert "Monday, 14 April 2026" in combined
        assert "3:00 PM" in combined

    def test_contains_timezone(self):
        slot = Slot(date="Monday, 14 April 2026", time="3:00 PM", advisor_id="ADV-01")
        msgs = build_confirmation_message(Topic.SIP_MANDATES, slot, "AB-C123")
        combined = " ".join(msgs)
        assert "IST" in combined

    def test_contains_booking_code(self):
        slot = Slot(date="Monday, 14 April 2026", time="3:00 PM", advisor_id="ADV-01")
        msgs = build_confirmation_message(Topic.SIP_MANDATES, slot, "XY-Z999")
        combined = " ".join(msgs)
        assert "XY-Z999" in combined


class TestHandoffBuilder:

    def test_contains_secure_url(self):
        msgs = build_handoff_message("NL-A742", "https://secure.example.com")
        combined = " ".join(msgs)
        assert "https://secure.example.com" in combined

    def test_contains_time_limit(self):
        msgs = build_handoff_message("NL-A742", "https://secure.example.com")
        combined = " ".join(msgs)
        assert "2 hours" in combined


class TestWaitlist:

    def setup_method(self):
        reset_calendar()

    def test_add_to_waitlist(self):
        entry = add_to_waitlist(
            session_id="test-123",
            topic=Topic.KYC_ONBOARDING,
            day_pref="Monday",
            time_pref="morning",
        )
        assert entry.code is not None
        assert entry.topic == Topic.KYC_ONBOARDING

    def test_waitlist_persists(self):
        add_to_waitlist("s1", Topic.SIP_MANDATES, "Tuesday", "afternoon")
        add_to_waitlist("s2", Topic.KYC_ONBOARDING, "Wednesday", "morning")
        wl = get_waitlist()
        assert len(wl) == 2

    def test_waitlist_codes_unique(self):
        e1 = add_to_waitlist("s1", Topic.SIP_MANDATES, "Mon", "AM")
        e2 = add_to_waitlist("s2", Topic.KYC_ONBOARDING, "Tue", "PM")
        assert e1.code != e2.code


class TestBookSlot:

    def setup_method(self):
        reset_calendar()

    def test_booking_removes_from_pool(self):
        all_before = get_all_available_slots()
        target = all_before[0]
        book_slot(target)
        all_after = get_all_available_slots()
        booked_dates_times = [(s.date, s.time) for s in all_after]
        assert (target.date, target.time) not in booked_dates_times

    def test_cannot_book_same_slot_twice(self):
        all_before = get_all_available_slots()
        target = all_before[0]
        assert book_slot(target) is True
        assert book_slot(target) is False
