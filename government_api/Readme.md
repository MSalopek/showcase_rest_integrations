### Install
```
pip install -r requirements.txt
```

### Use
```python
import EmaticaService


institution_code = "mock_code"
institution_subcode = "mock_subcode"

# if you don't provide credentials the default 
# - "Username" 
# - "Password" 
# - "CompanyID" 
# - "SoftwareId"
# from ./conf.json will be used
ws = EmaticaService()

# fetch all employees for an institution
# with institution_code & institution_subcode combination 
employees_list = ws.get_djelatnik(institution_code, institution_subcode)

processed = [process(i) for i in employees_list]

# etc.
```