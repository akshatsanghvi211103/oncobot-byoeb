import os
import json
from dotenv import load_dotenv

# Get the directory of the current script
current_dir = os.path.dirname(os.path.abspath(__file__))
app_config_path = os.path.join(current_dir, '..', 'app_config.json')
app_config_path = os.path.normpath(app_config_path)
app_config = None
with open(app_config_path, 'r', encoding='utf-8') as file:
    app_config = json.load(file)

bot_config_path = os.path.join(current_dir, '..', 'bot_config.json')
bot_config_path = os.path.normpath(bot_config_path)
bot_config = None
with open(bot_config_path, 'r', encoding='utf-8') as file:
    bot_config = json.load(file)

environment_path = os.path.join(current_dir, '../../..', 'keys.env')
environment_path = os.path.normpath(environment_path)
load_dotenv(environment_path)

# Environment variables
# Whatsapp
env_whatsapp_token = os.getenv("WHATSAPP_VERIFICATION_TOKEN")
env_whatsapp_auth_token = os.getenv("WHATSAPP_AUTH_TOKEN")
env_whatsapp_phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")

# Qikchat
env_qikchat_api_key = os.getenv("QIKCHAT_API_KEY")
env_qikchat_verify_token = os.getenv("QIKCHAT_VERIFY_TOKEN")
env_qikchat_webhook_url = os.getenv("QIKCHAT_WEBHOOK_URL")

# OpenAI
env_openai_api_key = os.getenv("OPENAI_API_KEY")
env_openai_org_id = os.getenv("OPENAI_ORG_ID")

# Azure cosmos db
env_mongo_db_connection_string = os.getenv("MONGO_DB_CONNECTION_STRING")