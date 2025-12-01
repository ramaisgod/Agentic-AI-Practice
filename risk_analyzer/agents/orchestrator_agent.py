from langgraph.graph import StateGraph, START, END
from .agent_state import AgentState
from .validation_agent import ValidationAgent
from .risk_analysis_agent import RiskAnalysisAgent
from .summarizer_agent import SummarizerAgent


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
