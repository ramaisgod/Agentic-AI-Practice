import os
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename
from agents.orchestrator_agent import OrchestratorAgent
from agents.agent_state import AgentState
from utils.docs_reader import process_file


app = Flask(__name__)
CORS(app)


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/upload_contract", methods=["POST"])
def upload_contract():
    """
    Endpoint to upload a document and extract text for project_description.
    Expects multipart/form-data with a file field: description_file
    """
    try:
        if "description_file" not in request.files:
            return jsonify({
                "status": "failed",
                "errors": ["'description_file' is required in form-data"],
                "message": "No file part in the request.",
                "project_description": None,
            }), 400

        file = request.files["description_file"]

        if file.filename == "":
            return jsonify({
                "status": "failed",
                "errors": ["Empty filename."],
                "message": "No selected file.",
                "project_description": None,
            }), 400

        text = process_file(file)

        return jsonify({
            "status": "success",
            "errors": [],
            "message": "File processed successfully.",
            "project_description": text,
        }), 200

    except Exception as e:
        return jsonify({
            "status": "failed",
            "errors": ["Exception while processing file."],
            "message": str(e),
            "project_description": None,
        }), 500


@app.route("/analyze_contract_risk", methods=["POST"])
def risk_analysis():
    payload = request.get_json(silent=True) or {}

    project_description = payload.get("project_description", "") or ""
    user_feedback = payload.get("feedback", "") or ""

    # Optional future support for feedback_history list
    feedback_history = payload.get("feedback_history")
    if isinstance(feedback_history, list) and feedback_history:
        if user_feedback:
            feedback_history.append(user_feedback)
        user_feedback = "\n\n".join(str(item) for item in feedback_history if item)

    if not project_description.strip():
        return jsonify({
            "status": "failed",
            "errors": ["'project_description' is required in request body"],
            "message": "Missing project / contract description.",
            "summary": None,
            "risk_analysis_report": None,
        }), 400

    state = AgentState(
        input_contract=project_description,
        feedback=user_feedback or None,
    )

    try:
        agent = OrchestratorAgent(state)
        final_state = agent.run()
    except Exception as e:
        return jsonify({
            "status": "failed",
            "errors": ["Internal orchestration error"],
            "message": f"Orchestrator failed: {str(e)}",
            "summary": None,
            "risk_analysis_report": None,
        }), 500

    response = {
        "status": final_state.status,
        "errors": final_state.errors,
        "message": final_state.message,
        "summary": final_state.summary,
        "risk_analysis_report": final_state.risk_analysis_report,
    }

    return jsonify(response), 200



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
