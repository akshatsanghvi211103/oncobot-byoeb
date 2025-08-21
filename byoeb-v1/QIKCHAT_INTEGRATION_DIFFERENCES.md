# Qikchat Integration vs WhatsApp Integration - Key Differences

## Overview
This document outlines the key differences between the Qikchat integration and the existing WhatsApp integration in the BYOeB system.

## Directory Structure Comparison

### WhatsApp Structure:
```
byoeb-integrations/channel/whatsapp/
├── __init__.py
├── register.py
├── request_payload.py  
├── validate_message.py
├── convert_message.py
└── meta/
    └── async_whatsapp_client.py
```

### Qikchat Structure:
```
byoeb-integrations/channel/qikchat/
├── __init__.py
├── register.py
├── request_payload.py
├── validate_message.py
├── convert_message.py
└── qikchat_client.py
```

## 1. Authentication & Configuration

### WhatsApp Authentication:
- **Multiple tokens required:**
  - `WHATSAPP_VERIFICATION_TOKEN` - for webhook verification
  - `WHATSAPP_AUTH_TOKEN` - for API calls
  - `WHATSAPP_PHONE_NUMBER_ID` - for sending messages
- **Complex authentication flow**

### Qikchat Authentication:
- **Single API key:**
  - `QIKCHAT_API_KEY` - for all API operations
  - `QIKCHAT_VERIFY_TOKEN` - for webhook verification only
- **Simpler authentication using Bearer token**

## 2. Webhook Registration

### WhatsApp (`register.py`):
```python
# Required parameters:
__REQUESST_MODE = "hub.mode"           # Must be "subscribe"
__REQUEST_TOKEN = "hub.verify_token"   # Verification token
__REQUEST_CHALLENGE = "hub.challenge"  # Challenge to return

# Complex validation with mode checking
if mode != self.__MODE_TYPE:
    return error_response
```

### Qikchat (`register.py`):
```python
# Simplified parameters:
__REQUEST_TOKEN = "verify_token"       # No "hub." prefix
__REQUEST_CHALLENGE = "challenge"      # Direct challenge

# No mode validation required
# Direct token and challenge verification
```

## 3. Message Request Format

### WhatsApp Message Structure:
```python
# Complex nested structure
wa_message = {
    "messaging_product": "whatsapp",     # Required product field
    "to": phone_number_id,               # Recipient
    "type": "text",                      # Message type
    "text": {                            # Nested text object
        "body": message_text
    },
    "context": {                         # Reply context (if any)
        "message_id": reply_id
    }
}
```

### Qikchat Message Structure:
```python
# Simpler flat structure
qik_message = {
    "from": phone_number,                # Sender (in body, not URL)
    "to": phone_number,                  # Recipient  
    "type": "text",                      # Message type
    "text": message_text,                # Direct text field
    "context": {                         # Reply context (if any)
        "message_id": reply_id
    }
}
```

## 4. API Endpoints

### WhatsApp API:
- **Base URL:** `https://graph.facebook.com/v17.0/`
- **Send Message:** `/{phone_number_id}/messages`
- **Media Upload:** `/{phone_number_id}/media`
- **Uses phone_number_id in URL path**

### Qikchat API:
- **Base URL:** `https://api.qikchat.in/api/v1`
- **Send Message:** `/messages`
- **Media Upload:** `/media/upload`
- **Uses 'from' field in request body instead of URL path**

## 5. Message Validation

### WhatsApp Validation:
```python
# Complex nested structure validation
regular_message = incoming_message.WhatsAppRegularMessageBody.model_validate(original_message)
message_type = regular_message.entry[0].changes[0].value.messages[0].type
```

### Qikchat Validation:
```python
# Direct field validation
message_type = original_message.get("type")
required_fields = ["type", "from", "timestamp"]
# Simple field existence checking
```

## 6. Message Conversion

### WhatsApp Message Conversion:
```python
# Nested field extraction
timestamp = regular_message.entry[0].changes[0].value.messages[0].timestamp
from_number = regular_message.entry[0].changes[0].value.messages[0].from_
message_text = regular_message.entry[0].changes[0].value.messages[0].text.body
```

### Qikchat Message Conversion:
```python
# Direct field extraction
timestamp = original_message.get("timestamp")
from_number = original_message.get("from")
message_text = original_message.get("text", "")
```

## 7. HTTP Client Implementation

### WhatsApp Client:
- Uses Meta's Graph API
- Complex authentication with multiple tokens
- Separate endpoints for different operations
- Complex response parsing

### Qikchat Client:
- Single API key authentication
- Unified endpoint structure
- Simpler response format
- Direct JSON response handling

## 8. Service Layer Differences

### WhatsApp Service (`whatsapp.py`):
```python
class WhatsAppService(BaseChannelService):
    __client_type = "whatsapp"
    
    # Uses WhatsApp-specific request functions
    wa_text_message = wa_req_payload.get_whatsapp_text_request_from_byoeb_message(byoeb_message)
    
    # Complex response handling with WhatsAppResponse objects
    responses = [response for result in results for response in result]
```

### Qikchat Service (`qikchat.py`):
```python
class QikchatService(BaseChannelService):
    __client_type = "qikchat"
    
    # Uses Qikchat-specific request functions
    qik_text_message = qik_req_payload.get_qikchat_text_request_from_byoeb_message(byoeb_message)
    
    # Simpler response handling with Dict objects
    responses.append(result)
```

## 9. Configuration Changes Needed

### Environment Variables:
```env
# Remove WhatsApp variables:
# WHATSAPP_VERIFICATION_TOKEN=xxx
# WHATSAPP_AUTH_TOKEN=xxx  
# WHATSAPP_PHONE_NUMBER_ID=xxx

# Add Qikchat variables:
QIKCHAT_API_KEY=your_qikchat_api_key_here
QIKCHAT_VERIFY_TOKEN=your_verification_token_here
QIKCHAT_WEBHOOK_URL=https://your-domain.com/webhook/qikchat
```

### App Configuration:
```python
# Change client type from "whatsapp" to "qikchat" in:
# - dependency_setup.py
# - chat_app configuration
# - channel factory settings
```

## 10. Key Advantages of Qikchat Integration

1. **Simpler Authentication:** Single API key vs multiple tokens
2. **Cleaner Message Format:** Flat structure vs nested objects
3. **Direct Field Access:** No complex path navigation
4. **Unified API:** Single endpoint for message operations
5. **Easier Debugging:** Simpler request/response structure
6. **Less Boilerplate:** Fewer validation layers needed

## Next Steps for Implementation

1. **Get Qikchat API credentials**
2. **Update configuration files** to use Qikchat instead of WhatsApp
3. **Test message sending/receiving** with the new integration
4. **Deploy webhook endpoint** for Qikchat message reception
5. **Verify oncology knowledge base** works with Qikchat channel

The integration maintains the same BYOeB interface while providing a much simpler and cleaner implementation compared to WhatsApp's complex API structure.
