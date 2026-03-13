import base64
import os
import time
import requests
import xml.etree.ElementTree as ET
# deployment trigger
from flask import Flask, request, jsonify, send_from_directory
from google.cloud import secretmanager

app = Flask(__name__)

PROJECT_ID = "perotto-hmlr"
CERT_SECRET = "bgtest-client-cert"
CA_SECRET = "bgtest-ca-chain"

USERNAME = "LKyprianou3003"
PASSWORD = "LRAdmin2026!"

DOC_FOLDER = "/tmp"


def get_secret(secret_name):
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{PROJECT_ID}/secrets/{secret_name}/versions/latest"
    response = client.access_secret_version(name=name)
    return response.payload.data.decode("UTF-8")


def get_cert_files():
    cert = get_secret(CERT_SECRET)
    ca = get_secret(CA_SECRET)

    cert_path = "/tmp/client.pem"
    ca_path = "/tmp/ca.pem"

    with open(cert_path, "w") as f:
        f.write(cert)

    with open(ca_path, "w") as f:
        f.write(ca)

    return cert_path, ca_path


def soap_headers():
    token = base64.b64encode(f"{USERNAME}:{PASSWORD}".encode()).decode()

    return {
        "Content-Type": "text/xml",
        "Authorization": f"Basic {token}"
    }


@app.route("/")
def home():
    return "HMLR middleware is running"


# ---------------------------------------------------------
# SEARCH BY PROPERTY DESCRIPTION
# ---------------------------------------------------------

@app.route("/search-property")
def search_property():

    number = request.args.get("number")
    street = request.args.get("street")
    postcode = request.args.get("postcode")

    if not number or not street or not postcode:
        return jsonify({"error": "missing parameters"})

    message_id = f"msg{int(time.time())}"

    soap_body = f"""
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
xmlns:int="http://www.landregistry.gov.uk/international"
xmlns:lr="http://www.oscre.org/ns/eReg-Final/2011"
xmlns:wsse="http://schemas.xmlsoap.org/ws/2002/12/secext">

<soapenv:Header>
<wsse:Security>
<wsse:UsernameToken>
<wsse:Username>{USERNAME}</wsse:Username>
<wsse:Password>{PASSWORD}</wsse:Password>
</wsse:UsernameToken>
</wsse:Security>
</soapenv:Header>

<soapenv:Body>
<lr:RequestSearchByPropertyDescriptionV2_0>

<lr:ID>
<lr:MessageID>{message_id}</lr:MessageID>
</lr:ID>

<lr:Product>

<lr:ExternalReference>
<lr:Reference>ext{message_id}</lr:Reference>
</lr:ExternalReference>

<lr:CustomerReference>
<lr:Reference>cust{message_id}</lr:Reference>
</lr:CustomerReference>

<lr:SubjectProperty>
<lr:Address>

<lr:BuildingNumber>{number}</lr:BuildingNumber>
<lr:StreetName>{street}</lr:StreetName>
<lr:PostcodeZone>{postcode}</lr:PostcodeZone>

</lr:Address>
</lr:SubjectProperty>

</lr:Product>

</lr:RequestSearchByPropertyDescriptionV2_0>
</soapenv:Body>
</soapenv:Envelope>
"""

    cert_path, ca_path = get_cert_files()

    url = "https://businessgateway.landregistry.gov.uk/b2b/BGSoapEngine/SearchByPropertyDescriptionV2_0WebService"

    response = requests.post(
        url,
        data=soap_body,
        headers=soap_headers(),
        cert=cert_path,
        verify=ca_path,
    )

    xml = response.text

    root = ET.fromstring(xml)

    results = []

    for title in root.findall(".//TitleNumber"):
        results.append({
            "title_number": title.text
        })

    return jsonify({
        "results": results
    })


# ---------------------------------------------------------
# OFFICIAL COPY (already working)
# ---------------------------------------------------------

@app.route("/official-copy")
def official_copy():

    title = request.args.get("title_number", "ST500681")

    message_id = f"msg{int(time.time())}"

    soap_body = f"""
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
xmlns:int="http://www.landregistry.gov.uk/international"
xmlns:lr="http://www.oscre.org/ns/eReg-Final/2011"
xmlns:wsse="http://schemas.xmlsoap.org/ws/2002/12/secext">

<soapenv:Header>
<wsse:Security>
<wsse:UsernameToken>
<wsse:Username>{USERNAME}</wsse:Username>
<wsse:Password>{PASSWORD}</wsse:Password>
</wsse:UsernameToken>
</wsse:Security>
</soapenv:Header>

<soapenv:Body>

<lr:performTitleKnownSearch>

<arg0>

<lr:ID>
<lr:MessageID>{message_id}</lr:MessageID>
</lr:ID>

<lr:Product>

<lr:ExternalReference>
<lr:Reference>extRef0001</lr:Reference>
</lr:ExternalReference>

<lr:CustomerReference>
<lr:Reference>custRef0001</lr:Reference>
</lr:CustomerReference>

<lr:SubjectProperty>
<lr:TitleNumber>{title}</lr:TitleNumber>
</lr:SubjectProperty>

<lr:ExpectedPrice>
<lr:GrossPriceAmount>10</lr:GrossPriceAmount>
</lr:ExpectedPrice>

<lr:Contact>
<lr:Name>Test</lr:Name>
<lr:Communication>
<lr:Telephone>012345678</lr:Telephone>
</lr:Communication>
</lr:Contact>

<lr:TitleKnownOfficialCopy>
<lr:RequestedOfficialCopyCode>10</lr:RequestedOfficialCopyCode>
<lr:PropertyDescription>Test</lr:PropertyDescription>
<lr:OfficialCopyTypeCode>10</lr:OfficialCopyTypeCode>
<lr:ContinueIfActualFeeExceedsExpectedFeeIndicator>true</lr:ContinueIfActualFeeExceedsExpectedFeeIndicator>
</lr:TitleKnownOfficialCopy>

</lr:Product>

</arg0>

</lr:performTitleKnownSearch>

</soapenv:Body>
</soapenv:Envelope>
"""

    cert_path, ca_path = get_cert_files()

    url = "https://businessgateway.landregistry.gov.uk/b2b/BGSoapEngine/OfficialCopyTitleKnownV2_1WebService"

    response = requests.post(
        url,
        data=soap_body,
        headers=soap_headers(),
        cert=cert_path,
        verify=ca_path,
    )

    xml = response.text

    root = ET.fromstring(xml)

    pdf = None

    for node in root.iter():
        if "EmbeddedFileBinaryObject" in node.tag:
            pdf = node.text

    if not pdf:
        return jsonify({"error": "PDF not found"})

    pdf_bytes = base64.b64decode(pdf)

    filename = f"{title}-{int(time.time())}.pdf"
    path = f"{DOC_FOLDER}/{filename}"

    with open(path, "wb") as f:
        f.write(pdf_bytes)

    url = request.host_url + "document/" + filename

    return jsonify({
        "status": "success",
        "title_number": title,
        "pdf_url": url
    })


@app.route("/document/<name>")
def document(name):
    return send_from_directory(DOC_FOLDER, name)
