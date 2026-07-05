"""Starts the Beer Distribution Game simulator (FastAPI backend + static frontend
served from the same process) and shuts down cleanly on Ctrl+C."""

import uvicorn

HOST = "127.0.0.1"
PORT = 8010


def hyperlink(url: str) -> str:
    # OSC 8 terminal hyperlink; terminals that don't support it just show the URL text.
    return f"\033]8;;{url}\033\\{url}\033]8;;\033\\"


def main() -> None:
    base = f"http://{HOST}:{PORT}"
    print()
    print("Beer Distribution Game simulator")
    print(f"  App:      {hyperlink(base)}")
    print(f"  API docs: {hyperlink(base + '/docs')}")
    print()
    print("Press Ctrl+C to stop.")
    print()

    config = uvicorn.Config("app.main:app", host=HOST, port=PORT, log_level="info")
    server = uvicorn.Server(config)
    try:
        server.run()
    except KeyboardInterrupt:
        pass
    finally:
        print("\nStopped -- server and all connections closed.")


if __name__ == "__main__":
    main()
