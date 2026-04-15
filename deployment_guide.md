# Deploying to Streamlit Cloud 🚀

This guide explains how to deploy the **Advisor Voice Agent** to Streamlit Cloud.

## 1. Prerequisites
- Your code must be pushed to a **GitHub repository**.
- Ensure `requirements.txt` includes all necessary packages (already present in your project).
- You need a Google Cloud project with the necessary APIs enabled (Calendar, Sheets, Gmail) if you want to use the MCP tools.

## 2. Prepare Secrets
Streamlit Cloud uses a `secrets.toml` format (or a text area in the dashboard) to manage environment variables. You will need to add the following secrets:

### Required Secrets
| Key | Value Source |
| :--- | :--- |
| `GEMINI_API_KEY` | Your Google AI Studio API Key |
| `GOOGLE_SPREADSHEET_ID` | The ID of your Google Sheet |
| `GOOGLE_CALENDAR_ID` | usually `primary` |

### Google Workspace Integration (Mandatory for Cloud)
Since Streamlit Cloud cannot open a browser for OAuth login, you must provide your existing credentials as JSON strings.

| Key | Value Source |
| :--- | :--- |
| `GOOGLE_CREDENTIALS_JSON` | Copy the entire content of `credentials.json` |
| `GOOGLE_TOKEN_JSON` | Copy the entire content of `token.json` (after you've authenticated locally) |

---

## 3. Step-by-Step Deployment

1.  **Commit & Push**: Make sure all your latest changes are pushed to GitHub.
2.  **Login to Streamlit Cloud**: Go to [share.streamlit.io](https://share.streamlit.io/).
3.  **New App**: Click "**Create App**" and select your repository.
4.  **Main File**: Set the Main file path to `app.py` (not `streamlit_app/app.py` as the root version is more featured).
5.  **Advanced Settings**:
    - Click on **Advanced settings...** before deploying.
    - In the **Secrets** section, paste the following (filling in your real values):

```toml
GEMINI_API_KEY = "your_gemini_key_here"
GOOGLE_SPREADSHEET_ID = "1D6jshX6KhWzWbaNDq2nh_LpOiTJ6faX_FhXlHj9ramM"
GOOGLE_CALENDAR_ID = "primary"

# Environment flags
MOCK_GOOGLE_APIS = "0"

# Google Auth strings (Copy-paste the content of your local files)
GOOGLE_CREDENTIALS_JSON = '''
{ 
  "installed": { ... contents of credentials.json ... }
}
'''

GOOGLE_TOKEN_JSON = '''
{
  "token": "...", 
  "refresh_token": "...",
  ... contents of token.json ...
}
'''
```

6.  **Deploy**: Click **Deploy!**

---

## 4. Key Considerations for Cloud
- **Audio Input**: The browser will ask for Microphone permission. `st.audio_input` works seamlessly on modern browsers.
- **Audio Autoplay**: Some browsers (like Chrome) block autoplay until the user interacts with the page once. The "🚀 Connect to Advisor Agent" button handles this initial interaction.
- **Temporary Files**: The app generates temporary `.mp3` files for speech. Streamlit Cloud's ephemeral filesystem allows this, but they are cleared whenever the app reboots.

## 5. Troubleshooting
- **ModuleNotFoundError**: Ensure `requirements.txt` is in the root directory.
- **Google Auth Error**: Ensure you've completed the login locally once to generate a valid `token.json`, then copy that content to your secrets.
- **Port Error**: If you see errors about `8000`, it means you are trying to run the `streamlit_app/app.py` version which expects a separate backend. Use the root `app.py` for a self-contained deployment.
