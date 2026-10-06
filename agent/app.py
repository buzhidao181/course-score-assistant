import os
import requests
from flask import Flask, request, jsonify
from dotenv import load_dotenv

from llm import translate

load_dotenv()

app = Flask(__name__)
GATEWAY_URL = "http://127.0.0.1:5001/gateway/query"


@app.route("/agent/ask", methods=["POST"])
def agent_ask():
    body = request.get_json(silent=True) or {}
    user_input = body.get("input")
    token = body.get("token")

    if not user_input:
        return jsonify({"error": "missing input"}), 400
    if not token:
        return jsonify({"error": "missing token"}), 400

    try:
        structured = translate(user_input)
    except Exception as e:
        return jsonify({"error": f"llm failure: {e}"}), 502

    try:
        resp = requests.post(
            GATEWAY_URL,
            json=structured,
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        )
    except requests.RequestException as e:
        return jsonify({"error": f"gateway failure: {e}"}), 502

    return jsonify({
        "llm_generated": structured,
        "gateway_response": resp.json(),
        "gateway_status": resp.status_code,
    }), resp.status_code


@app.route("/agent/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)