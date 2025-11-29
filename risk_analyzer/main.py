from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from analyzer_agent import OrchestratorAgent, AgentState


app = Flask(__name__)
CORS(app)


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/analyze_contract_risk", methods=["POST"])
def risk_analysis():
    payload = request.get_json(force=True) or {}
    project_description = payload.get("project_description", "")
    user_feedback = payload.get("feedback", "")

    if not project_description:
        return jsonify({
            "status": "failed",
            "errors": ["'project_description' is required in request body"],
            "message": "Missing contract data",
            "summary": None,
            "risk_analysis_report": None,
        }), 400

    state = AgentState(input_contract=project_description, feedback=user_feedback)
    agent = OrchestratorAgent(state)
    final_state = agent.run()

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
