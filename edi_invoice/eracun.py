import os
import json

import requests


class MojEracun:

    def __init__(self, user, passwd, company_oib, software_id):
        self.user = user
        self.passwd = passwd
        self.company_oib = company_oib
        self.software_id = software_id
        self.base_url = ""
        self.api_version = ""
        self.api = {}
        self._load_cfg()

    def _load_cfg(self):
        """Load configuration:
    - methods and API ENDPOINTS
    - api versions
    - base_url
        The configuration file should be in the same dir as this file.
        """
        this_dir = os.path.dirname(os.path.realpath(__file__))
        with open(os.path.join(this_dir,"conf.json")) as f:
            c = json.load(f)
            self.base_url = c["baseURL"]
            self.api_version = c["apiVersion"]
            self.api = c["REST"]
            self.doc_status = c["documentStatus"]
            self.doc_process_status = c["documentProcessStatus"]
            self._ping = c["ping"]

    def _url(self, endpoint):
        return self.base_url + self.api_version + endpoint

    def _credentials(self):
        return {
            "Username": self.user,
            "Password": self.passwd,
            "CompanyID": self.company_oib,
            "SoftwareId": self.software_id,
        }

    def _headers(self):
        return {
            "content-type": "application/json",
            "charset": "utf-8",
        }

    def ping(self):
        """Test service status:
        {
           "Status": "ok",
           "Message": "Service is up"
        }
        """
        response = requests.get(self._ping)
        return response.json()

    def query_incoming_invoices(self, invoice_id=None, filter_undelivered=False, from_date=None, to_date=None):
        """JSON parameters
            "Username": "Sender Username", required
            "Password": "Sender Password", required
            "CompanyId": "Sender Company Id (Oib)", required
            "SoftwareId": "Business Software (Erp) Id", required

            "CompanyBu": "Sender Business Unit (PJ)"
            "Filter": "'Undelivered' | Undelivered filters status 30-Sent",
            "ElectronicId": "Filters single document",
            "StatusId": Filters status. Valid options: "30" for Sent or "40" for Delivered",

            "From": "YYYY-MM-DDThh:mm:ss or YYYY-MM-DD",
            "To": "YYYY-MM-DDThh:mm:ss or YYYY-MM-DD",
        """
        endpoint = self.api['queryInbox'][0]
        req = self._credentials()
        if invoice_id:
            req["ElectronicId"] = invoice_id
        else:
            if filter_undelivered:
                req["Filter"] = "Undelivered"
            if from_date:
                req["From"] = from_date
            if to_date:
                req["To"] = to_date
        response = requests.post(
            self._url(endpoint), data=json.dumps(req), headers=self._headers())
        return response.json()

    def query_outgoing_invoices(self, invoice_id=None, status_id=None, year=None, from_date=None, to_date=None):
        """JSON parameters
            "Username": "Sender Username", required
            "Password": "Sender Password", required
            "CompanyId": "Sender Company Id (Oib)", required
            "SoftwareId": "Business Software (Erp) Id", required
            "CompanyBu": "Sender Business Unit (PJ)",

            "ElectronicId": "Filters single document",
            "StatusId": "Filters status. Valid options 10, 20, 30, 40, 45, 50, 60",
            "InvoiceYear": "Filters documents based on the year in which an invoice was sent",
            "InvoiceNumber": "Filters single document based on its number",
            "From": "YYYY-MM-DDThh:mm:ss or YYYY-MM-DD",
            "To": "YYYY-MM-DDThh:mm:ss or YYYY-MM-DD",
        """
        def validate_status(status_id):
            if status_id not in self.doc_status.keys():
                raise ValueError(
                    "invalid document status: {}".format(status_id))
        endpoint = self.api['queryOutbox'][0]
        req = self._credentials()
        if invoice_id:
            req["ElectronicId"] = invoice_id
        else:
            if status_id:
                validate_status(status_id)
                req["StatusId"] = status_id
            if from_date:
                req["From"] = from_date
            if to_date:
                req["To"] = to_date
        response = requests.post(
            self._url(endpoint), data=json.dumps(req), headers=self._headers())
        return response.json()

    def receive_invoice(self, invoice_id):
        """Download INCOMING and OUTGOING invoices.
        Returns JSON, False on error returned from API
        - response status.code is 200 (OK)
        - usually on requesting for non existent ElectronicId
        - error that should be handled:
        -{"ElectronicId": {"Value": "546468684", "Messages": ["Document: 546468684 not found"]}}
        Returns XML, True if the invoice exists and can be received.
        The second return value is inferred from response header "content-type".
        JSON parameters:
            "Username": "Sender Username", required
            "Password": "Sender Password", required
            "CompanyId": "Sender Company Id (Oib)", required
            "SoftwareId": "Business Software (Erp) Id", required
            "ElectronicId": "Electronic Document Id", required
            "CompanyBu": "Sender Business Unit (PJ)"        
        """
        endpoint = self.api['receive'][0]
        req = self._credentials()
        req["ElectronicId"] = str(invoice_id)
        response = requests.post(
            self._url(endpoint), data=json.dumps(req), headers=self._headers())
        content_type = response.headers.get('content-type', "")
        # response can be either XML or JSON - JSON is returned on error
        # NOTE: add checks if this can be application/xml;charset=utf-8
        if content_type == "text/xml;charset=utf-8":
            return response.text, True
        return response.json(), False

    def notify_import(self, invoice_id):
        """Notify import method is used for sending
        notifying MojEracun services that an invoice was successfully
        imported into an ERP solution.
        JSON parameters:
            "Username": "Sender Username", required
            "Password": "Sender Password", required
            "CompanyId": "Sender Company Id (Oib)", required
            "SoftwareId": "Business Software (Erp) Id", required
            "ElectronicId": "Electronic Document Id", required
            "CompanyBu": "Sender Business Unit (PJ)"
        URL parameter:
        -- ElectronicId - required
        -- ex. /apis/v2/notifyimport/123456
        """
        endpoint = self.api['notifyImport'][0]
        req = self._credentials()
        url = self._url(endpoint).format(invoice_id)
        response = requests.post(
            url, data=json.dumps(req), headers=self._headers())
        # should return: {"Status":"ok"}
        return response.json()

    def mark_paid(self, paid_date, invoice_id):
        """Mark paid method is used for sending information that an invoice is paid.
        JSON parameters:
            "Username": "Sender Username", required
            "Password": "Sender Password", required
            "CompanyId": "Sender Company Id (Oib)", required
            "SoftwareId": "Business Software (Erp) Id", required
            "ElectronicId": "Electronic Document Id", required
            "PaidDate": "Date when an invoice was paid", ISO datetime, required

            "CompanyBu": "Sender Business Unit (PJ)"
        """
        endpoint = self.api['markPaid'][0]
        req = self._credentials()
        req["PaidDate"] = paid_date
        req["ElectronicId"] = invoice_id
        response = requests.post(
            self._url(endpoint), data=json.dumps(req), headers=self._headers())
        # should return: {"ElectronicId": <int>, "InvoiceDate": <ISO date>, "Paid": <ISO date>}
        return response.json()

    def document_action(self, invoice_id, resend=True):
        """Either resends or cancels the invoice
        JSON parameters:
            "Username": "Sender Username", required
            "Password": "Sender Password", required
            "CompanyId": "Sender Company Id (Oib)", required
            "SoftwareId": "Business Software (Erp) Id", required
            "ElectronicId": "Electronic Document Id", required
            "Apply": resend | cancel, required

            "CompanyBu": "Sender Business Unit (PJ)"
        ERROR ex. (not really an error, just an invalid attmpt)
        "Apply": {
            "Value": "resend",
            "Messages": ["Action resend can be applied only on documents in status 30 (Sent) or 50 (Unsuccessful)."]}
        """
        endpoint = self.api['documentAction'][0]
        req = self._credentials()
        req["Apply"] = "resend" if resend else "cancel"
        req["ElectronicId"] = invoice_id
        response = requests.post(
            self._url(endpoint), data=json.dumps(req), headers=self._headers())
        # should return: {"ElectronicId": <int>, "InvoiceDate": <ISO date>, "Paid": <ISO date>}
        return response.json()

    def send_invoice(self, xml_str, important=False):
        """Send OUTGOING invoices.
        JSON parameters:
            "Username": "Sender Username", required
            "Password": "Sender Password", required
            "CompanyId": "Sender Company Id (Oib)", required
            "SoftwareId": "Business Software (Erp) Id", required
            "File": "Utf-8 encoded Xml File", type - string, required

            "CompanyBu": "Sender Business Unit (PJ)"        
            "HighImportanceReceive": bool
        EXAMPLE SEND:
        {
            "Username": 1083,
            "Password": "test123",
            "CompanyId": "99999999927",
            "CompanyBu": "",
            "SoftwareId": "Test-001",
            "File": "<?xml version=\"1.0\" encoding=\"UTF-8\"?><OutgoingInvoicesData>...</OutgoingInvoicesData></?xml>"

        }
        EXAMPLE RESPONSE:
        {
            "ElectronicId": 394167,
            "DocumentNr": "20156256",
            "DocumentTypeId": 1,
            "DocumentTypeName": "Račun",
            "StatusId": 30,
            "StatusName": "Sent",
            "RecipientBusinessNumber": "99999999927",
            "RecipientBusinessUnit": "",
            "RecipientBusinessName": "Test Klising d.o.o.",
            "Created": "2016-04-18T08:23:08.5879877+02:00",
            "Sent": "2016-04-18T08:23:09.6730491+02:00",
            "Modified": "2016-04-18T08:23:09.6840519+02:00",
            "Delivered": null
        }
        EXAMPLE ERRORS:
        {
            "Username": {
                "Value": "1808",
                "Messages": [
                    "Username and password are not valid"
                ]
            }
        }
        {
            "CompanyId": {
                "Value": "",
                "Messages": [
                    "CompanyId 999999999927 not found."
                ]
            }
        }
        """
        endpoint = self.api['send'][0]
        req = self._credentials()
        req["File"] = xml_str.decode()
        req["HighImportanceReceive"] = important
        response = requests.post(
            self._url(endpoint), data=json.dumps(req), headers=self._headers())
        return response.json()

    def update_document_processing_status(self, invoice_id, status_id="4", reject_reason=""):
        """Used to update the status on an INCOMING invoice.
        JSON parameters:
            "Username": "Sender Username", required
            "Password": "Sender Password", required
            "CompanyId": "Sender Company Id (Oib)", required
            "SoftwareId": "Business Software (Erp) Id", required
            "ElectronicId": "Electronic Document Id", required
            "CompanyBu": "Sender Business Unit (PJ)"

            "StatusId": "Defines PROCESSING status in user's system
                Valid options:
                    - "0": "APPROVED - Document is successfully approved by the recepient",
                    - "1": "REJECTED - Document is rejected by the recepient",
                    - "2": "PAYMENT_FULFILLED - Document is fully paid",
                    - "3": "PAYMENT_PARTIALLY_FULLFILLED – Document is partially paid",
                    - "4": "RECEIVING_CONFIRMED – Document successfully downloaded by the recepient",
                    - "99": "RECEIVED – Document received in the inbox of the recepient (e.g. FINA service)"
                REQUIRED
            "RejectReason": "If a document is rejected, one must send the reason why it was rejected"
                USED WITH STATUS 4 - gives additional rejection reason info to the sender
        JSON RETURN:
            - {"ElectronicId": <int>, "DokumentProcessStatus": <int, [0, 1, 2, 3, 4, 99]>, "UpdateDate": "2019-04-04T19:05:04.3818381+02:00"}
        """
        status_id_str = str(status_id)
        endpoint = self.api['updateDocumentStatus'][0]
        req = self._credentials()
        req["ElectronicId"] = invoice_id
        if status_id_str not in self.doc_process_status.keys():
            raise ValueError(
                "unsupported document process status: {}".format(status_id_str))
        if status_id_str == "1" and not reject_reason:
            raise ValueError(
                "status REJECTED must be used with additional 'RejectReason' field")
        if status_id_str == "1":
            req["RejectReason"] = reject_reason
        req["StatusId"] = status_id
        response = requests.post(
            self._url(endpoint), data=json.dumps(req), headers=self._headers())
        # should return: {"ElectronicId": <int>, "DokumentProcessStatus": 0, "UpdateDate": "2019-04-04T19:05:04.3818381+02:00"}
        return response.json()

    def query_processing_incoming_invoices(self, status_id=None, year=None, invoice_id=None, update_date=None, from_date=None, to_date=None):
        """Query invoices SENT TO the user company
        -- returns more data than query_incoming_invoices
        -- Addtional response data compared to queryInbox/Outbox:
            - IssueDate
            - DocumentProcessStatusId
            - DocumentProcessStatusName
            - AdditionalDokumentStatusId
            - RejectReason
        JSON parameters:
            "Username": "Sender Username", required
            "Password": "Sender Password", required
            "CompanyId": "Sender Company Id (Oib)", required
            "SoftwareId": "Business Software (Erp) Id", required

            "ElectronicId": "Filters single document",
            "StatusId": "Filters status. Valid options 0, 1, 2, 3"
            "InvoiceYear": "Filters documents based on the year in which an invoice was sent",
            "InvoiceNumber": "Filters single document based on its number",
            "From": "YYYY-MM-DDThh:mm:ss or YYYY-MM-DD",
            "To": "YYYY-MM-DDThh:mm:ss or YYYY-MM-DD",
            "ByUpdateDate": "Filters documents based on their update date rather than the date when they were sent",
        example response JSON:
        {
            "ElectronicId": 394162,
            "DocumentNr": "3-1-1",
            "DocumentTypeId": 1,
            "DocumentTypeName": "Invoice",
            "StatusId": 30,
            "StatusName": "Sent",
            "SenderBusinessNumber": "99999999927",
            "SenderBusinessUnit": "",
            "SenderBusinessName": "Test Klising d.o.o.",
            "Sent": "2016-04-18T08:13:03.177",
            "Delivered": null,
        -- ADDITIONAL FIELDS COMPARED TO queryInbox/Outbox
            "IssueDate": "2016-04-18T08:13:03.177",
            "DocumentProcessStatusId": null,
            "DocumentProcessStatusName": "",
            "AdditionalDokumentStatusId": null,
            "RejectReason": null
        }
        """
        endpoint = self.api['queryProcessingInbox'][0]
        req = self._credentials()
        if invoice_id: # skip other fields
            req["ElectronicId"] = invoice_id
        else:
            if status_id:
                status_id_str = str(status_id)
                if status_id_str not in self.doc_process_status.keys():
                    raise ValueError("unsupported document process status: {}".format(status_id_str))
                req["StatusId"] = status_id
            if year:
                req["InvoiceYear"] = year
            if from_date:
                req["From"] = from_date
            if to_date:
                req["To"] = to_date    
        response = requests.post(
            self._url(endpoint), data=json.dumps(req), headers=self._headers())
        return response.json()

    def query_processing_outgoing_invoices(self, status_id=None, year=None, invoice_id=None, update_date=None, from_date=None, to_date=None):
        """Query invoices SENT BY the user company
        -- returns more data than query_outgoing_invoices
        -- Addtional response data compared to queryInbox/Outbox:
            - IssueDate
            - DocumentProcessStatusId
            - DocumentProcessStatusName
            - AdditionalDokumentStatusId
            - RejectReason
        JSON parameters:
            "Username": "Sender Username", required
            "Password": "Sender Password", required
            "CompanyId": "Sender Company Id (Oib)", required
            "SoftwareId": "Business Software (Erp) Id", required

            "ElectronicId": "Filters single document",
            "StatusId": "Filters status. Valid options 0, 1, 2, 3"
            "InvoiceYear": "Filters documents based on the year in which an invoice was sent",
            "InvoiceNumber": "Filters single document based on its number",
            "From": "YYYY-MM-DDThh:mm:ss or YYYY-MM-DD",
            "To": "YYYY-MM-DDThh:mm:ss or YYYY-MM-DD",
            "ByUpdateDate": "Filters documents based on their update date rather than the date when they were sent",
        example response JSON:
        {
            "ElectronicId": 394162,
            "DocumentNr": "3-1-1",
            "DocumentTypeId": 1,
            "DocumentTypeName": "Invoice",
            "StatusId": 30,
            "StatusName": "Sent",
            "SenderBusinessNumber": "99999999927",
            "SenderBusinessUnit": "",
            "SenderBusinessName": "Test Klising d.o.o.",
            "Sent": "2016-04-18T08:13:03.177",
            "Delivered": null,
        -- ADDITIONAL FIELDS COMPARED TO queryInbox/Outbox
            "IssueDate": "2016-04-18T08:13:03.177",
            "DocumentProcessStatusId": null,
            "DocumentProcessStatusName": "",
            "AdditionalDokumentStatusId": null,
            "RejectReason": null
        }
        """
        endpoint = self.api['queryProcessingOutbox'][0]
        req = self._credentials()
        if invoice_id: # skip other fields
            req["ElectronicId"] = invoice_id
        else:
            if status_id:
                status_id_str = str(status_id)
                if status_id_str not in self.doc_process_status.keys():
                    raise ValueError("unsupported document process status: {}".format(status_id_str))
                req["StatusId"] = status_id
            if year:
                req["InvoiceYear"] = year
            if from_date:
                req["From"] = from_date
            if to_date:
                req["To"] = to_date    
        response = requests.post(
            self._url(endpoint), data=json.dumps(req), headers=self._headers())
        return response.json()

if __name__ == "__main__":
    # basic test to check all methods are working in demo environment
    # URL: http://demo.moj-eracun.hr
    from pprint import pformat
    from time import sleep

    cfg = {}
    with open("conf.json") as f:
        cfg = json.load(f)

    svc = MojEracun(cfg["Username"], cfg["Password"],
                    cfg["CompanyID"], cfg["SoftwareId"])
    ping_resp = svc.ping()
    if not ping_resp.get("Status", "") == "ok":
        raise RuntimeError("could not connect to moj-eracun.hr")
    print("# GOT PING")
    # queryInbox and outbox:
    print("# QUERY INBOX")
    inbox = svc.query_incoming_invoices()
    print(pformat(inbox), "\n", "-"*50)
    sleep(1)
    print("# QUERY OUTBOX")
    outbox = svc.query_outgoing_invoices()
    print(pformat(outbox), "\n", "-"*50)
    sleep(1)
    # attempt receive on known ElectronicId - got from queryInbox
    if inbox:
        invoice_id = inbox[-1]["ElectronicId"]
        rcv, ok = svc.receive_invoice(invoice_id)
        if ok:
            print("# receive got XML response", "\n", rcv[:100], "\n", "-"*50)
            sleep(1)
            svc.notify_import(invoice_id)
            print("# NOTIFIED IMPORT for", invoice_id)
        else:
            # dump first 100 chars
            print("# FAILED TO receive invoice", invoice_id,
                  '\n', pformat(rcv), "\n", "-"*50)

    print("# QUERY PROCESS INBOX")
    p_inbox = svc.query_processing_incoming_invoices()
    print(pformat(p_inbox))
    sleep(1)
    print("# QUERY PROCESS OUTBOX")
    p_outbox = svc.query_processing_outgoing_invoices()
    print(pformat(p_outbox))