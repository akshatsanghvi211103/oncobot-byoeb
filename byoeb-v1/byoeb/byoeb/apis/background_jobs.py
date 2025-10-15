import logging
import os
import subprocess
import pytz
import byoeb.chat_app.configuration.dependency_setup as dependency_setup
from io import BytesIO
from azure.identity import DefaultAzureCredential
from datetime import datetime
from fastapi import APIRouter, Request
from croniter import croniter
from fastapi.responses import JSONResponse
from fastapi import Form, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import StreamingResponse
from byoeb_integrations.media_storage.azure.async_azure_blob_storage import AsyncAzureBlobStorage

REGISTER_API_NAME = 'background_api'

background_apis_router = APIRouter()
_logger = logging.getLogger(REGISTER_API_NAME)

current_dir = os.path.dirname(os.path.abspath(__file__))
jobs_path = os.path.join(current_dir, '..', 'background_jobs')
jobs_path = os.path.normpath(jobs_path)
template_dir = os.path.join(current_dir, 'ui_templates')
templates = Jinja2Templates(directory=template_dir)
# file_path = "asha_data.xlsx"
# account_url = "https://khushibabyashastorage.blob.core.windows.net"
# container_name = "ashacontainer"

# Store application start time to track intervals
app_start_time = datetime.now(pytz.timezone("Asia/Kolkata"))
last_expert_reminder = None
last_kb_update = None

# Available background jobs (will be selectively executed based on timing)
available_jobs = {
    "expert_reminder": f"python {jobs_path}/send_expert_reminder.py && exit",
    "kb_update": f"python {jobs_path}/update_kb_with_corrections.py && exit"
}
pids = []

# @background_apis_router.get("/asha_logs", response_class=HTMLResponse)
# async def form_get(request: Request):
#     return templates.TemplateResponse("index.html", {"request": request})

# @background_apis_router.post("/asha_logs", response_class=HTMLResponse)
# async def form_post(request: Request, start_datetime: str = Form(...), end_datetime: str = Form(...)):
#     start = datetime.strptime(start_datetime, "%Y-%m-%dT%H:%M")
#     end = datetime.strptime(end_datetime, "%Y-%m-%dT%H:%M")
    
#     start_unix = str(start.timestamp())
#     end_unix = str(end.timestamp())
#     media_storage = AsyncAzureBlobStorage(
#         container_name=container_name,
#         account_url=account_url,
#         credentials=DefaultAzureCredential()
#     )

#     ashas_df = await fetch_daily_logs(
#         start_timestamp=start_unix,
#         end_timestamp=end_unix
#     )
    
#     # Save to excel for download
#     ashas_df.to_excel(file_path, index=False)
#     blob_file_name = f"logs/{os.path.basename(file_path)}"
#     await media_storage.adelete_file(
#         file_name=blob_file_name
#     )
#     await media_storage.aupload_file(
#         file_path=file_path,
#         file_name=blob_file_name
#     )
#     await media_storage._close()
#     # Render HTML
#     df_html = ashas_df.to_html(classes="table table-bordered", index=False)
#     return templates.TemplateResponse("index.html", {
#         "request": request,
#         "table": df_html,
#         "show_download": True
#     })

# @background_apis_router.get("/download")
# async def download_excel():
#     media_storage = AsyncAzureBlobStorage(
#         container_name=container_name,
#         account_url=account_url,
#         credentials=DefaultAzureCredential()
#     )
#     _, asha_data = await media_storage.adownload_file(
#         file_name=f"logs/{os.path.basename(file_path)}"
#     )
#     await media_storage._close()
#     stream = BytesIO(asha_data.data)  # or just use Filedata if already BytesIO
#     return StreamingResponse(
#         stream,
#         media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
#         headers={
#             "Content-Disposition": "attachment; filename=downloaded.xlsx"
#         }
#     )
#     # return FileResponse(
#     #     path=file_path,
#     #     media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
#     #     filename="data.xlsx",
#     # )

@background_apis_router.post("/schedule")
async def schedule(request: Request):
    global last_expert_reminder, last_kb_update

    # Clean up completed processes
    for pid in pids[:]:
        if pid["pid"] == "completed":
            pids.remove(pid)
            continue
            
        try:
            os.kill(pid["pid"], 0)
        except OSError:
            _logger.info(f"Process {pid['pid']} is not running")
            pids.remove(pid)
        else:
            _logger.info(f"Process {pid['pid']} is running")
    
    # Get current time in IST
    now = datetime.now(pytz.timezone("Asia/Kolkata"))
    print(f"🕐 Current time: {now}")
    print(f"📅 App started at: {app_start_time}")
    
    jobs_to_run = []
    
    # Check Expert Reminder Logic (Every 3 hours, skip night 10PM-6AM)
    should_run_expert_reminder = False
    current_hour = now.hour
    
    # Skip night hours (10PM to 6AM)
    if not (23 <= current_hour or current_hour < 6):
        if last_expert_reminder is None:
            # First run - run immediately if during day hours
            should_run_expert_reminder = True
            print("🔔 Expert reminder: First run during day hours")
        else:
            # Check if 3 hours have passed since last run
            hours_since_last = (now - last_expert_reminder).total_seconds() / 3600
            if hours_since_last >= 3:
                should_run_expert_reminder = True
                print(f"🔔 Expert reminder: {hours_since_last:.1f} hours since last run")
            else:
                print(f"⏰ Expert reminder: Only {hours_since_last:.1f} hours since last run (need 3)")
    else:
        print(f"🌙 Expert reminder: Skipping night hours (current: {current_hour}:00)")
    
    if should_run_expert_reminder:
        jobs_to_run.append(("expert_reminder", available_jobs["expert_reminder"]))
        last_expert_reminder = now
    
    # Check KB Update Logic (Daily at 3AM)
    should_run_kb_update = False
    if current_hour == 22:  # 3AM
        if last_kb_update is None or last_kb_update.date() != now.date():
            should_run_kb_update = True
            print("🗃️ KB update: Daily 3AM run")
        else:
            print("�️ KB update: Already ran today at 3AM")
    else:
        print(f"�️ KB update: Waiting for 3AM (current: {current_hour}:00)")
    
    if should_run_kb_update:
        jobs_to_run.append(("kb_update", available_jobs["kb_update"]))
        last_kb_update = now
    
    # Execute selected jobs
    if not jobs_to_run:
        print("⏸️ No jobs scheduled to run at this time")
        return JSONResponse(
            content={"message": "No jobs scheduled", "current_time": str(now)},
            status_code=200
        )
    
    print(f"🚀 Running {len(jobs_to_run)} job(s): {[job[0] for job in jobs_to_run]}")
    
    for job_name, command in jobs_to_run:
        print(f"🚀 Executing {job_name}: {command}")
        try:
            # Set up environment variables for UTF-8 encoding
            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'
            env['PYTHONLEGACYWINDOWSSTDIO'] = '0'
            
            # Run the command
            result = subprocess.run(
                command, 
                shell=True, 
                capture_output=True, 
                text=True, 
                encoding='utf-8',
                errors='replace',
                env=env,
                timeout=300  # 5 minute timeout
            )
            
            print(f"✅ {job_name} exit code: {result.returncode}")
            if result.stdout:
                print(f"📤 {job_name} stdout (first 3000 chars):\n{result.stdout[:3000]}")
            if result.stderr:
                print(f"❌ {job_name} stderr:\n{result.stderr}")
                
            # Track completed process
            pids.append({
                "pid": "completed",
                "job_name": job_name,
                "command": command,
                "exit_code": result.returncode,
                "executed_at": str(now),
                "stdout": result.stdout[:1000] if result.stdout else None,
                "stderr": result.stderr[:1000] if result.stderr else None
            })
            
        except subprocess.TimeoutExpired:
            print(f"⏰ {job_name} timed out after 5 minutes")
        except Exception as e:
            print(f"❌ Error executing {job_name}: {e}")

    return JSONResponse(
        content={
            "executed_jobs": [job[0] for job in jobs_to_run],
            "current_time": str(now),
            "last_expert_reminder": str(last_expert_reminder) if last_expert_reminder else "Never",
            "last_kb_update": str(last_kb_update) if last_kb_update else "Never",
            "next_kb_update": "Tomorrow at 3AM" if current_hour >= 3 else "Today at 3AM"
        },
        status_code=202
    )