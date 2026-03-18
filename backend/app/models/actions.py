from typing import Optional, Literal
from pydantic import BaseModel


class ElementContext(BaseModel):
    tag: Optional[str] = None
    id: Optional[str] = None
    class_name: Optional[str] = None
    name: Optional[str] = None
    aria_label: Optional[str] = None
    aria_labelledby: Optional[str] = None
    role: Optional[str] = None
    text_content: Optional[str] = None
    title: Optional[str] = None
    data_testid: Optional[str] = None
    data_id: Optional[str] = None
    data_cy: Optional[str] = None
    data_qa: Optional[str] = None
    placeholder: Optional[str] = None
    href: Optional[str] = None
    input_type: Optional[str] = None
    value: Optional[str] = None
    css_selector: Optional[str] = None
    xpath: Optional[str] = None
    locator_strategy: Optional[str] = None
    container_css: Optional[str] = None


class RawAction(BaseModel):
    action_type: Literal[
        "click", "dblclick", "type", "keydown", "scroll", "navigate", "wait"
    ]
    timestamp: float
    x: Optional[int] = None
    y: Optional[int] = None
    key: Optional[str] = None
    text: Optional[str] = None
    url: Optional[str] = None
    element: Optional[ElementContext] = None


class ProcessedAction(BaseModel):
    action_type: str
    description: str
    element: Optional[ElementContext] = None
    value: Optional[str] = None
    url: Optional[str] = None
    wait_time: Optional[float] = None
