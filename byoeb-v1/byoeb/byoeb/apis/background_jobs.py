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

background_jobs = [
    # f"*/30 * * * * python {jobs_path}/consensus/respond_with_consensus.py",
    # f"00 8-20 * * * python {jobs_path}/consensus/send_query_to_expert.py",
    f"*/20 * * * * python {jobs_path}/send_expert_reminder.py && exit"  # Every 20 minutes
]
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

    # Clean up completed processes and check running ones
    for pid in pids[:]:  # Copy list to avoid modification during iteration
        if pid["pid"] == "completed":
            # Skip completed processes
            pids.remove(pid)
            continue
            
        try:
            os.kill(pid["pid"], 0)
        except OSError:
            _logger.info(f"Process {pid['pid']} is not running")
            pids.remove(pid)
        else:
            _logger.info(f"Process {pid['pid']} is running")
    
    # Get the current time in IST
    now = datetime.now(pytz.timezone("Asia/Kolkata"))
    print(f"🕐 Current time: {now}")
    # Round the time to the nearest half hour
    minutes = (now.minute // 5) * 5
    rounded_now = now.replace(minute=minutes, second=0, microsecond=0)
    for background_job in background_jobs:
        # Parse the cron schedule
        parts = background_job.strip().split()
        cron_expression = " ".join(parts[:5])
        command = " ".join(parts[5:])
        
        iter = croniter(cron_expression, now)
        prev_time = iter.get_prev(datetime)

        print(f"🔍 Command: {command}")
        print(f"🔍 Previous execution time: {prev_time}")

        # Run the job immediately since external scheduler handles timing
        if True:  # Always run when endpoint is hit
            print(f"🚀 Running command: {command}")
            try:
                # Set up environment variables for UTF-8 encoding
                env = os.environ.copy()
                env['PYTHONIOENCODING'] = 'utf-8'
                env['PYTHONLEGACYWINDOWSSTDIO'] = '0'
                
                # Run the command and capture output for debugging with UTF-8 encoding
                result = subprocess.run(
                    command, 
                    shell=True, 
                    capture_output=True, 
                    text=True, 
                    encoding='utf-8',
                    errors='replace',  # Replace problematic characters instead of failing
                    env=env,  # Use the modified environment
                    timeout=300  # 5 minute timeout
                )
                
                print(f"✅ Command exit code: {result.returncode}")
                if result.stdout:
                    print(f"📤 Command stdout (first 5000 chars):\n{result.stdout[:5000]}")
                if result.stderr:
                    print(f"❌ Command stderr:\n{result.stderr}")
                    
                # Still track the process for reference (though it's already completed)
                pids.append({
                    "pid": "completed",
                    "command": command,
                    "exit_code": result.returncode,
                    "stdout": result.stdout[:1000] if result.stdout else None,  # Truncate for JSON response
                    "stderr": result.stderr[:1000] if result.stderr else None
                })
                
            except subprocess.TimeoutExpired:
                print(f"⏰ Command timed out after 5 minutes: {command}")
            except Exception as e:
                print(f"❌ Error executing command: {e}")
                print(f"❌ Command was: {command}")

    return JSONResponse(
        content=pids,
        status_code=202
    )