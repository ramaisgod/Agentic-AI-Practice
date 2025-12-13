# main.py
import uuid
import time
from typing import Optional
from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
from core.logger import logger, setup_logging

# DB helpers
from core.db_utils import (
    get_or_create_user,
    get_conversation_by_thread,
    create_conversation,
    add_message,
    get_conversation_messages,
    list_conversations_for_user,
)

# Agents
from agents.orchestrator_agent import OrchestratorAgent
from agents.agent_state import AgentState, Message

# LangGraph Command
from langgraph.types import Command

app = Flask(__name__, static_folder="static", template_folder="templates")
CORS(app)
setup_logging()


def _preview(text, limit=200):
    if not isinstance(text, str):
        return str(text)
    return text if len(text) <= limit else text[:limit] + "..."


@app.route("/", methods=["GET"])
def index():
    logger.info("GET / — Home page loaded")
    return render_template("index.html")


# ==========================================================================================
# /chat/start
# ==========================================================================================
@app.route("/chat/start", methods=["POST"])
def start_chat():
    start = time.time()
    logger.info("POST /chat/start called")

    payload = request.get_json(silent=True) or {}
    logger.debug("Incoming payload preview: %s", _preview(str(payload)))

    user_email = payload.get("user_email")
    message = payload.get("message", "")
    thread_id = payload.get("thread_id") or str(uuid.uuid4())

    # Validate input
    if not user_email or not message or not message.strip():
        logger.warning("Invalid payload: user_email or message missing")
        return jsonify({"status": "failed", "errors": ["user_email and message are required"]}), 400

    try:
        logger.info("Ensuring user exists for email=%s", user_email)
        user_id = get_or_create_user(user_email)

        state = AgentState(
            user_id=str(user_id),
            input_contract=message.strip(),
            thread_id=thread_id
        )
        logger.debug("AgentState initialized for start_chat (thread_id=%s)", thread_id)

        # Ensure conversation exists
        conv = get_conversation_by_thread(thread_id)
        if not conv:
            logger.info("No existing conversation found. Creating new record for thread_id=%s", thread_id)
            create_conversation(user_id, thread_id)

        # Run orchestrator
        logger.info("Starting OrchestratorAgent run for thread_id=%s", thread_id)
        agent = OrchestratorAgent(state)
        result = agent.run()

        if isinstance(result, dict) and result.get("status") == "failed":
            logger.error("Orchestrator returned failure (thread_id=%s): %s", thread_id, result)
            return jsonify(result), 500

        logger.info("POST /chat/start completed successfully (elapsed=%.3fs)", time.time() - start)
        return jsonify(result), 200

    except Exception as e:
        logger.exception("Error in /chat/start (thread_id=%s): %s", thread_id, e)
        return jsonify({"status": "failed", "errors": [str(e)]}), 500


# ==========================================================================================
# /chat/resume
# ==========================================================================================
@app.route("/chat/resume", methods=["POST"])
def resume_chat():
    start = time.time()
    logger.info("POST /chat/resume called")

    payload = request.get_json(silent=True) or {}
    logger.debug("Incoming resume payload preview: %s", _preview(str(payload)))

    thread_id = payload.get("thread_id")
    decision = payload.get("decision", "")

    if not thread_id:
        logger.warning("resume_chat missing thread_id")
        return jsonify({"status": "failed", "message": "'thread_id' is required"}), 400

    try:
        logger.info("Resuming chat for thread_id=%s", thread_id)

        state = AgentState(user_id="", input_contract="", thread_id=thread_id)
        agent = OrchestratorAgent(state)

        logger.debug("Invoking graph resume for thread_id=%s decision=%s", thread_id, decision)
        result = agent.graph.invoke(
            Command(resume=decision),
            config={"configurable": {"thread_id": thread_id}}
        )

        # Check for human interrupt
        if isinstance(result, dict) and "__interrupt__" in result:
            interrupt_items = result["__interrupt__"]
            prompt_for_human = interrupt_items[0].value if interrupt_items else "Human input required"
            logger.info("Human input required for thread_id=%s", thread_id)

            return jsonify({
                "status": "awaiting_human",
                "thread_id": thread_id,
                "prompt_for_human": prompt_for_human,
                "partial_state": {
                    "summary": result.get("summary"),
                    "risk_analysis_report": result.get("risk_analysis_report"),
                    "message": result.get("message"),
                    "quality_score": result.get("quality_score"),
                },
            }), 200

        # Completed normally
        final_state = result if isinstance(result, dict) else {}
        logger.info("Chat resumed successfully (thread_id=%s, elapsed=%.3fs)", thread_id, time.time() - start)

        return jsonify({
            "status": final_state.get("status", "completed"),
            "thread_id": thread_id,
            "summary": final_state.get("summary"),
            "risk_analysis_report": final_state.get("risk_analysis_report"),
            "message": final_state.get("message"),
            "quality_score": final_state.get("quality_score"),
        }), 200

    except Exception as e:
        logger.exception("Error in /chat/resume (thread_id=%s): %s", thread_id, e)
        return jsonify({"status": "failed", "errors": [str(e)]}), 500


# ==========================================================================================
# /conversations/<user_id>
# ==========================================================================================
@app.route("/conversations/<user_id>", methods=["GET"])
def list_convs(user_id):
    logger.info("GET /conversations/%s called", user_id)
    try:
        convs = list_conversations_for_user(uuid.UUID(user_id))
        logger.info("Conversations fetched for user %s (count=%d)", user_id, len(convs))
        return jsonify(convs), 200
    except Exception as e:
        logger.exception("Error in /conversations/%s: %s", user_id, e)
        return jsonify({"status": "failed", "errors": [str(e)]}), 500


# ==========================================================================================
# /conversation/<conv_id>/messages
# ==========================================================================================
@app.route("/conversation/<conv_id>/messages", methods=["GET"])
def get_msgs(conv_id):
    logger.info("GET /conversation/%s/messages called", conv_id)
    try:
        msgs = get_conversation_messages(uuid.UUID(conv_id))
        logger.info("Messages fetched for conversation %s (count=%d)", conv_id, len(msgs))
        return jsonify(msgs), 200
    except Exception as e:
        logger.exception("Error fetching messages for conv_id=%s: %s", conv_id, e)
        return jsonify({"status": "failed", "errors": [str(e)]}), 500


# ==========================================================================================
# Static Files
# ==========================================================================================
@app.route("/static/<path:filename>")
def static_files(filename):
    logger.debug("Serving static file: %s", filename)
    return send_from_directory(app.static_folder, filename)


# ==========================================================================================
# DEVELOPMENT SERVER
# ==========================================================================================
if __name__ == "__main__":
    logger.info("Starting Flask development server at http://0.0.0.0:5000")
    app.run(host="0.0.0.0", port=5000, debug=True)
