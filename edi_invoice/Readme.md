### Install
```
pip install -r requirements.txt
```

### Use
```python
import stream
from lxml import etree

from edi_invoice.eracun import MojEracun
from edi_invoice.parser import InvoiceParser

username = "mock_dont_use_this"
password = "mock_dont_use_this"
company_id = "mock_dont_use_this"
software_id = "mock_dont_use_this"
params = {"some": "mock_params", "some_other": "mock_param"}

# API client instance
api = MojEracun(
    username,
    password,
    company_id,
    software_id
)

parseXML = InvoiceParser()

# make the request
resp = api.query_processing_outgoing_invoices(**params)

# get invoice envelope and process it
raw = io.BytesIO(resp.encode('utf-8'))
root = etree.parse(raw).getroot()
root_ns = root.nsmap

# this elem has all relevant data
inv_elem = root.find(".//default:OutgoingInvoice", root_ns)
envelope = inv_elem.find(".//default:InvoiceEnvelope", root_ns)
if envelope is None:
    raise ValueError("Got none envelope")

# process this dict further after parsing
data_dict = parseXML(envelope[0])
```