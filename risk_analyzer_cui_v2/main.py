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
from agents.agent_state import AgentState

# LangGraph Command & checkpointer
from langgraph.types import Command
from core.database import checkpointer

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

    if not user_email or not message.strip():
        return jsonify({"status": "failed", "errors": ["user_email and message are required"]}), 400

    try:
        user_id = get_or_create_user(user_email)

        # INITIAL AgentState with first message
        state = AgentState(
            user_id=str(user_id),
            input_contract=message.strip(),
            input_history=[message.strip()],  # 🔥 Store first message
            thread_id=thread_id
        )

        conv = get_conversation_by_thread(thread_id)
        if not conv:
            create_conversation(user_id, thread_id)

        agent = OrchestratorAgent(state)
        result = agent.run()

        return jsonify(result), 200

    except Exception as e:
        logger.exception("Error in /chat/start: %s", e)
        return jsonify({"status": "failed", "errors": [str(e)]}), 500



# ==========================================================================================
# /chat/resume  → Handles HUMAN FEEDBACK
# ==========================================================================================
@app.route("/chat/resume", methods=["POST"])
def resume_chat():
    start = time.time()
    logger.info("POST /chat/resume called")

    payload = request.get_json(silent=True) or {}
    logger.debug("Incoming resume payload preview: %s", _preview(str(payload)))

    thread_id = payload.get("thread_id")
    feedback = payload.get("decision", "")

    if not thread_id:
        return jsonify({"status": "failed", "message": "'thread_id' is required"}), 400

    try:
        logger.info("Resuming chat for thread_id=%s", thread_id)

        # 🔥 Restore the previous checkpoint state
        saved_state = checkpointer.get_tuple({"configurable": {"thread_id": thread_id}})
        if not saved_state:
            return jsonify({"status": "failed", "message": "No saved state found"}), 404

        restored = saved_state.checkpoint["channel_values"]
        logger.debug("Restored state from checkpoint: %s", restored)

        # 🔥 Convert restored state to AgentState
        state = AgentState(**restored)

        # 🔥 Append new human feedback
        if feedback:
            add_message(
                get_conversation_by_thread(thread_id)["conversation_id"],
                "user",
                feedback
            )
            state.input_history.append(feedback)
            state.input_contract = "\n".join(state.input_history)
            state.human_input = False       # feedback consumed
            state.message = None            # clear prior prompt

        # Restart the agent from validation
        agent = OrchestratorAgent(state)

        logger.info("Restarting full pipeline after human feedback")
        result = agent.graph.invoke(
            state.model_dump(),
            config={"configurable": {"thread_id": thread_id}}
        )

        # Check if graph wants more human input
        if "__interrupt__" in result:
            interrupt_items = result["__interrupt__"]
            prompt = interrupt_items[0].value if interrupt_items else "Human input required"


            return jsonify(result), 200

            # return jsonify({
            #     "status": "awaiting_human",
            #     "thread_id": thread_id,
            #     "prompt_for_human": prompt
            # }), 200

        # Completed normally
        return jsonify(result), 200

    except Exception as e:
        logger.exception("Error in /chat/resume: %s", e)
        return jsonify({"status": "failed", "errors": [str(e)]}), 500



# ==========================================================================================
# /conversations/<user_id>
# ==========================================================================================
@app.route("/conversations/<user_id>", methods=["GET"])
def list_convs(user_id):
    try:
        convs = list_conversations_for_user(uuid.UUID(user_id))
        return jsonify(convs), 200
    except Exception as e:
        logger.exception("Error: %s", e)
        return jsonify({"status": "failed", "errors": [str(e)]}), 500



# ==========================================================================================
# /conversation/<conv_id>/messages
# ==========================================================================================
@app.route("/conversation/<conv_id>/messages", methods=["GET"])
def get_msgs(conv_id):
    try:
        msgs = get_conversation_messages(uuid.UUID(conv_id))
        return jsonify(msgs), 200
    except Exception as e:
        logger.exception("Error fetching messages: %s", e)
        return jsonify({"status": "failed", "errors": [str(e)]}), 500



# ==========================================================================================
# Static Files
# ==========================================================================================
@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(app.static_folder, filename)



# ==========================================================================================
# FLASK DEV SERVER
# ==========================================================================================
if __name__ == "__main__":
    logger.info("Starting Flask development server at http://0.0.0.0:5000")
    app.run(host="0.0.0.0", port=5000, debug=True)
