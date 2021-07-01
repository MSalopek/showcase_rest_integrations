import xml.etree.ElementTree as ET
from collections import defaultdict

import base64


class InvoiceParser(object):
    """ InvoiceParser parses Fina eRacun Invoice envelopes (IncomingInvoiceEnvelope) and retrieves relevant data
    about the supplier, customer, headers and invoice lines.
    Basic usage:
    -- instantiate invoice parser with xml data: InvoiceParser(xmlData)
    -- run parser by calling Run() on the parser instance

    :param: xml -- XML data
    :param: xml_is_string -- specifies whether XML data gets provided as file or string"""

    # used for stripping namespaces
    ns_filter = (
        "{urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2}",
        "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}",
        "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}",
        "{urn:oasis:names:specification:ubl:schema:xsd:Invoice-2}"
    )

    def __init__(self, xml=None, xml_is_string=True):
        self.xml = xml
        self.xml_is_string = xml_is_string
        self.xml_root = self._load_xml_root()

    def __call__(self, xml_root):
        self.xml_root = xml_root
        return self.Run()
    
    def _load_xml_root(self):
        """
        If provided xml is A FILE load it as file.
        ELSE treat it as STRING
        """
        if not self.xml:
            return None
        if self.xml_is_string:
            return ET.fromstring(self.xml)
        else:
            tree = ET.parse(self.xml)
            return tree.getroot()

    def _post_process_result_dict(self, result):
        supplier = {
            'edi_supplier_id': result.get('AccountingSupplierParty', {}).get('EndpointID'),
            'edi_supplier_identificator': result.get('AccountingSupplierParty', {}).get('PartyIdentification', {}).get('ID'),
            'edi_supplier_name': result.get('AccountingSupplierParty', {}).get('PartyName', {}).get('Name'),
            'edi_supplier_street': result.get('AccountingSupplierParty', {}).get('PostalAddress', {}).get('StreetName'),
            'edi_supplier_city': result.get('AccountingSupplierParty', {}).get('PostalAddress', {}).get('CityName'),
            'edi_supplier_postal_code': result.get('AccountingSupplierParty', {}).get('PostalAddress', {}).get('PostalZone'),
            'edi_supplier_country_code': result.get('AccountingSupplierParty', {}).get('PostalAddress', {}).get('Country', {}).get('IdentificationCode'),
            'edi_supplier_company_id': result.get('AccountingSupplierParty', {}).get('PartyTaxScheme', {}).get('CompanyID'),
            'edi_supplier_tax_scheme_code': result.get('AccountingSupplierParty', {}).get('PartyTaxScheme', {}).get('TaxScheme', {}).get('ID'),
            'edi_supplier_registration_name': result.get('AccountingSupplierParty', {}).get('PartyLegalEntity', {}).get('RegistrationName'),
            'edi_supplier_telephone': result.get('AccountingSupplierParty', {}).get('Contact', {}).get('Telephone'),
            'edi_supplier_email': result.get('AccountingSupplierParty', {}).get('Contact', {}).get('ElectronicMail'),
        }
        customer = {
            'edi_customer_id': result.get('AccountingCustomerParty', {}).get('EndpointID'),
            'edi_customer_identificator': result.get('AccountingCustomerParty', {}).get('PartyIdentification', {}).get('ID'),
            'edi_customer_name': result.get('AccountingCustomerParty', {}).get('PartyName', {}).get('Name'),
            'edi_customer_street': result.get('AccountingCustomerParty', {}).get('PostalAddress', {}).get('StreetName'),
            'edi_customer_city': result.get('AccountingCustomerParty', {}).get('PostalAddress', {}).get('CityName'),
            'edi_customer_postal_code': result.get('AccountingCustomerParty', {}).get('PostalAddress', {}).get('PostalZone'),
            'edi_customer_country_code': result.get('AccountingCustomerParty', {}).get('PostalAddress', {}).get('Country', {}).get('IdentificationCode'),
            'edi_customer_company_id': result.get('AccountingCustomerParty', {}).get('PartyTaxScheme', {}).get('CompanyID'),
            'edi_customer_tax_scheme_code': result.get('AccountingCustomerParty', {}).get('PartyTaxScheme', {}).get('TaxScheme', {}).get('ID'),
            'edi_customer_registration_name': result.get('AccountingCustomerParty', {}).get('PartyLegalEntity', {}).get('RegistrationName'),
            'edi_customer_telephone': result.get('AccountingCustomerParty', {}).get('Contact', {}).get('Telephone'),
            'edi_customer_email': result.get('AccountingCustomerParty', {}).get('Contact', {}).get('ElectronicMail'),
        }
        payment_model, payment_reference = self._parse_payment_id(
            result.get('PaymentMeans', {}).get('PaymentID'))
        invoice_header = {
            # for CreditNoteEnvelopes
            "document_reference": result.get("InvoiceDocumentReference"),
            'currency': result.get('TaxCurrencyCode'),
            'due_date': result.get('DueDate'),
            'customization_id': result.get('CustomizationID'),
            'edi_supplier_invoice_id': result.get("ID"),
            'tax_amount': result.get('TaxTotal', {}).get('TaxAmount'),
            'tax_percent': result.get('TaxTotal', {}).get('TaxSubtotal', {}).get('TaxCategory', {}).get('Percent'),
            'tax_exemption_reason': result.get('TaxTotal', {}).get('TaxSubtotal', {}).get('TaxCategory', {}).get('TaxExemptionReason'),
            'taxable_amount': result.get('TaxTotal', {}).get('TaxSubtotal', {}).get('TaxableAmount'),
            'iban': result.get('PaymentMeans', {}).get('PayeeFinancialAccount', {}).get('ID'),
            'instruction_note': result.get('PaymentMeans', {}).get('InstructionNote'),
            'payment_means_code': result.get('PaymentMeans', {}).get('PaymentMeansCode'),
            'payment_id': result.get('PaymentMeans', {}).get('PaymentID'),
            'payable_amount': result.get("LegalMonetaryTotal", {}).get("PayableAmount"),
            'payment_model': payment_model,
            'payment_reference':  payment_reference,
        }
        pdf_document = {
            "pdf_document": result.get("PdfDocument")
        }
        invoice_lines = self._flatten_invoice_lines(result)
        return {
            "supplier": supplier,
            "customer": customer,
            "invoice_header": invoice_header,
            "invoice_lines": invoice_lines,
            "pdf_document": pdf_document,  # additional pdf document
        }

    def _flatten_invoice_lines(self, result):
        flattened_invoice_lines = []
        if "InvoiceLines" in result:
            for i in result["InvoiceLines"]:
                # Tax can be under Item or under InvoiceLine
                # usually when under Item it has a tag ClassifiedTaxCategory
                # on InvoiceLine it has a tag TaxCategory
                # the 3 variables below handle both cases so the tax is never empty 
                tax_id = i.get('Items', {}).get('ClassifiedTaxCategory', {}).get('ID')
                if not tax_id:
                    tax_id = i.get("TaxID")
                tax_percent = i.get('Items', {}).get('ClassifiedTaxCategory', {}).get('Percent')
                if not tax_percent:
                    tax_percent = i.get("TaxPercent")
                tax_exempt = i.get('Items', {}).get('ClassifiedTaxCategory', {}).get('TaxExemptionReason')
                if not tax_exempt:
                    tax_exempt = i.get('TaxExemptionReason')
                flattened_invoice_lines.append({
                    'edi_line_id': i.get('ID'),
                    'edi_line_name': i.get('Items', {}).get('Name'),
                    'edi_line_description': i.get('Items', {}).get('Description'),
                    'invoiced_quantity': i.get('InvoicedQuantity'),
                    'invoiced_amount': i.get('LineExtensionAmount'),
                    'single_unit_price': i.get('Price', {}).get('PriceAmount'),
                    'tax_category_id': tax_id,
                    'tax_percent':  tax_percent,
                    'tax_exemption_reason': tax_exempt,
                    'tax_scheme_code':  i.get('Items', {}).get('ClassifiedTaxCategory', {}).get('TaxScheme', {}).get('ID'),
                })
            return flattened_invoice_lines
        return flattened_invoice_lines

    def prettify_tag(self, tag):
        """Strip namespaces from XML element tags"""
        pretty_tag = tag
        for ns in self.ns_filter:
            pretty_tag = pretty_tag.replace(ns, '')
        return pretty_tag

    def _parseInvoiceLineItem(self, xml_element):
        nested_fields = [
            "SellersItemIdentification",
            "ClassifiedTaxCategory",
        ]
        item_data = defaultdict(dict)
        for sub in xml_element:
            tag = self.prettify_tag(sub.tag)
            if tag in nested_fields:
                if tag == "SellersItemIdentification":
                    for child in sub:
                        child_tag = self.prettify_tag(child.tag)
                        item_data[child_tag] = child.text
                elif tag == "ClassifiedTaxCategory":
                    tax_dict = defaultdict(dict)
                    for child in sub:
                        child_tag = self.prettify_tag(child.tag)
                        if child_tag == "TaxScheme":
                            tax_scheme_data = defaultdict(dict)
                            for next_child in child:
                                next_child_tag = self.prettify_tag(
                                    next_child.tag)
                                tax_scheme_data[next_child_tag] = next_child.text
                            tax_dict["TaxScheme"] = dict(tax_scheme_data)
                        else:
                            tax_dict[child_tag] = child.text
                    item_data["ClassifiedTaxCategory"] = dict(tax_dict)
            else:
                item_data[tag] = sub.text
        return dict(item_data)

    def parseInvoiceLine(self, xml_element):
        invoice_line_dict = defaultdict(dict)
        for child in xml_element:
            tag = self.prettify_tag(child.tag)
            if tag == "Item":
                invoice_line_dict["Items"] = self._parseInvoiceLineItem(child)
            # done
            elif tag == "Price":
                invoice_line_dict["Price"] = {}
                for sub in child:
                    invoice_line_dict["Price"][self.prettify_tag(
                        sub.tag)] = sub.text
            elif tag == "InvoicedQuantity":
                invoice_line_dict["InvoicedQuantity"] = child.text
                invoice_line_dict["unitCode"] = child.attrib['unitCode']
            elif tag == "LineExtensionAmount":
                invoice_line_dict["LineExtensionAmount"] = child.text
                invoice_line_dict["currencyID"] = child.attrib['currencyID']
            elif tag == "TaxTotal":
                for sub in child:
                    pretty_tag = self.prettify_tag(sub.tag)
                    if pretty_tag == "TaxAmount":
                        invoice_line_dict["TaxAmount"] = sub.text
                    if pretty_tag == "TaxSubtotal":
                        for third in sub:
                            p_third_tag = self.prettify_tag(third.tag)
                            if p_third_tag == "TaxCategory":
                                for fourth in third:
                                    p_fourth_tag = self.prettify_tag(fourth.tag)
                                    if p_fourth_tag == "ID":
                                        invoice_line_dict["TaxID"] = fourth.text
                                    if p_fourth_tag == "Percent":
                                        invoice_line_dict["TaxPercent"] = fourth.text
                                    if p_fourth_tag == "TaxExemptionReason":
                                        invoice_line_dict["TaxExemptionReason"] = fourth.text
            else:
                invoice_line_dict[tag] = child.text
        return dict(invoice_line_dict)

    def parseLegalMonetaryTotal(self, xml_element):
        """<cac:LegalMonetaryTotal>
            <cbc:LineExtensionAmount currencyID="HRK">2996.44</cbc:LineExtensionAmount>
                .........
            </cac:LegalMonetaryTotal>
        NOTE:
        # currencyID is not extracted - there is a currencyID for
        # an each and every invoice line which is extracted from InvoiceLine element
        """
        monetary_total = defaultdict(dict)
        for elem in xml_element:
            tag = self.prettify_tag(elem.tag)
            monetary_total[tag] = elem.text
        return dict(monetary_total)

    def parseTaxTotal(self, xml_element):
        """<cac:TaxTotal>
                <cbc:TaxAmount currencyID="HRK">0.00</cbc:TaxAmount>
                <cac:TaxSubtotal>
                    <cbc:TaxableAmount currencyID="HRK">2996.44</cbc:TaxableAmount>
                    <cbc:TaxAmount currencyID="HRK">0.00</cbc:TaxAmount>
                    <cac:TaxCategory>
                        <cbc:ID>E</cbc:ID>
                        <cbc:Percent>0</cbc:Percent>
                        <cbc:TaxExemptionReason>...</cbc:TaxExemptionReason>
                        <cac:TaxScheme>
                            <cbc:ID>VAT</cbc:ID>
                        </cac:TaxScheme>
                    </cac:TaxCategory>
                </cac:TaxSubtotal>
        </cac:TaxTotal>
        """
        tax_total = defaultdict(dict)
        for elem in xml_element:
            tag = self.prettify_tag(elem.tag)
            if tag == "TaxSubtotal":
                tax_subtotal = defaultdict(dict)
                for child in elem:
                    child_tag = self.prettify_tag(child.tag)
                    if child_tag == "TaxCategory":
                        category = defaultdict(dict)
                        for sub in child:
                            sub_tag = self.prettify_tag(sub.tag)
                            category[sub_tag] = sub.text
                            if sub_tag == "TaxScheme":
                                tax_scheme_data = defaultdict(dict)
                                for next_child in sub:
                                    next_child_tag = self.prettify_tag(
                                        next_child.tag)
                                    tax_scheme_data[next_child_tag] = next_child.text
                                category["TaxScheme"] = dict(tax_scheme_data)
                        tax_subtotal["TaxCategory"] = dict(category)
                    else:
                        tax_subtotal[child_tag] = child.text
                tax_total["TaxSubtotal"] = dict(tax_subtotal)
            else:
                tax_total[tag] = elem.text
        return dict(tax_total)

    def parsePaymentMeans(self, xml_element):
        payment_means = defaultdict(dict)
        for elem in xml_element:
            tag = self.prettify_tag(elem.tag)
            if tag == "PayeeFinancialAccount":
                fiancial_acc = defaultdict(dict)
                for child in elem:
                    child_tag = self.prettify_tag(child.tag)
                    if child_tag == "FinancialInstitutionBranch":
                        financial_inst = defaultdict(dict)
                        for sub in child:
                            sub_tag = self.prettify_tag(sub.tag)
                            financial_inst[sub_tag] = sub.text
                        fiancial_acc["FinancialInstitutionBranch"] = dict(
                            financial_inst)
                    else:
                        fiancial_acc[child_tag] = child.text
                payment_means["PayeeFinancialAccount"] = dict(fiancial_acc)
            else:
                payment_means[tag] = elem.text
        return dict(payment_means)

    def _parse_payment_id(self, string):
        """<cbc:PaymentID>HR02 3</cbc:PaymentID>
        PaymentID contains PaymentModel and PaymentReference
        PaymentModel consists of first 4 characters while the
        remainder (exclucing whitespace) comprises the PaymentReference"""
        if string is None:
            return None, None
        return string[0:4], string[4:].lstrip()

    def parseAccountingParty(self, xml_element):
        """ There may be more than 1 supplier party per invoice:
        EXAMPLE:
        <cac:AccountingSupplierParty>
            <cac:Party>
                <cbc:EndpointID schemeID="9934">65723536010</cbc:EndpointID>
                ......
        </cac:Party>
        </cac:AccountingSupplierParty>
        -> NOTE: This example implies the existence of > 1 suppliers in 1 invoice

        ### function can handle both Customer and Supplier parties ###
        ### IF MULTIPLE SUPPLIERS OR CUSTOMERS ONLY THE LAST ONE IS RETURNED ###
        """
        single_child_tags = ("PartyIdentification",
                             "PartyName", "PartyLegalEntity", "Contact")
        party = defaultdict(dict)
        for elem in xml_element:
            party_tag = self.prettify_tag(elem.tag)
            if party_tag == "Party":
                for sub_elem in elem:
                    sub_elem_tag = self.prettify_tag(sub_elem.tag)
                    if sub_elem_tag in single_child_tags:
                        stuff = defaultdict(dict)
                        for child in sub_elem:
                            child_tag = self.prettify_tag(child.tag)
                            stuff[child_tag] = child.text
                        party[sub_elem_tag] = dict(stuff)
                    elif sub_elem_tag == "PostalAddress":
                        address = defaultdict(dict)
                        for child in sub_elem:
                            child_tag = self.prettify_tag(child.tag)
                            if child_tag == "Country":
                                country = defaultdict(dict)
                                for next_child in child:
                                    next_child_tag = self.prettify_tag(
                                        next_child.tag)
                                    country[next_child_tag] = next_child.text
                                address["Country"] = dict(country)
                            else:
                                address[child_tag] = child.text
                        party[sub_elem_tag] = dict(address)
                    elif sub_elem_tag == "PartyTaxScheme":
                        party_tax = defaultdict(dict)
                        for child in sub_elem:
                            child_tag = self.prettify_tag(child.tag)
                            if child_tag == "TaxScheme":
                                tax_scheme = defaultdict(dict)
                                for next_child in child:
                                    next_child_tag = self.prettify_tag(
                                        next_child.tag)
                                    tax_scheme[next_child_tag] = next_child.text
                                party_tax["TaxScheme"] = dict(tax_scheme)
                            else:
                                party_tax[child_tag] = child.text
                        party[sub_elem_tag] = dict(party_tax)
                    else:
                        party[sub_elem_tag] = sub_elem.text
        return dict(party)

    def parseInvoicePeriod(self, xml_element):
        """Parses invoice periods. This is relevant for
        files with multiple invoice lines.
        NOTE:
            # if there is no invoice period "InvoicePeriod" key
            # IS NOT in the result dictionary
        """
        invoice_period = defaultdict(dict)
        for elem in xml_element:
            tag = self.prettify_tag(elem.tag)
            invoice_period[tag] = elem.text
        return dict(invoice_period)

    def parsePdfDocument(self, xml_element):
        """Pdf document gets extracted from soap envelopes.
        This step is necessary because parsing removes various
        control caracters from strings. Pdf doc is returned as bytes
        object decoded from base64"""
        pdf_doc = ""
        for elem in xml_element:
            if self.prettify_tag(elem.tag) == "Attachment":
                for child in elem:
                    if self.prettify_tag(child.tag) == "EmbeddedDocumentBinaryObject":
                        pdf_doc = base64.b64encode(child.text.strip().encode('utf-8')) # strip whitespaces on chunked files
        if pdf_doc:
            return pdf_doc
        return None

    def Run(self):
        sol = defaultdict(dict)
        sol["Note"] = ""
        sol["InvoiceLines"] = []
        sol["AccountingSupplierParty"] = []
        sol["AccountingCustomerParty"] = []
        for elem in self.xml_root:
            tag = self.prettify_tag(elem.tag)
            if tag == 'UBLExtensions':
                # we do not need this data ATM
                continue
            if tag == 'InvoiceLine':
                sol["InvoiceLines"].append(self.parseInvoiceLine(elem))
            elif tag == "LegalMonetaryTotal":
                sol["LegalMonetaryTotal"] = self.parseLegalMonetaryTotal(elem)
            elif tag == "TaxTotal":
                sol["TaxTotal"] = self.parseTaxTotal(elem)
            elif tag == "PaymentMeans":
                sol["PaymentMeans"] = self.parsePaymentMeans(elem)
            elif tag == "AccountingSupplierParty":
                sol["AccountingSupplierParty"] = self.parseAccountingParty(
                    elem)
            elif tag == "AccountingCustomerParty":
                sol["AccountingCustomerParty"] = self.parseAccountingParty(
                    elem)
            elif tag == "InvoicePeriod":
                sol["InvoicePeriod"] = self.parseInvoicePeriod(elem)
            elif tag == "AdditionalDocumentReference":  # additional pdf
                sol["PdfDocument"] = self.parsePdfDocument(elem)
            elif tag == "Note":
                if elem.text is not None:
                    if not sol["Note"]:
                        sol["Note"] = elem.text
                    else:
                        sol["Note"] += "\n" + str(elem.text)
            else:
                # assumes element has no children
                sol[tag] = elem.text
        sol = dict(sol)
        # post processing flattens excessive nesting
        return self._post_process_result_dict(sol)


class CreditNoteParser(InvoiceParser):
    """CreditNoteParser handles CreditNoteEnvelopes found in IncomingInvoiceEnvelope
    part of the response from Fina-eRacun service
    -- CreditLine is treated as InvoiceLine to satisfy db model
    -- basic use: see InvoiceParser"""

    def __init__(self, xml=None, xml_is_string=True):
        super(CreditNoteParser, self).__init__(xml, xml_is_string)

    def _post_process_result_dict(self, result):
        res = super(CreditNoteParser, self)._post_process_result_dict(result)
        res["invoice_header"]["due_date"] = result.get("IssueDate")
        return res

    def parseInvoiceLine(self, xml_element):
        """Overriden so CreditedQuantity in CreditNoteLine
        can be treated as InvoicedQuantity to satisfy db model"""
        invoice_line_dict = defaultdict(dict)
        for child in xml_element:
            tag = self.prettify_tag(child.tag)
            if tag == "Item":
                invoice_line_dict["Items"] = self._parseInvoiceLineItem(child)
            # done
            elif tag == "Price":
                invoice_line_dict["Price"] = {}
                for sub in child:
                    invoice_line_dict["Price"][self.prettify_tag(
                        sub.tag)] = sub.text
            elif tag == "CreditedQuantity":
                invoice_line_dict["InvoicedQuantity"] = child.text
                invoice_line_dict["unitCode"] = child.attrib['unitCode']
            elif tag == "LineExtensionAmount":
                invoice_line_dict["LineExtensionAmount"] = child.text
                invoice_line_dict["currencyID"] = child.attrib['currencyID']
            else:
                invoice_line_dict[tag] = child.text
        return dict(invoice_line_dict)

    def parseBillingReference(self, xml_element):
        """<cac:BillingReference>
                <cac:InvoiceDocumentReference>
                    <cbc:ID>6489/JP2/8</cbc:ID>
                    <cbc:IssueDate>2019-10-02</cbc:IssueDate>
                </cac:InvoiceDocumentReference>
            </cac:BillingReference>"""
        return xml_element[0][0].text

    def Run(self):
        """Overriden so CreditNoteLine gets treated as InvoiceLine
        to satisfy db model"""
        sol = defaultdict(dict)
        sol["Note"] = ""
        sol["InvoiceLines"] = []
        sol["AccountingSupplierParty"] = []
        sol["AccountingCustomerParty"] = []
        for elem in self.xml_root:
            tag = self.prettify_tag(elem.tag)
            if tag == 'UBLExtensions':
                # we do not need this data ATM
                continue
            if tag == 'CreditNoteLine':
                sol["InvoiceLines"].append(self.parseInvoiceLine(elem))
            elif tag == "LegalMonetaryTotal":
                sol["LegalMonetaryTotal"] = self.parseLegalMonetaryTotal(elem)
            elif tag == "TaxTotal":
                sol["TaxTotal"] = self.parseTaxTotal(elem)
            elif tag == "PaymentMeans":
                sol["PaymentMeans"] = self.parsePaymentMeans(elem)
            elif tag == "AccountingSupplierParty":
                sol["AccountingSupplierParty"] = self.parseAccountingParty(
                    elem)
            elif tag == "AccountingCustomerParty":
                sol["AccountingCustomerParty"] = self.parseAccountingParty(
                    elem)
            elif tag == "InvoicePeriod":
                sol["InvoicePeriod"] = self.parseInvoicePeriod(elem)
            elif tag == "AdditionalDocumentReference":
                sol["PdfDocument"] = self.parsePdfDocument(elem)
            elif tag == "Note":
                if elem.text is not None:
                    if not sol["Note"]:
                        sol["Note"] = elem.text
                    else:
                        sol["Note"] += "\n" + str(elem.text)
            else:
                # assumes element has no children
                sol[tag] = elem.text
        sol = dict(sol)
        # post processing flattens excessive nesting
        return self._post_process_result_dict(sol)


if __name__ == "__main__":
    # run from this file's directory
    from pprint import pformat
    # with open("./examples/primjer-2020-01-14 više_oporezivih.xml", 'rb') as f:
    with open("./examples/585473_credit_note.xml", 'rb') as f:
        p = CreditNoteParser(f, False)
        r = p.Run()
        print(pformat(r["invoice_header"]))
        print(pformat(r['invoice_lines']))
        # print(r['pdf_document'])