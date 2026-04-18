import time

from server.tasks.broker import list_registered_tasks


def main() -> None:
    registered = ", ".join(list_registered_tasks())
    print(f"KnowLink worker scaffold registered tasks: {registered}")
    while True:
        print("KnowLink worker placeholder is running.")
        time.sleep(60)


if __name__ == "__main__":
    main()
