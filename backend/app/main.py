import asyncio
import logging
import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator

# Windows requires ProactorEventLoop for subprocess support (Playwright needs it)
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import ws, generate, execute, browser
from app.services.action_recorder import ActionRecorder
from app.services.browser_manager import BrowserManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: start and stop the browser manager."""
    logger.info("Starting application...")

    # Initialize services
    browser_manager = BrowserManager()
    action_recorder = ActionRecorder()

    await browser_manager.start()

    # Store in app state for access by routers
    app.state.browser_manager = browser_manager
    app.state.action_recorder = action_recorder

    logger.info("Application started successfully.")
    yield

    # Shutdown
    logger.info("Shutting down application...")
    await browser_manager.stop()
    logger.info("Application shut down.")


app = FastAPI(
    title="Browser Action Recorder & Script Generator",
    description="Record browser actions and generate automation scripts.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(ws.router)
app.include_router(generate.router)
app.include_router(execute.router)
app.include_router(browser.router)


@app.get("/")
async def root() -> dict:
    return {"message": "Browser Action Recorder API", "status": "running"}


@app.get("/health")
async def health() -> dict:
    return {"status": "healthy"}
