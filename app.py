from flask import Flask, request, jsonify
from google.cloud import secretmanager
import os
import tempfile
import requests

app = Flask(__name__)


def get_secret(secret_id: str) -> str:
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCP_PROJECT")
    if not project_id:
        raise RuntimeError("Google Cloud project ID not found in environment.")

    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("utf-8")


@app.route("/", methods=["GET"])
def hello():
    return "HMLR middleware v2 is running"


@app.route("/order", methods=["POST"])
def order():
    data = request.json
    return jsonify({
        "status": "ok",
        "message": "Cloud Run received your request",
        "received": data
    })


@app.route("/bgtest-check", methods=["GET"])
def bgtest_check():
    cert_pem = None
    ca_chain_pem = None

    try:
        cert_pem = get_secret("bgtest-client-cert")
        ca_chain_pem = get_secret("bgtest-ca-chain")
    except Exception as e:
        return jsonify({
            "status": "error",
            "stage": "read_secrets",
            "message": str(e)
        }), 500

    try:
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as cert_file:
            cert_file.write(cert_pem)
            cert_path = cert_file.name

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as ca_file:
            ca_file.write(ca_chain_pem)
            ca_path = ca_file.name

        response = requests.get(
            "https://bgtest.landregistry.gov.uk",
            cert=cert_path,
            verify=ca_path,
            timeout=20,
            allow_redirects=True
        )

        return jsonify({
            "status": "ok",
            "http_status": response.status_code,
            "final_url": response.url,
            "body_preview": response.text[:500]
        })

    except requests.exceptions.SSLError as e:
        return jsonify({
            "status": "error",
            "stage": "tls_handshake",
            "message": str(e)
        }), 500

    except Exception as e:
        return jsonify({
            "status": "error",
            "stage": "request",
            "message": str(e)
        }), 500

    finally:
        try:
            if "cert_path" in locals() and os.path.exists(cert_path):
                os.remove(cert_path)
            if "ca_path" in locals() and os.path.exists(ca_path):
                os.remove(ca_path)
        except Exception:
            pass


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
