from .agent_state import AgentState
from prompts.validation_prompt import validation_prompt
from llm.gemini_service import call_gemini_llm


class ValidationAgent:
    def __call__(self, state: AgentState):
        self.state = state
        return self.validate_input()

    def validate_input(self) -> AgentState:
        if not self.state.input_contract or len(self.state.input_contract) < 2:
            self.state.errors.append("Input contract is too short or missing.")
            self.state.message = "Input validation failed."
            self.state.status = "failed"
            return self.state

        prompt = validation_prompt + self.state.input_contract

        result = call_gemini_llm(prompt).strip()
        print(f"ValidationAgent response: {result}")

        if "Invalid Input" in result:
            self.state.errors.append("Input contract is not valid contract data.")
            self.state.message = result
            self.state.status = "failed"
        else:
            self.state.message = "ok"
            self.state.status = "in_progress"

        return self.state
