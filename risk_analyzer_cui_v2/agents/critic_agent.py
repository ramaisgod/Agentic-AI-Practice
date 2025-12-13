# critic_agent.py
from .agent_state import AgentState
from core.logger import logger


class CriticAgent:
    def __call__(self, state: AgentState):
        logger.info("CriticAgent invoked")
        self.state = state
        return self.evaluate()

    def evaluate(self):
        logger.info("Starting quality evaluation based on risk analysis report")

        try:
            logger.debug("Incoming state: %s",
                         self.state.model_dump() if hasattr(self.state, "model_dump") else self.state)
        except Exception:
            logger.exception("Failed to dump state for logging")

        report = self.state.risk_analysis_report or {}
        logger.debug("Risk report received for evaluation: %s", report)

        # Default score
        score = 50

        try:
            if not report:
                logger.warning("No risk analysis report found — penalizing score")
                score = 30
            else:
                # Number of keys in the report
                keys = len(report.keys())
                logger.debug("Report has %d keys", keys)

                # Length/depth of report values
                try:
                    detail_score = sum(len(str(v)) for v in report.values()) / 1000 if report.values() else 0
                    logger.debug("Detail score computed: %s", detail_score)
                except Exception:
                    logger.exception("Error computing detail score")
                    detail_score = 0

                # Base formula
                score = min(100, 50 + (keys * 10) + (detail_score * 5))
                logger.debug("Score after depth & key evaluation: %s", score)

                # Penalize based on recent confusion/errors
                try:
                    recent_errors = sum(
                        1 for m in self.state.messages[-3:]
                        if hasattr(m, "content") and isinstance(m.content, str) and "error" in m.content.lower()
                    )
                    if recent_errors > 0:
                        logger.warning("Detected %d recent error messages — applying penalty", recent_errors)
                    score = max(0, score - (recent_errors * 20))
                except Exception:
                    logger.exception("Failed to check recent error messages")

        except Exception as e:
            logger.exception("Unexpected error during score evaluation: %s", e)

        # Determine if human input was previously flagged
        try:
            human_flag = bool(report.get("human_input", False))
        except Exception:
            logger.exception("Failed reading human_input flag from report")
            human_flag = False

        # Final result
        result = {
            "quality_score": int(score),
            "human_input": human_flag,
            "thread_id": self.state.thread_id
        }

        logger.info("CriticAgent scoring complete — Score=%s | HumanInput=%s", score, human_flag)
        logger.debug("CriticAgent output: %s", result)

        return result
