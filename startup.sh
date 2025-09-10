#!/bin/bash
echo "hi there nice to meet you"
pwd
ls -la
pip install -r requirements.txt
exec uvicorn byoeb_v1.byoeb.byoeb.chat_app.run:app --host 0.0.0.0 --port 8000
