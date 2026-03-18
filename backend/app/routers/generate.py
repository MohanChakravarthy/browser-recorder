import logging

from fastapi import APIRouter, Request, HTTPException

from app.config import settings
from app.models.scripts import GenerateResponse
from app.services.action_preprocessor import ActionPreprocessor
from app.services.action_recorder import ActionRecorder
from app.services.script_generator import ScriptGenerator
from app.services.template_generator import TemplateGenerator

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/api/generate", response_model=GenerateResponse)
async def generate_scripts(request: Request) -> GenerateResponse:
    """
    Generate automation scripts from recorded actions.

    Takes the recorded actions from the current session, preprocesses them,
    and uses GPT-4o to generate Playwright and Robot Framework scripts.
    """
    action_recorder: ActionRecorder = request.app.state.action_recorder
    browser_manager = request.app.state.browser_manager

    # Get recorded actions
    raw_actions = action_recorder.get_actions()
    if not raw_actions:
        raise HTTPException(
            status_code=400,
            detail="No actions recorded. Start recording, perform actions, then stop recording before generating scripts.",
        )

    # Preprocess actions
    preprocessor = ActionPreprocessor()
    processed_actions = preprocessor.process(raw_actions)

    if not processed_actions:
        raise HTTPException(
            status_code=400,
            detail="No meaningful actions found after preprocessing.",
        )

    # Get the starting URL — use the URL snapshot from when recording began
    starting_url = action_recorder.start_url or browser_manager.get_current_url()

    # Generate scripts
    if settings.AI_MODE.lower() == "on":
        if not settings.GEMINI_API_KEY:
            raise HTTPException(
                status_code=500,
                detail="GEMINI_API_KEY not configured. Set it in the .env file.",
            )
        generator = ScriptGenerator(api_key=settings.GEMINI_API_KEY)
        try:
            scripts = await generator.generate(processed_actions, starting_url)
        except Exception as e:
            logger.error(f"Script generation failed: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Script generation failed: {str(e)}",
            )
    else:
        template_gen = TemplateGenerator()
        scripts = template_gen.generate(processed_actions, starting_url)

    return GenerateResponse(
        scripts=scripts,
        action_count=len(processed_actions),
    )
