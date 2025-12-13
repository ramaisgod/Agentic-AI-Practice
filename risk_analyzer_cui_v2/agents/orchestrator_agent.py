# orchestrator_agent.py
import uuid
from typing import Union, Dict, Any

from langgraph.graph import StateGraph, START, END
from langgraph.types import Command, interrupt
from core.database import checkpointer

from .agent_state import AgentState
from .validation_agent import ValidationAgent
from .risk_analysis_agent import RiskAnalysisAgent
from .critic_agent import CriticAgent
from .summarizer_agent import SummarizerAgent

from core.db_utils import (
    get_conversation_by_thread,
    create_conversation,
    add_message
)

from core.logger import logger


class OrchestratorAgent:
    _graph = None

    def __init__(self, state: AgentState):
        logger.info(
            "Initializing OrchestratorAgent for user_id=%s thread_id=%s",
            state.user_id, state.thread_id
        )

        self.state = state

        # Ensure thread_id exists
        if not self.state.thread_id:
            self.state.thread_id = str(uuid.uuid4())

        # --- Create sub-agents BEFORE graph build ---
        self.validation = ValidationAgent()
        self.analyzer = RiskAnalysisAgent()
        self.critic = CriticAgent()
        self.summarizer = SummarizerAgent()

        # Build once
        if OrchestratorAgent._graph is None:
            OrchestratorAgent._graph = self._build_graph()

        self.graph = OrchestratorAgent._graph

    # -----------------------------------------------
    @staticmethod
    def _to_dict_state(state: Union[AgentState, dict]) -> dict:
        if hasattr(state, "model_dump"):
            return state.model_dump()
        return state if isinstance(state, dict) else {}

    # -----------------------------------------------
    def _build_graph(self):
        logger.info("Creating StateGraph...")
        g = StateGraph(AgentState)

        # Nodes
        g.add_node("validation", self._wrap(self.validation))
        g.add_node("analyzer", self._wrap(self.analyzer))
        g.add_node("critic", self._wrap(self.critic))
        g.add_node("arbiter", self._arbiter_node)
        g.add_node("human_review", self._human_review_node)
        g.add_node("summarizer", self._wrap(self.summarizer))

        # Flow
        g.add_edge(START, "validation")

        g.add_conditional_edges(
            "validation",
            self.route_after_validation,
            {
                "analyzer": "analyzer",
                "end": END
            }
        )

        g.add_conditional_edges(
            "analyzer",
            self.route_after_analyzer,
            {
                "critic": "critic",
                "end": END
            }
        )

        g.add_edge("critic", "arbiter")

        # 🔥 FIX: After human feedback, restart full pipeline
        g.add_edge("human_review", "validation")

        g.add_edge("summarizer", END)

        compiled = g.compile(checkpointer=checkpointer)
        logger.info("Graph compiled successfully")

        return compiled

    # -----------------------------------------------
    def _wrap(self, agent_callable):
        def node(state):
            name = agent_callable.__class__.__name__
            logger.info("Executing node: %s", name)

            try:
                res = agent_callable(state)
            except Exception as e:
                logger.exception("Agent '%s' failed: %s", name, e)
                return {
                    "status": "failed",
                    "errors": [str(e)],
                    "thread_id": self.state.thread_id
                }

            return res.model_dump() if hasattr(res, "model_dump") else res

        return node

    # -----------------------------------------------
    @staticmethod
    def route_after_validation(state):
        s = OrchestratorAgent._to_dict_state(state)

        errors = s.get("errors")
        status = s.get("status")

        if errors or status == "failed":
            return "end"

        return "analyzer"

    # -----------------------------------------------
    @staticmethod
    def route_after_analyzer(state):
        s = OrchestratorAgent._to_dict_state(state)

        if s.get("errors") or s.get("status") == "failed":
            return "end"

        return "critic"

    # -----------------------------------------------
    def _arbiter_node(self, state):
        s = OrchestratorAgent._to_dict_state(state)

        score = s.get("quality_score", 0)
        refinements = s.get("refinement_count", 0)
        wants_human = s.get("human_input", False)
        thread_id = s.get("thread_id")

        # 🔥 HUMAN FEEDBACK REQUESTED
        if wants_human:
            return Command(
                goto="human_review",
                update={
                    "message": "Human review requested",
                    "thread_id": thread_id
                }
            )

        # 🔁 REFINE IF POOR QUALITY
        if score < 80 and refinements < 2:
            return Command(
                goto="analyzer",
                update={
                    "message": "Refining based on quality score",
                    "refinement_count": refinements + 1,
                    "thread_id": thread_id
                }
            )

        # 👍 READY FOR SUMMARY
        return Command(
            goto="summarizer",
            update={"message": "Quality is good", "thread_id": thread_id}
        )

    # -----------------------------------------------
    def _human_review_node(self, state):
        """
        User is asked to provide corrections.
        LangGraph interrupt pauses execution.
        """
        return interrupt(
            "Human review needed. Provide corrections or improvements."
        )

    # -----------------------------------------------
    def run(self):
        thread_id = self.state.thread_id

        # Ensure conversation exists
        conv = get_conversation_by_thread(thread_id)
        if not conv:
            conv_id = create_conversation(self.state.user_id, thread_id)
            conv = {"conversation_id": conv_id}

        # Log initial user message
        add_message(conv["conversation_id"], "user", self.state.input_contract)

        # Run graph
        result = self.graph.invoke(
            self.state.model_dump(),
            config={"configurable": {"thread_id": thread_id}}
        )

        # Save assistant reply
        if result.get("message"):
            add_message(conv["conversation_id"], "assistant", result["message"])

        return result
