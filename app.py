from flask import Flask, jsonify
from google.cloud import secretmanager
import tempfile
import requests
import os

app = Flask(__name__)

PROJECT_ID = "perotto-hmlr"


def get_secret(secret_id: str) -> str:
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{PROJECT_ID}/secrets/{secret_id}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("utf-8")


@app.route("/", methods=["GET"])
def hello():
    return "HMLR middleware v6 running"


@app.route("/official-copy-test", methods=["GET"])
def official_copy_test():

    cert_pem = get_secret("bgtest-client-cert")
    ca_chain_pem = get_secret("bgtest-ca-chain")

    bg_username = get_secret("bg-username")
    bg_password = get_secret("bg-password")

    with tempfile.NamedTemporaryFile(mode="w", delete=False) as cert_file:
        cert_file.write(cert_pem)
        cert_path = cert_file.name

    with tempfile.NamedTemporaryFile(mode="w", delete=False) as ca_file:
        ca_file.write(ca_chain_pem)
        ca_path = ca_file.name

    title_number = "ND66318"

    soap_xml = f"""<?xml version="1.0" encoding="UTF-8"?>

<soapenv:Envelope
xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
xmlns:oc1="http://www.oscre.org/ns/eReg-Final/2011/RequestTitleKnownOfficialCopyV2_1"
xmlns:wsse="http://schemas.xmlsoap.org/ws/2002/12/secext"
xmlns:int="http://www.landregistry.gov.uk/international">

<soapenv:Header>

<wsse:Security>
<wsse:UsernameToken>
<wsse:Username>{bg_username}</wsse:Username>
<wsse:Password>{bg_password}</wsse:Password>
</wsse:UsernameToken>
</wsse:Security>

<int:International>
<int:Locale>en</int:Locale>
</int:International>

</soapenv:Header>

<soapenv:Body>

<oc1:RequestTitleKnownOfficialCopyV2_1>

<oc1:ID>TEST123</oc1:ID>

<oc1:TitleNumber>{title_number}</oc1:TitleNumber>

<oc1:OfficialCopyTypeCode>10</oc1:OfficialCopyTypeCode>

<oc1:CustomerReference>TESTREF1</oc1:CustomerReference>

</oc1:RequestTitleKnownOfficialCopyV2_1>

</soapenv:Body>
</soapenv:Envelope>
"""

    try:

        response = requests.post(
            "https://bgtest.landregistry.gov.uk/b2b/ECBG_StubService/OfficialCopyTitleKnownV2_1WebService",
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

    finally:
        os.remove(cert_path)
        os.remove(ca_path)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
