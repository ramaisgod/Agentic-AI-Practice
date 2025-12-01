from .agent_state import AgentState
from prompts.risk_analysis_prompt import risk_analysis_prompt
from llm.gemini_service import call_gemini_llm
from utils.common import extract_json


class RiskAnalysisAgent:
    def __call__(self, state: AgentState):
        self.state = state
        self.user_input = state.input_contract
        return self.run_analyzer()

    def run_analyzer(self) -> AgentState:
        if self.state.feedback:
            self.state.input_contract += f"\nAdditional Context: {self.state.feedback}"

        prompt = risk_analysis_prompt + self.state.input_contract
        resp_text = call_gemini_llm(prompt)
        resp_json = extract_json(resp_text) or {}
        print(f"RiskAnalysisAgent response: {resp_json}")

        self.state.risk_analysis_report = resp_json
        self.state.status = "in_progress"

        if resp_json.get("human_input") is True:
            self.state.message = "Human input required"
        else:
            self.state.message = ""

        return self.state