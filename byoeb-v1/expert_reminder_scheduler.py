#!/usr/bin/env python3
"""
Expert Reminder Cron Scheduler
Hits the /schedule endpoint every 1 minute to trigger expert reminder jobs.
This script should be run as a continuous background process.
"""

import asyncio
import aiohttp
import sys
import os
import time
from datetime import datetime

# Configuration  
# SCHEDULE_ENDPOINT = "http://localhost:5000/schedule"  # Use the port your server is running on
SCHEDULE_ENDPOINT = "https://oncobot-h7fme6hue9f7buds.canadacentral-01.azurewebsites.net/schedule"  # Use the port your server is running on
CHECK_INTERVAL_SECONDS = 10800  # 3 hours (3 * 60 * 60 seconds)
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 5

async def trigger_schedule():
    """
    Send POST request to /schedule endpoint to trigger background jobs.
    """
    try:
        async with aiohttp.ClientSession() as session:
            print(f"📡 Triggering schedule endpoint at {datetime.now()}")
            
            async with session.post(SCHEDULE_ENDPOINT) as response:
                if response.status == 202:
                    result = await response.json()
                    print(f"✅ Schedule triggered successfully!")
                    if "executed_jobs" in result:
                        jobs = result.get("executed_jobs", [])
                        print(f"   Executed jobs: {jobs}")
                        print(f"   Current time: {result.get('current_time', 'Unknown')}")
                    else:
                        print(f"   Response: {result}")
                    return True
                elif response.status == 200:
                    result = await response.json()
                    print(f"✅ Schedule checked - no jobs to run")
                    print(f"   Message: {result.get('message', 'No message')}")
                    print(f"   Current time: {result.get('current_time', 'Unknown')}")
                    return True
                else:
                    print(f"❌ Schedule endpoint returned status: {response.status}")
                    response_text = await response.text()
                    print(f"   Response: {response_text}")
                    return False
                    
    except aiohttp.ClientError as e:
        print(f"❌ Network error triggering schedule: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error triggering schedule: {e}")
        return False

async def main():
    """
    Main loop that triggers the schedule endpoint every minute.
    """
    print(f"🚀 Starting expert reminder cron scheduler")
    print(f"   Target endpoint: {SCHEDULE_ENDPOINT}")
    print(f"   Check interval: {CHECK_INTERVAL_SECONDS} seconds")
    print(f"   Started at: {datetime.now()}")
    print("=" * 50)
    
    consecutive_failures = 0
    
    while True:
        try:
            success = await trigger_schedule()
            
            if success:
                consecutive_failures = 0
                print(f"💤 Sleeping for {CHECK_INTERVAL_SECONDS} seconds...")
            else:
                consecutive_failures += 1
                print(f"⚠️ Failed to trigger schedule (failure #{consecutive_failures})")
                
                if consecutive_failures >= MAX_RETRIES:
                    print(f"❌ Too many consecutive failures ({consecutive_failures})")
                    print(f"   Retrying in {RETRY_DELAY_SECONDS} seconds...")
                    await asyncio.sleep(RETRY_DELAY_SECONDS)
                    consecutive_failures = 0  # Reset counter after delay
            
            # Wait for next iteration
            await asyncio.sleep(CHECK_INTERVAL_SECONDS)
            
        except KeyboardInterrupt:
            print(f"\n🛑 Received interrupt signal - shutting down gracefully")
            break
        except Exception as e:
            print(f"❌ Unexpected error in main loop: {e}")
            consecutive_failures += 1
            await asyncio.sleep(RETRY_DELAY_SECONDS)
    
    print(f"🏁 Expert reminder cron scheduler stopped at {datetime.now()}")

if __name__ == "__main__":
    # Ensure we can import required modules
    try:
        import aiohttp
    except ImportError:
        print("❌ aiohttp not installed. Install with: pip install aiohttp")
        sys.exit(1)
    
    # Run the scheduler
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Scheduler stopped by user")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)