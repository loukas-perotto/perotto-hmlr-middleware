from flask import Flask, request, jsonify
from google.cloud import secretmanager
import os
import tempfile
import requests

app = Flask(__name__)

PROJECT_ID = "perotto-hmlr"


def get_secret(secret_id: str) -> str:
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{PROJECT_ID}/secrets/{secret_id}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("utf-8")


@app.route("/", methods=["GET"])
def hello():
    return "HMLR middleware v2 is running"


@app.route("/bgtest-check", methods=["GET"])
def bgtest_check():

    cert_pem = get_secret("bgtest-client-cert")
    ca_chain_pem = get_secret("bgtest-ca-chain")

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
        timeout=20
    )

    return jsonify({
        "status": "ok",
        "http_status": response.status_code,
        "body_preview": response.text[:500]
    })


@app.route("/official-copy-test", methods=["GET"])
def official_copy_test():

    cert_pem = get_secret("bgtest-client-cert")
    ca_chain_pem = get_secret("bgtest-ca-chain")

    with tempfile.NamedTemporaryFile(mode="w", delete=False) as cert_file:
        cert_file.write(cert_pem)
        cert_path = cert_file.name

    with tempfile.NamedTemporaryFile(mode="w", delete=False) as ca_file:
        ca_file.write(ca_chain_pem)
        ca_path = ca_file.name

    # TEST TITLE NUMBER FROM HMLR VENDOR TEST DATA
    title_number = "ND66318"

    soap_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
xmlns:oc="http://www.landregistry.gov.uk/OfficialCopyTitleKnown/V2_1">
<soapenv:Header/>
<soapenv:Body>

<oc:OfficialCopyTitleKnownRequest>

<oc:MessageHeader>
<oc:MessageId>test123</oc:MessageId>
<oc:Timestamp>2026-03-10T12:00:00</oc:Timestamp>
</oc:MessageHeader>

<oc:Application>
<oc:TitleNumber>{title_number}</oc:TitleNumber>

<oc:OfficialCopyTypeCode>10</oc:OfficialCopyTypeCode>

<oc:CustomerReference>TESTREF1</oc:CustomerReference>

</oc:Application>

</oc:OfficialCopyTitleKnownRequest>

</soapenv:Body>
</soapenv:Envelope>
"""

    response = requests.post(
        "https://bgtest.landregistry.gov.uk/b2b/BGSoapEngine/OfficialCopyTitleKnownV2_1WebService",
        data=soap_xml,
        headers={"Content-Type": "text/xml"},
        cert=cert_path,
        verify=ca_path,
        timeout=30
    )

    return jsonify({
        "status": "ok",
        "http_status": response.status_code,
        "response_xml": response.text[:2000]
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
