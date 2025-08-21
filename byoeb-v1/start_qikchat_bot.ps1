# PowerShell script to start both BYOeB applications for Qikchat integration
Write-Host "Starting BYOeB Qikchat Bot..." -ForegroundColor Green

# Function to start a service in a new PowerShell window
function Start-Service {
    param(
        [string]$ServiceName,
        [string]$WorkingDirectory,
        [string]$Command,
        [int]$Port
    )
    
    Write-Host "Starting $ServiceName on port $Port..." -ForegroundColor Yellow
    
    # Create a new PowerShell window for each service
    Start-Process powershell -ArgumentList @(
        "-NoExit",
        "-Command",
        "cd '$WorkingDirectory'; Write-Host 'Starting $ServiceName...' -ForegroundColor Cyan; $Command"
    ) -WindowStyle Normal
    
    Start-Sleep -Seconds 2
}

# Set the base directory
$BaseDir = "c:\Users\t-asanghvi\work\byoeb\byoeb-v1\byoeb"

Write-Host "BYOeB Qikchat Bot Startup" -ForegroundColor Magenta
Write-Host "=========================" -ForegroundColor Magenta
Write-Host ""

# Start Knowledge Base Service (Port 5001)
Start-Service -ServiceName "Knowledge Base Service" -WorkingDirectory "$BaseDir\byoeb\kb_app" -Command "python run.py" -Port 5001

# Start Chat App Service (Port 5000 - handles Qikchat webhooks)
Start-Service -ServiceName "Chat App Service" -WorkingDirectory "$BaseDir\byoeb\chat_app" -Command "python run.py" -Port 5000

Write-Host ""
Write-Host "Services Started!" -ForegroundColor Green
Write-Host "==================" -ForegroundColor Green
Write-Host "Knowledge Base API: http://127.0.0.1:5001" -ForegroundColor Cyan
Write-Host "Chat App (Webhooks): http://127.0.0.1:5000" -ForegroundColor Cyan
Write-Host "Qikchat Webhook URL: http://127.0.0.1:5000/webhook/qikchat" -ForegroundColor Yellow
Write-Host ""
Write-Host "To test the bot:" -ForegroundColor White
Write-Host "1. Make sure your Qikchat webhook URL points to: http://127.0.0.1:5000/webhook/qikchat" -ForegroundColor White
Write-Host "2. Send a WhatsApp message to your Qikchat number" -ForegroundColor White
Write-Host "3. Check the chat app logs for incoming messages and responses" -ForegroundColor White
Write-Host ""
Write-Host "Press any key to continue..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
