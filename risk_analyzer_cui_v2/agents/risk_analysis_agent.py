# risk_analysis_agent.py
from .agent_state import AgentState
from prompts.risk_analysis_prompt import risk_analysis_prompt
from llm.llm_manager import call_llm
from utils.common import extract_json
from core.logger import logger


class RiskAnalysisAgent:
    def __call__(self, state: AgentState):
        logger.info("RiskAnalysisAgent invoked")
        self.state = state
        self.user_input = state.input_contract
        return self.run_analyzer()

    def run_analyzer(self) -> AgentState:
        logger.info("Starting risk analysis")
        try:
            logger.debug("Incoming state: %s", self.state.model_dump() if hasattr(self.state, "model_dump") else dict(self.state))
        except Exception:
            logger.exception("Failed to dump incoming state for logging")

        # Append feedback to input if present
        try:
            if getattr(self.state, "feedback", None):
                logger.info("Appending feedback to input_contract for analysis")
                self.state.input_contract += f"\nFeedback: {self.state.feedback}"
        except Exception as e:
            logger.exception("Error while appending feedback: %s", e)

        # Build recent context from last 3 messages
        try:
            logger.debug("Building recent_context from last 3 messages")
            recent_context = "\n".join([f"{m.role}: {m.content}" for m in self.state.messages[-3:]])
        except Exception as e:
            logger.exception("Failed to build recent_context: %s", e)
            recent_context = ""

        full_input = f"{recent_context}\nAnalyze: {self.state.input_contract}"
        prompt = risk_analysis_prompt + full_input
        logger.debug("Risk analysis prompt length=%d", len(prompt))

        try:
            logger.info("Calling Gemini LLM for risk analysis...")
            resp_text = call_llm(prompt)
            if isinstance(resp_text, str):
                resp_text = resp_text.strip()
            logger.info("LLM risk analysis response received")
            logger.debug("Raw LLM response preview: %s", (resp_text[:500] + "...") if isinstance(resp_text, str) and len(resp_text) > 500 else resp_text)

            # Try to extract JSON from response
            try:
                resp_json = extract_json(resp_text) or {}
                logger.debug("Extracted JSON from LLM response: %s", resp_json)
            except Exception as e:
                logger.exception("Failed to extract JSON from LLM response: %s", e)
                resp_json = {}

            # Persist results into state
            self.state.risk_analysis_report = resp_json
            self.state.status = "in_progress"
            human_flag = bool(resp_json.get("human_input"))
            self.state.human_input = human_flag
            self.state.message = "Human input required" if human_flag else ""
            logger.info("Risk analysis completed; human_input=%s", human_flag)
            logger.debug("State after analysis: %s", self.state.model_dump() if hasattr(self.state, "model_dump") else dict(self.state))

        except Exception as e:
            logger.exception("Error during risk analysis: %s", e)
            # ensure errors list exists
            try:
                self.state.errors = getattr(self.state, "errors", [])
                self.state.errors.append(f"Analysis error: {e}")
            except Exception:
                logger.exception("Failed to append analysis error to state.errors")
            self.state.status = "failed"
            logger.debug("State after failed analysis: %s", self.state.model_dump() if hasattr(self.state, "model_dump") else dict(self.state))

        return self.state
