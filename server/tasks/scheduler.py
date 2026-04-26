import time


SCHEDULED_JOBS = ("review_refresh", "cache_cleanup", "stuck_task_watchdog")


def main() -> None:
    print(f"KnowLink scheduler scaffold jobs: {', '.join(SCHEDULED_JOBS)}")
    while True:
        print("KnowLink scheduler placeholder is running.")
        time.sleep(60)


if __name__ == "__main__":
    main()
