"""Entry point that configures the event loop before uvicorn starts."""
import asyncio
import sys

# Must be set BEFORE uvicorn creates its event loop
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        loop="none",  # Don't let uvicorn override the loop policy
    )
