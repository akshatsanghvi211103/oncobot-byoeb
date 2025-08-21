# BYOeB Qikchat Integration Documentation

## Overview
This document explains how the BYOeB (Build Your Own Expert Bot) platform integrates with Qikchat for WhatsApp messaging, specifically for the oncology bot use case.

## Integration Flow

### 1. Message Reception (Webhook)
**What happens**: User sends a WhatsApp message → Qikchat receives it → Qikchat sends webhook to BYOeB

**Code Location**: `byoeb-integrations/byoeb_integrations/channel/qikchat/`
- `validate_message.py` - Validates incoming webhook data
- `convert_message.py` - Converts Qikchat format to BYOeB internal format

**Example Flow**:
```
User: "What are side effects of radiotherapy?" 
↓
Qikchat Webhook: POST /webhook/qikchat
{
  "from": "919739811075",
  "text": {"body": "What are side effects of radiotherapy?"},
  "timestamp": "2025-08-06T11:30:00Z"
}
↓
BYOeB processes message
```

### 2. Message Processing (BYOeB Core)
**What happens**: BYOeB converts webhook data into internal message context

**Code Location**: `byoeb/byoeb/services/channel/qikchat.py`
- `create_conv()` - Creates conversation context from webhook
- Converts phone number, message text, timestamp into BYOeB format

**Key Function**:
```python
def create_conv(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
    phone_number = message_data.get('from', '')
    message_body = message_data.get('text', {}).get('body', '')
    # Creates internal BYOeB message context
```

### 3. Oncology Knowledge Base Query
**What happens**: BYOeB queries the oncology knowledge base to find relevant answer

**Code Location**: 
- `csv_to_kb.py` - Loads 234 oncology Q&A pairs into ChromaDB
- `local_kb_loader.py` - Handles knowledge base queries
- ChromaDB vector store with oncology data

**Process**:
```
User Question: "What are side effects of radiotherapy?"
↓
Vector Search in ChromaDB oncology knowledge base
↓
Find best matching Q&A pair
↓
Return: "Common side effects include skin irritation, fatigue..."
```

### 4. Response Preparation (24-Hour Rule Logic)
**What happens**: BYOeB decides whether to send template or free-form message

**Code Location**: `qikchat_service_enhanced.py`
- `_is_within_24_hour_window()` - Checks if user replied within 24 hours
- `_should_use_template()` - Decides template vs free-form
- `prepare_oncology_response()` - Creates appropriate response

**Decision Logic**:
```python
if user_last_reply > 24_hours_ago:
    # Use approved template message ($0.86 cost)
    return template_message
else:
    # Use free-form oncology response ($0.00 cost)
    return oncology_text_message
```

### 5. Message Sending (Qikchat API)
**What happens**: BYOeB sends response back to user via Qikchat API

**Code Location**: `byoeb-integrations/byoeb_integrations/channel/qikchat/`
- `qikchat_client.py` - HTTP client for Qikchat API
- `request_payload.py` - Formats message requests

**API Call**:
```python
# Template Message (24+ hours)
{
  "to_contact": "919739811075",
  "type": "template",
  "template": {
    "name": "testing",
    "language": "en", 
    "components": []
  }
}

# Free-form Message (within 24h)
{
  "to_contact": "919739811075", 
  "type": "text",
  "text": {
    "body": "🏥 **BYOeB Oncology Assistant**\n\nCommon side effects include..."
  }
}
```

## Key Integration Points

### A. Webhook Handler
**File**: `byoeb/byoeb/apis/channel/qikchat.py` (to be created)
**Purpose**: Receives Qikchat webhooks
```python
@app.post("/webhook/qikchat")
async def receive_qikchat_message(request):
    # 1. Validate webhook signature
    # 2. Extract message data
    # 3. Pass to QikchatService for processing
```

### B. Service Layer
**File**: `byoeb/byoeb/services/channel/qikchat.py`
**Purpose**: Main business logic
```python
class QikchatService:
    def prepare_requests() -> List[Dict]:
        # Decides template vs free-form based on 24h rule
        
    def send_requests() -> List[Dict]:
        # Sends messages via QikchatClient
        
    def create_conv() -> Dict:
        # Converts webhook to internal format
```

### C. Integration Layer
**File**: `byoeb-integrations/byoeb_integrations/channel/qikchat/`
**Purpose**: Qikchat-specific implementations
- **qikchat_client.py**: HTTP API client
- **request_payload.py**: Message formatting
- **validate_message.py**: Webhook validation

### D. Knowledge Base
**File**: `local_kb_loader.py`, `csv_to_kb.py`
**Purpose**: Oncology expertise
- 234 Q&A pairs about cancer treatment, radiotherapy, side effects
- Vector search for relevant answers
- ChromaDB storage

## Critical Business Logic: 24-Hour Rule

### Problem
WhatsApp Business API restricts free-form messages:
- **Within 24 hours** of user's last reply: Free-form messages allowed ($0.00)
- **After 24+ hours**: Only approved templates allowed ($0.86 each)

### Solution Implementation
```python
def _should_use_template(self, phone_number: str) -> bool:
    last_interaction = self.get_last_user_interaction(phone_number)
    if not last_interaction:
        return True  # First contact - use template
    
    time_since_last = datetime.now() - last_interaction
    return time_since_last > timedelta(hours=24)
```

### Cost Impact
- **Template message**: $0.86 per message (re-engagement)  
- **Free-form message**: $0.00 (active conversation)
- **Optimal strategy**: Use templates only when necessary

## Data Flow Summary

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   User WhatsApp │───▶│   Qikchat API    │───▶│  BYOeB Webhook  │
│                 │    │                  │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                         │
                                                         ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   User receives │◀───│   Qikchat API    │◀───│ BYOeB Response  │
│   response      │    │                  │    │ (Template/Text) │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                         ▲
                                                         │
                                               ┌─────────────────┐
                                               │ Oncology KB     │
                                               │ (234 Q&A pairs) │
                                               └─────────────────┘
```

## Testing Strategy

### Local Testing (No API Costs)
- `test_oncobot_local.py` - Mock all API calls
- `template_logic_demo.py` - Test 24-hour rule logic
- Test oncology Q&A scenarios without charges

### Minimal Real Testing ($0.86)
1. Send one template message to your WhatsApp
2. Reply to start 24-hour window  
3. Test one oncology question (free)
4. Total cost: ~$0.86

## Configuration Files

### Environment Variables (`keys.env`)
```
QIKCHAT_API_KEY=04zg-Ir9t-kfaZ
QIKCHAT_VERIFY_TOKEN=byoeb_qikchat_verify_token_2025
```

### Templates (Qikchat Dashboard)
- **"testing"** (MARKETING): "Hello world" 
- **"test"** (UTILITY): "Thanks for shopping with us..."

## Next Steps for Full Integration

1. **Update Service Layer**: Add 24-hour logic to existing `qikchat.py`
2. **Create Webhook Endpoint**: Handle incoming Qikchat webhooks
3. **Connect Knowledge Base**: Link ChromaDB oncology data
4. **Deploy & Test**: Start with 1-2 real messages
5. **Create Medical Templates**: Get oncology-specific templates approved

## File Structure Overview
```
byoeb-v1/
├── byoeb/byoeb/services/channel/qikchat.py          # Main service logic
├── byoeb-integrations/channel/qikchat/              # Qikchat implementations  
│   ├── qikchat_client.py                           # API client
│   ├── request_payload.py                          # Message formatting
│   └── validate_message.py                         # Webhook validation
├── csv_to_kb.py                                    # Knowledge base loader
├── local_kb_loader.py                              # KB query handler
└── keys.env                                        # Configuration
```

This integration allows BYOeB to provide oncology expertise through WhatsApp while minimizing costs through intelligent template usage.
