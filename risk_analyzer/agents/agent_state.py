from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class AgentState(BaseModel):
    input_contract:str
    errors: List[str] = Field(default_factory=list)
    message: Optional[str] = None
    feedback: Optional[str] = None
    summary: Optional[str] = None
    risk_analysis_report: Optional[Dict[str, Any]] = None
    status: Optional[str] = None # "failed" | "in_progress" | "success"

