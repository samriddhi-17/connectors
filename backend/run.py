"""Local / container entrypoint.

Serves the app with a selector-based event loop on Windows (uvicorn defaults
to ``ProactorEventLoop`` there, which breaks psycopg async connections). The
custom loop factory is used everywhere; on Linux it behaves like the default.
"""
import os

import uvicorn


def main() -> None:
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.environ.get("BACKEND_PORT", "8000")),
        reload=os.environ.get("RELOAD", "").lower() in {"1", "true", "yes"},
        log_level=os.environ.get("LOG_LEVEL", "info").lower(),
        loop="app.loop_factory:selector_loop_factory",
    )


if __name__ == "__main__":
    main()