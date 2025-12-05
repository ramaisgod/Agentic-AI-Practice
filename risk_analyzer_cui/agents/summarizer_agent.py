from .agent_state import AgentState
from prompts.summarizer_prompt import summarizer_prompt
from llm.gemini_service import call_gemini_llm
import json

class SummarizerAgent:
    def __call__(self, state: AgentState):
        self.state = state
        return self.summarize()

    def summarize(self) -> AgentState:
        prompt = summarizer_prompt + json.dumps(self.state.risk_analysis_report)
        resp_text = call_gemini_llm(prompt)
        self.state.summary = resp_text

        if self.state.risk_analysis_report.get("human_input") is True:
            self.state.status = "in_progress"
            self.state.message = "Human input required"
        else:
            self.state.status = "success"
            self.state.message = ""

        return self.state