from langgraph.graph import StateGraph, START, END
from pydantic import BaseModel, Field
from gemini_service import call_gemini_llm
from typing import AnyStr, List, Dict, Optional, Any
import json
import re


class AgentState(BaseModel):
    input_contract:str
    errors: List[str] = Field(default_factory=list)
    message: Optional[str] = None
    feedback: Optional[str] = None
    summary: Optional[str] = None
    risk_analysis_report: Optional[Dict[str, Any]] = None
    status: Optional[str] = None # "failed" | "in_progress" | "success"


def extract_json(text: str):
    # Find the first {...} block
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        return None

    json_str = match.group()

    try:
        return json.loads(json_str)
    except:
        return None


class ValidationAgent:
    def __call__(self, state: AgentState):
        self.state = state
        return self.validate_input()

    def validate_input(self) -> AgentState:
        if not self.state.input_contract or len(self.state.input_contract) < 50:
            self.state.errors.append("Input contract is too short or missing.")
            self.state.message = "Input validation failed."
            self.state.status = "failed"
            return self.state

        else:
            prompt = f"""You are an expert project-understanding and input-validation agent. 
            Your job is to determine whether the user's input is relevant to PROJECT or CONTRACT information.
            
            Valid input examples:
            - Project goals, requirements, scope
            - Timelines, phases, milestones
            - Risks, blockers, dependencies
            - Budget, cost, resources, effort
            - Teams, roles, stakeholders
            - Deliverables, acceptance criteria
            - Technical or operational details
            - Compliance, legal, contract clauses
            
            Invalid input examples:
            - Greetings (e.g., "hello", "how are you")
            - Chatting or personal conversation
            - Poetry, jokes, stories
            - Unrelated topics (movies, food, travel, weather, etc.)
            - Empty or meaningless text
            
            Your strict response must be ONLY:
            - "OK" → if the input is clearly related to project/contract details.
            - "Invalid Input" → if the input is irrelevant or unsuitable for project analysis.
            
            Do NOT add explanations or additional text.
            
            Here is the InputData:
            {self.state.input_contract}
            """

            result = call_gemini_llm(prompt)

            if "Invalid Input" in result:
                self.state.errors.append("Input contract is not valid contract data.")
                self.state.message = result
                self.state.status = "failed"
            else:
                self.state.message = "ok"
                self.state.status = "in_progress"

            return self.state


class RiskAnalysisAgent:
    def __call__(self, state: AgentState):
        self.state = state
        self.user_input = state.input_contract
        return self.run_analyzer()

    def run_analyzer(self) -> AgentState:
        if self.state.feedback:
            self.state.input_contract += f"\nAdditional Context: {self.state.feedback}"

        prompt = f"""You are an Expert Contract & Project Risk Analyst Agent. 
        Your responsibilities include:
        1. Validating whether the input is relevant to project/contract analysis.
        2. Checking completeness, clarity, and consistency of the provided information.
        3. Detecting contradictions, gaps, missing context, or unclear data.
        4. Performing detailed risk analysis ONLY when the input is valid and complete.
        5. Classifying risks into categories such as:
        - Technical
        - Operational
        - Financial
        - Compliance / Legal
        - Strategic
        - Resource / Staffing
        - Timeline / Delivery
        6. Recommending precise, realistic mitigation actions based on industry best practices.

        --------------------------------------------------------
        ## STEP 1 — INPUT VALIDATION
        Determine whether the user input is relevant to PROJECT or CONTRACT information.
        Valid inputs include:
        - Project scope, deliverables, requirements
        - Risks, blockers, assumptions
        - Roles, stakeholders, responsibilities
        - Budget, milestones, timelines
        - Technical or operational details
        - Compliance or legal clauses

        Invalid inputs include:
        - Greetings (“hello”, “hi”)
        - General chatting
        - Personal messages
        - Irrelevant topics (weather, movies, food, travel)
        - Poetry, jokes, or casual requests

        If the input is invalid, return STRICTLY:
        "Invalid Input"

        --------------------------------------------------------
        ## STEP 2 — CHECK COMPLETENESS & CLARITY
        If the input IS related but contains any of the following:
        - missing information
        - unclear or vague statements
        - contradictions
        - incomplete project description
        - insufficient data for proper risk analysis

        Then return STRICTLY in this JSON format:

        {{
        "human_input": true,
        "clarification": [
            "Write each clarification question in simple, direct language here."
        ]
        }}

        Ask ONLY the questions needed to complete the missing information.

        --------------------------------------------------------
        ## STEP 3 — FULL RISK ANALYSIS (ONLY WHEN INPUT IS VALID & COMPLETE)

        If the input is valid AND complete, perform full analysis:
        - Extract key risk factors
        - Classify each risk under a specific category
        - Explain why the risk exists (root cause)
        - Suggest recommended mitigation actions
        - Keep the analysis structured, clear, and professional

        Return STRICTLY in the following JSON format:

        {{
        "human_input": false,
        "analysis": [
            {{
            "risk": "Describe the identified risk",
            "type": "Technical / Operational / Financial / Compliance / etc.",
            "impact": "High / Medium / Low",
            "reason": "Explain the cause of the risk",
            "mitigation": "Provide actionable mitigation steps"
            }}
        ]
        }}

        Do NOT ask for clarification when information is complete.
        Do NOT output anything outside the allowed formats.

        --------------------------------------------------------
        ## INPUT DATA
        {self.state.input_contract}
        """

        resp = call_gemini_llm(prompt=prompt)
        resp_json = extract_json(resp)
        self.state.risk_analysis_report = resp_json
        self.state.status = "in_progress"
        if resp_json.get("human_input") is True:
            self.state.message = "Human input required"
        else:
            self.state.message = ""

        return self.state


class SummarizerAgent:
    def __call__(self, state: AgentState):
        self.state = state
        return self.summarize()

    def summarize(self) -> AgentState:
        prompt = f"""
        You are an expert in summarizing project and contract risk analysis.

        Your task is to generate a clear, concise, accurate summary of the identified risks in markdown.
        Your summary must:
        - Capture the key risks and their categories
        - Highlight the most critical risks (high-impact or high-probability)
        - Reflect overall project or contract risk posture
        - Include major mitigation themes (without repeating full details)
        - Be easy to understand for executives and non-technical stakeholders
        - Avoid technical jargon unless necessary
        - Remain faithful to the provided analysis (no assumptions or invented data)

        Do NOT add new risks.
        Do NOT infer missing information.
        Summarize ONLY from the given risk analysis.

        Here are the risk analysis findings:
        {self.state.risk_analysis_report}
        """

        resp = call_gemini_llm(prompt=prompt)
        self.state.summary = resp
        if self.state.risk_analysis_report.get("human_input") is True:
            self.state.status = "in_progress"
            self.state.message = "Human input required"
        else:
            self.state.status = "success"
            self.state.message = ""

        return self.state


class OrchestratorAgent:
    def __init__(self, state: AgentState):
        self.state = state
        self.validation = ValidationAgent()
        self.analyzer = RiskAnalysisAgent()
        self.summarizer = SummarizerAgent()

        self.graph = self._build_graph()

    @staticmethod
    def route_after_validation(state: AgentState):
        if state.errors or state.status == "failed":
            return "end"
        return "analyzer"

    @staticmethod
    def route_after_analyzer(state: AgentState):
        if state.errors or state.status == "failed" or not state.risk_analysis_report:
            return "end"
        return "summarizer"


    def _build_graph(self):
        g = StateGraph(AgentState)
        g.add_node("validation", self.validation)
        g.add_node("analyzer", self.analyzer)
        g.add_node("summarizer", self.summarizer)

        g.add_edge(START, "validation")
        g.add_conditional_edges(
            "validation",
            OrchestratorAgent.route_after_validation,
            {"analyzer": "analyzer", "end": END}
        )
        g.add_conditional_edges(
            "analyzer",
            OrchestratorAgent.route_after_analyzer,
            {"summarizer": "summarizer", "end": END}
        )

        g.add_edge("summarizer", END)

        g.set_entry_point("validation")

        return g.compile()

    def run(self) -> AgentState:
        result = self.graph.invoke(self.state)
        if isinstance(result, dict):
            return AgentState(**result)
        return result


if __name__ == '__main__':
    print("welcome")
    data = """ Project Name: Smart Inventory Automation System"""
    state = AgentState(input_contract=data)
    agent = OrchestratorAgent(state)
    final_state = agent.run()

    print("Status:", final_state.status)
    print("Errors:", final_state.errors)
    print("Message:", final_state.message)
    print("Risk Analysis:", final_state.risk_analysis_report)
    print("Summary:", final_state.summary)

