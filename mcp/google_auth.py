import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Scopes needed for Calendar, Sheets, and Gmail Drafts
SCOPES = [
    'https://www.googleapis.com/auth/calendar.events',
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/gmail.compose'
]

def get_credentials():
    """Gets valid user credentials from storage or initiates OAuth2 flow."""
    creds = None
    cred_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'credentials.json')
    token_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'token.json')
    
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(cred_path, SCOPES)
            creds = flow.run_local_server(port=0)
            
        # Save the credentials for the next run
        with open(token_path, 'w') as token:
            token.write(creds.to_json())
            
    return creds

def get_calendar_service():
    if os.environ.get("MOCK_GOOGLE_APIS") == "1":
        from unittest.mock import MagicMock
        return MagicMock()
    return build('calendar', 'v3', credentials=get_credentials())

def get_sheets_service():
    if os.environ.get("MOCK_GOOGLE_APIs") == "1":
        from unittest.mock import MagicMock
        return MagicMock()
    return build('sheets', 'v4', credentials=get_credentials())

def get_gmail_service():
    if os.environ.get("MOCK_GOOGLE_APIs") == "1":
        from unittest.mock import MagicMock
        return MagicMock()
    return build('gmail', 'v1', credentials=get_credentials())

if __name__ == '__main__':
    print("Initiating Google Authentication...")
    get_credentials()
    print("✅ Authentication successful! token.json has been created.")
