# trigger rebuild


from flask import Flask, request, jsonify

# Create the web app
app = Flask(__name__)

# Home page test
@app.route("/", methods=["GET"])
def hello():
    return "HMLR middleware is running"

# Test endpoint (Sheets will call this)
@app.route("/order", methods=["POST"])
def order():
    data = request.json

    return jsonify({
        "status": "ok",
        "message": "Cloud Run received your request",
        "received": data
    })

# Cloud Run runs on port 8080
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
