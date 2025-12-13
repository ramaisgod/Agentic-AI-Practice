# validation_agent.py
from .agent_state import AgentState
from prompts.validation_prompt import validation_prompt
from llm.llm_manager import call_llm
from core.logger import logger


class ValidationAgent:
    def __call__(self, state: AgentState):
        logger.info("ValidationAgent invoked")
        self.state = state
        return self.validate_input()

    def validate_input(self) -> AgentState:
        logger.info("Starting validation process...")
        logger.debug("Incoming state: %s", self.state.model_dump() if hasattr(self.state, "model_dump") else self.state)

        # Build context from last 5 messages
        try:
            logger.debug("Building context from previous messages")
            context = "\n".join([f"{m.role}: {m.content}" for m in self.state.messages[-5:]])
        except Exception as e:
            logger.exception("Failed building context from messages: %s", e)
            context = ""

        full_input = f"{context}\nCurrent: {self.state.input_contract}"
        logger.debug("Full validation input constructed: %s", full_input)

        # Basic sanity validation
        if len(self.state.input_contract) < 2:
            logger.warning("Input contract too short. Validation failing immediately.")
            self.state.errors.append("Input too short.")
            self.state.message = "Input validation failed."
            self.state.status = "failed"
            logger.debug("Updated state after short input failure: %s", self.state.model_dump())
            return self.state

        # Build prompt
        prompt = validation_prompt + full_input
        logger.debug("Final prompt being sent to LLM: %s", prompt)

        # Call LLM
        try:
            logger.info("Calling Gemini LLM for validation...")
            result = call_llm(prompt)  # Must be sync now
            if isinstance(result, str):
                result = result.strip()

            logger.info("Validation LLM response received")
            logger.debug("LLM response content: %s", result)

            # Interpret LLM result
            if "Invalid Input" in result:
                logger.warning("LLM marked the input as invalid")
                self.state.errors.append("Invalid contract data.")
                self.state.message = result
                self.state.status = "failed"
            else:
                logger.info("LLM validation passed successfully")
                self.state.message = "OK"
                self.state.status = "in_progress"

        except Exception as e:
            logger.exception("Error occurred during LLM validation: %s", e)
            self.state.errors.append(f"Validation error: {e}")
            self.state.status = "failed"

        logger.debug("Final state after validation: %s", self.state.model_dump())
        return self.state
