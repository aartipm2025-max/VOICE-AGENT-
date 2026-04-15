"""
Tests for Phase 5: REST API endpoints — aligned with refactored State enum.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient
from surfaces.api import app
from core.session import clear_all_sessions, State
from core.booking import reset_calendar


client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_teardown():
    clear_all_sessions()
    reset_calendar()
    yield
    clear_all_sessions()
    reset_calendar()


class TestRESTAPI:

    def test_create_session(self):
        response = client.post("/session")
        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert len(data["session_id"]) > 10

    def test_send_message_valid_session(self):
        create_res = client.post("/session")
        session_id = create_res.json()["session_id"]

        msg_res = client.post("/message", json={
            "session_id": session_id,
            "text": "I want to book an appointment"
        })
        assert msg_res.status_code == 200
        data = msg_res.json()
        assert len(data["responses"]) > 0
        assert data["completed"] is False

    def test_send_message_invalid_session(self):
        msg_res = client.post("/message", json={
            "session_id": "fake-1234",
            "text": "Hello"
        })
        assert msg_res.status_code == 404

    def test_compliance_works_via_api(self):
        create_res = client.post("/session")
        session_id = create_res.json()["session_id"]

        msg_res = client.post("/message", json={
            "session_id": session_id,
            "text": "my phone is 9876543210"
        })
        data = msg_res.json()
        joined = " ".join(data["responses"]).lower()
        assert "secure" in joined or "personal" in joined

    def test_get_session_status(self):
        create_res = client.post("/session")
        session_id = create_res.json()["session_id"]

        status_res = client.get(f"/session/{session_id}")
        assert status_res.status_code == 200
        data = status_res.json()
        assert data["state"] == "START"

    def test_delete_session(self):
        create_res = client.post("/session")
        session_id = create_res.json()["session_id"]

        del_res = client.delete(f"/session/{session_id}")
        assert del_res.status_code == 200

        msg_res = client.post("/message", json={
            "session_id": session_id,
            "text": "Hello"
        })
        assert msg_res.status_code == 404
