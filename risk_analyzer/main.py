import os

from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename

from analyzer_agent import OrchestratorAgent, AgentState

# Optional: make these configurable
ALLOWED_EXTENSIONS = {".txt", ".pdf", ".docx"}

app = Flask(__name__)
CORS(app)


def allowed_file(filename: str) -> bool:
    _, ext = os.path.splitext(filename)
    return ext.lower() in ALLOWED_EXTENSIONS


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/analyze_contract_risk", methods=["POST"])
def risk_analysis():
    # JSON body for main analysis endpoint
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


@app.route("/upload_contract", methods=["POST"])
def upload_contract():
    """
    Endpoint to upload a document and extract text for project_description.
    Expects multipart/form-data with a file field: description_file
    """
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

    filename = secure_filename(file.filename)
    _, ext = os.path.splitext(filename)
    ext = ext.lower()

    if not allowed_file(filename):
        return jsonify({
            "status": "failed",
            "errors": [f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"],
            "message": "Unsupported file type.",
            "project_description": None,
        }), 415

    try:
        text = ""

        if ext == ".txt":
            # Simple text file
            raw = file.read()
            text = raw.decode("utf-8", errors="ignore")

        elif ext == ".pdf":
            # PDF → use PyPDF2
            try:
                from PyPDF2 import PdfReader
            except ImportError:
                return jsonify({
                    "status": "failed",
                    "errors": ["PyPDF2 is not installed. Run 'pip install PyPDF2'."],
                    "message": "PDF support not available on server.",
                    "project_description": None,
                }), 500

            reader = PdfReader(file)
            pages = []
            for page in reader.pages:
                page_text = page.extract_text() or ""
                pages.append(page_text)
            text = "\n\n".join(pages)

        elif ext == ".docx":
            # Word docx → use python-docx
            try:
                import docx
            except ImportError:
                return jsonify({
                    "status": "failed",
                    "errors": ["python-docx is not installed. Run 'pip install python-docx'."],
                    "message": "DOCX support not available on server.",
                    "project_description": None,
                }), 500

            # python-docx can read file-like objects
            doc = docx.Document(file)
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            text = "\n\n".join(paragraphs)

        # Fallback safety
        text = (text or "").strip()

        if not text:
           return jsonify({
                "status": "failed",
                "errors": ["Unable to extract text from the uploaded file."],
                "message": "File parsed but no text was found.",
                "project_description": None,
            }), 422

        # Success → return text so frontend can populate textarea
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
