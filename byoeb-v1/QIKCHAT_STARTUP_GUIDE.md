# BYOeB Qikchat Bot - Manual Startup Instructions

## Overview
You need to run TWO separate Python applications for the Qikchat oncology bot to work:

1. **Knowledge Base Service** (Port 5001) - Handles oncology Q&A
2. **Chat App Service** (Port 5000) - Handles Qikchat webhooks and messaging

## Quick Start (Automated)

Run the PowerShell script:
```powershell
cd c:\Users\t-asanghvi\work\byoeb\byoeb-v1
.\start_qikchat_bot.ps1
```

## Manual Start Instructions

### Terminal 1: Knowledge Base Service
```powershell
cd c:\Users\t-asanghvi\work\byoeb\byoeb-v1\byoeb\byoeb\kb_app
python run.py
```
This will start on: http://127.0.0.1:5001

### Terminal 2: Chat App Service  
```powershell
cd c:\Users\t-asanghvi\work\byoeb\byoeb-v1\byoeb\byoeb\chat_app
python run.py
```
This will start on: http://127.0.0.1:5000

## Important URLs

- **Knowledge Base API**: http://127.0.0.1:5001
- **Chat App**: http://127.0.0.1:5000  
- **Qikchat Webhook Endpoint**: http://127.0.0.1:5000/webhook/qikchat

## Testing the Bot

1. **Configure Webhook in Qikchat Dashboard**:
   - Set webhook URL to: `http://127.0.0.1:5000/webhook/qikchat`
   - Use verify token: `byoeb_qikchat_verify_token_2025`

2. **Send Test Message**:
   - Send a WhatsApp message to your Qikchat number
   - Ask something like: "What is chemotherapy?"
   - Check terminal logs for incoming message processing

3. **Monitor Logs**:
   - Watch Terminal 2 (Chat App) for incoming webhook calls
   - Look for successful message processing and response sending

## Configuration Files Modified

- ✅ `keys.env` - Contains Qikchat API credentials
- ✅ `app_config.json` - Qikchat channel configuration added
- ✅ `chat.py` - Qikchat webhook endpoint added (/webhook/qikchat)
- ✅ `message_producer.py` - Qikchat message validation added
- ✅ `validate_message.py` - Qikchat message format validation
- ✅ `kb_app/run.py` - Changed to port 5001 (no port conflict)

## Expected Flow

1. User sends WhatsApp message → Qikchat API
2. Qikchat API → Your webhook (http://127.0.0.1:5000/webhook/qikchat)  
3. Chat App validates message → Processes with oncology knowledge base
4. Chat App sends response → Qikchat API → User's WhatsApp

## Troubleshooting

- **Port conflicts**: Make sure ports 5000 and 5001 are available
- **Import errors**: Check that all Python dependencies are installed
- **Webhook not receiving**: Ensure Qikchat dashboard has correct webhook URL
- **No responses**: Check both terminal windows for error messages

## Dependencies Check

Make sure these are installed:
```powershell
pip install fastapi uvicorn python-multipart
```
