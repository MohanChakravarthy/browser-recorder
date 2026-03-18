from pydantic import BaseModel


class ScriptOutput(BaseModel):
    playwright_python: str
    robot_framework: str
    robot_selenium: str


class GenerateResponse(BaseModel):
    scripts: ScriptOutput
    action_count: int
