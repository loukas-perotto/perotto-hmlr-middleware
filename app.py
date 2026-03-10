from flask import Flask, jsonify, request, Response
from google.cloud import secretmanager
from google.cloud import storage
import requests
import tempfile
import os
import base64
import re
import time

app = Flask(__name__)

PROJECT_ID = "perotto-hmlr"
BUCKET_NAME = "perotto-hmlr-documents"


# -----------------------------
# SECRET MANAGER HELPER
# -----------------------------

def get_secret(secret_id):
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{PROJECT_ID}/secrets/{secret_id}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("utf-8")


# -----------------------------
# HEALTH CHECK
# -----------------------------

@app.route("/", methods=["GET"])
def home():
    return "HMLR middleware running"


# -----------------------------
# DOWNLOAD DOCUMENT FROM BUCKET
# -----------------------------

@app.route("/document/<filename>", methods=["GET"])
def serve_document(filename):

    storage_client = storage.Client()
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(filename)

    if not blob.exists():
        return {"error": "File not found"}, 404

    pdf_bytes = blob.download_as_bytes()

    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"'
        }
    )


# -----------------------------
# REQUEST OFFICIAL COPY
# -----------------------------

@app.route("/official-copy", methods=["GET"])
def official_copy():

    title_number = request.args.get("title_number", "ST500681")

    cert_path = None
    ca_path = None

    try:

        cert_pem = get_secret("bgtest-client-cert")
        ca_chain_pem = get_secret("bgtest-ca-chain")
        username = get_secret("bg-username")
        password = get_secret("bg-password")

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as cert_file:
            cert_file.write(cert_pem)
            cert_path = cert_file.name

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as ca_file:
            ca_file.write(ca_chain_pem)
            ca_path = ca_file.name

        message_id = f"DfltMsgId{int(time.time()*1000)}"

        soap_xml = f"""
<?xml version="1.0" encoding="UTF-8"?>

<soapenv:Envelope
xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
xmlns:ns1="http://www.oscre.org/ns/eReg-Final/2011/RequestTitleKnownOfficialCopyV2_1"
xmlns:ns3="http://officialcopyv2_1.ws.bg.lr.gov/"
xmlns:wsse="http://schemas.xmlsoap.org/ws/2002/12/secext"
xmlns:int="http://www.landregistry.gov.uk/international">

<soapenv:Header>

<wsse:Security>
<wsse:UsernameToken>
<wsse:Username>{username}</wsse:Username>
<wsse:Password>{password}</wsse:Password>
</wsse:UsernameToken>
</wsse:Security>

<int:International>
<int:Locale>en</int:Locale>
</int:International>

</soapenv:Header>

<soapenv:Body>

<ns3:performTitleKnownSearch>

<arg0>

<ns1:ID>
<ns1:MessageID>{message_id}</ns1:MessageID>
</ns1:ID>

<ns1:Product>

<ns1:ExternalReference>
<ns1:Reference>extRef0001</ns1:Reference>
</ns1:ExternalReference>

<ns1:CustomerReference>
<ns1:Reference>custRef0001</ns1:Reference>
</ns1:CustomerReference>

<ns1:SubjectProperty>
<ns1:TitleNumber>{title_number}</ns1:TitleNumber>
</ns1:SubjectProperty>

<ns1:ExpectedPrice>
<ns1:GrossPriceAmount>10</ns1:GrossPriceAmount>
</ns1:ExpectedPrice>

<ns1:Contact>
<ns1:Name>Test User</ns1:Name>
<ns1:Communication>
<ns1:Telephone>0123456789</ns1:Telephone>
</ns1:Communication>
</ns1:Contact>

<ns1:TitleKnownOfficialCopy>

<ns1:RequestedOfficialCopyCode>10</ns1:RequestedOfficialCopyCode>

<ns1:PropertyDescription>Test Property</ns1:PropertyDescription>

<ns1:OfficialCopyTypeCode>10</ns1:OfficialCopyTypeCode>

<ns1:ContinueIfTitleIsClosedAndContinuedIndicator>false</ns1:ContinueIfTitleIsClosedAndContinuedIndicator>

<ns1:NotifyIfPendingFirstRegistrationIndicator>false</ns1:NotifyIfPendingFirstRegistrationIndicator>

<ns1:NotifyIfPendingApplicationIndicator>false</ns1:NotifyIfPendingApplicationIndicator>

<ns1:SendBackDatedIndicator>false</ns1:SendBackDatedIndicator>

<ns1:ContinueIfActualFeeExceedsExpectedFeeIndicator>true</ns1:ContinueIfActualFeeExceedsExpectedFeeIndicator>

</ns1:TitleKnownOfficialCopy>

</ns1:Product>

</arg0>

</ns3:performTitleKnownSearch>

</soapenv:Body>
</soapenv:Envelope>
"""

        response = requests.post(
            "https://bgtest.landregistry.gov.uk/b2b/ECBG_StubService/OfficialCopyTitleKnownV2_1WebService",
            data=soap_xml,
            headers={"Content-Type": "text/xml"},
            cert=cert_path,
            verify=ca_path,
            timeout=30
        )

        xml = response.text

        pdf_match = re.search(
            r"<ns4:EmbeddedFileBinaryObject[^>]*>(.*?)</ns4:EmbeddedFileBinaryObject>",
            xml,
            re.DOTALL
        )

        if not pdf_match:
            return jsonify({
                "status": "error",
                "message": "PDF not found in HMLR response"
            }), 500

        pdf_base64 = pdf_match.group(1).strip()
        pdf_bytes = base64.b64decode(pdf_base64)

        filename = f"{title_number}-{int(time.time())}.pdf"

        storage_client = storage.Client()
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(filename)

        blob.upload_from_string(
            pdf_bytes,
            content_type="application/pdf"
        )

        url = f"https://perotto-hmlr-middleware-804049538982.europe-west1.run.app/document/{filename}"

        return jsonify({
            "status": "success",
            "title_number": title_number,
            "pdf_url": url
        })

    except Exception as e:

        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

    finally:

        try:
            if cert_path and os.path.exists(cert_path):
                os.remove(cert_path)

            if ca_path and os.path.exists(ca_path):
                os.remove(ca_path)

        except:
            pass


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
