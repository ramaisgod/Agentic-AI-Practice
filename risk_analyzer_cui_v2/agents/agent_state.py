# agent_state.py
from pydantic import BaseModel, Field, root_validator
from typing import List, Optional, Dict, Any
from datetime import datetime
from core.logger import logger


class Message(BaseModel):
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None

    # Log whenever a message is created
    @root_validator(pre=True)
    def log_message_creation(cls, values):
        try:
            role = values.get("role")
            content = values.get("content", "")
            safe_preview = (content[:150] + "...") if len(content) > 150 else content
            logger.debug("Message created: role=%s | content_preview=%s", role, safe_preview)
        except Exception:
            logger.exception("Failed logging message creation")
        return values


class AgentState(BaseModel):
    user_id: str
    input_contract: str
    messages: List[Message] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    message: Optional[str] = None
    feedback: Optional[str] = None
    summary: Optional[str] = None
    risk_analysis_report: Optional[Dict[str, Any]] = None
    status: Optional[str] = None  # "failed" | "in_progress" | "success"
    quality_score: int = 0
    thread_id: Optional[str] = None
    approved: Optional[bool] = None
    refinement_count: int = 0
    human_input: bool = False

    # Log state initialization
    @root_validator(pre=True)
    def log_state_initialization(cls, values):
        try:
            logger.info("Initializing AgentState for user_id=%s thread_id=%s",
                        values.get("user_id"), values.get("thread_id"))
            logger.debug("Initial AgentState values: %s", values)
        except Exception:
            logger.exception("Failed logging AgentState initialization")
        return values

    # Custom helper: add message with logging
    def add_message(self, role: str, content: str, metadata: Dict[str, Any] = None):
        try:
            logger.info("Adding message to AgentState: role=%s", role)
            preview = (content[:150] + "...") if len(content) > 150 else content
            logger.debug("Message content preview: %s", preview)

            msg = Message(role=role, content=content, timestamp=datetime.utcnow(), metadata=metadata)
            self.messages.append(msg)

            logger.debug("Total messages in state now: %d", len(self.messages))
        except Exception:
            logger.exception("Failed to add message to AgentState")

    # Custom helper: add error with logging
    def add_error(self, error_msg: str):
        try            :
            logger.warning("Adding error to AgentState: %s", error_msg)
            self.errors.append(error_msg)
            logger.debug("Total errors in state now: %d", len(self.errors))
        except Exception:
            logger.exception("Failed to append error to AgentState")

    # Custom helper: update status with logging
    def set_status(self, status: str):
        try:
            logger.info("Updating AgentState status: %s → %s", self.status, status)
            self.status = status
        except Exception:
            logger.exception("Failed updating status")

    # Custom helper: change quality score with logging
    def set_quality_score(self, score: int):
        try:
            logger.info("Setting quality_score=%s", score)
            self.quality_score = score
        except Exception:
            logger.exception("Failed updating quality_score")

    # Custom helper: update summary with logging
    def set_summary(self, summary_text: str):
        try:
            preview = (summary_text[:200] + "...") if len(summary_text) > 200 else summary_text
            logger.info("Updating summary (preview): %s", preview)
            self.summary = summary_text
        except Exception:
            logger.exception("Failed updating summary")

    # Custom helper: update risk analysis report
    def set_risk_report(self, report: Dict[str, Any]):
        try:
            logger.info("Updating risk_analysis_report")
            logger.debug("Risk report data: %s", report)
            self.risk_analysis_report = report
        except Exception:
            logger.exception("Failed updating risk_analysis_report")

    # Custom helper: increment refinement count
    def increment_refinement(self):
        try:
            logger.info("Incrementing refinement_count: %s → %s",
                        self.refinement_count, self.refinement_count + 1)
            self.refinement_count += 1
        except Exception:
            logger.exception("Failed to increment refinement_count")
