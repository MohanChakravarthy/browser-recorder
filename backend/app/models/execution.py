from typing import Literal
from pydantic import BaseModel


class ExecuteRequest(BaseModel):
    script_type: Literal["playwright_python", "robot_framework", "robot_selenium"]
    script_content: str
