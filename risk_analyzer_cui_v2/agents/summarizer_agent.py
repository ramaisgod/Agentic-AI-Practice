# summarizer_agent.py
from .agent_state import AgentState
from prompts.summarizer_prompt import summarizer_prompt
from llm.llm_manager import call_llm
from core.logger import logger
import json


class SummarizerAgent:
    def __call__(self, state: AgentState):
        logger.info("SummarizerAgent invoked")
        self.state = state
        return self.summarize()

    def summarize(self) -> AgentState:
        logger.info("Starting summarization process...")
        try:
            state_dump = self.state.model_dump() if hasattr(self.state, "model_dump") else dict(self.state)
            logger.debug("Incoming state for summarizer: %s", state_dump)
        except Exception:
            logger.exception("Failed to dump incoming state")

        # Build recent conversation context (last 10 messages)
        try:
            logger.debug("Building recent messages context (last 10)")
            recent_msgs = "\n".join([f"{m.role}: {m.content}" for m in self.state.messages[-10:]])
        except Exception as e:
            logger.exception("Failed to build recent messages: %s", e)
            recent_msgs = ""

        # Prepare risk report JSON safely
        try:
            risk_report_json = json.dumps(self.state.risk_analysis_report or {}, default=str)
        except Exception as e:
            logger.exception("Failed to serialize risk_analysis_report: %s", e)
            risk_report_json = "{}"

        full_prompt = summarizer_prompt + risk_report_json + f"\nConversation: {recent_msgs}"
        logger.debug("Final summarization prompt length=%d", len(full_prompt))

        try:
            logger.info("Calling Gemini LLM for summarization...")
            resp_text = call_llm(full_prompt)
            if isinstance(resp_text, str):
                resp_text = resp_text.strip()
            logger.info("Received summarization response (len=%d)", len(resp_text) if isinstance(resp_text, str) else 0)
            logger.debug("Raw summarizer response preview: %s", (resp_text[:500] + "...") if isinstance(resp_text, str) and len(resp_text) > 500 else resp_text)

            # Truncate for storage / perf
            truncated = resp_text[:1000] if isinstance(resp_text, str) else ""
            self.state.summary = resp_text
            logger.debug("Truncated summary length=%d", len(truncated))

            # Decide next status based on whether human input was flagged in risk report
            human_input_flag = False
            try:
                human_input_flag = bool(self.state.risk_analysis_report and self.state.risk_analysis_report.get("human_input"))
            except Exception:
                logger.exception("Error checking human_input flag in risk_analysis_report")

            if human_input_flag:
                logger.info("Risk report indicates human input required; marking state in_progress")
                self.state.status = "in_progress"
                self.state.message = "Human input required"
            else:
                logger.info("Summarization successful; marking state success")
                self.state.status = "success"
                # Use summary as response message
                self.state.message = self.state.summary

            logger.debug("State after summarization: %s", self.state.model_dump() if hasattr(self.state, "model_dump") else dict(self.state))
        except Exception as e:
            logger.exception("Summarization error: %s", e)
            self.state.errors = getattr(self.state, "errors", [])
            try:
                self.state.errors.append(f"Summarization error: {e}")
            except Exception:
                logger.exception("Failed to append summarization error to state.errors")
            self.state.status = "failed"
            self.state.message = "Summarization failed; retrying..."

        return self.state
