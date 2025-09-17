import time
import datetime
import logging

def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
    while True:
        now = datetime.datetime.utcnow().isoformat()
        logging.info(f"Ping at {now}")
        # 👇 put your actual job logic here
        # e.g., requests.get("https://example.com/health")
        time.sleep(1)

if __name__ == "__main__":
    main()
