# e-matica REST API communication service
# API documentation: https://matice-api-test.mzo.hr/swagger/index.html
import os
import json
import logging
from datetime import datetime

import requests
import asyncio

import aiohttp


class EmaticaService:
    """EmaticaService connects with e-Matica REST service APIs
    To connect with the e-Matica service provide the path to the configuration file
    containing the user's API credentials
    """

    def __init__(self):
        self.user = None
        self.password = None
        self.token = None
        self.auth_jwt = None # jwt can be cached
        self.auth_url = None
        self.req_timeout = None
        self.resources = None # resource URL map; ex. GetDjelatnik: <url>
        self._logger = logging.getLogger(__name__)
        self._load_cfg()

    def _load_cfg(self):
        """Load and validate config params.
        Raises ValueError on missing params.
        Take note to handle the error!
        """
        this_file = os.path.realpath(__file__)
        cfg_dir, _ = os.path.split(this_file)
        cfg_path = cfg_dir + "/cfg.json"
        with open(cfg_path) as in_file:
            cfg = json.load(in_file)
        self.user = cfg.get('Username')
        self.password = cfg.get('Password')
        self.token = cfg.get('Token')
        self.auth_url = cfg.get("AuthURL")
        self.resources = cfg.get("ResourceHandlers")
        self.req_timeout = cfg.get("SyncTimeout", 60) # default synchronous req timeout == 60 seconds
        # async request parameters
        self.sock_connect = cfg.get("ConnectTimeout", 30)
        self.sock_read = cfg.get("ReadTimeout", 30)
        self._validate_cfg()

    def _validate_cfg(self):
        if not self.user:
            raise ValueError("missing EmaticaService user")
        if not self.password:
            raise ValueError("missing EmaticaService password")            
        if not self.token:
            raise ValueError("missing EmaticaService token")
        if not self.auth_url: 
            raise ValueError("missing EmaticaService authorization URL")

    def _get_auth_headers(self):
        """Builds header with current JWT authentication
        """
        return {
            'accept': 'application/json',
            'Authorization': self.auth_jwt,
        }

    def _get_auth_req_params(self):
        """Builds parameters for requesting authentication JWT.
        """
        return {
            'Username': self.user,
            'Password': self.password,
            'Token': self.token,
        }

    def authenticate(self):
        """Fetch JWT from e-Matica. 
        JWT is stored for future use and may be refreshed by calling authenticate.
        Timestamp of latest successful auth request is saved in self.auth_ts.
        Raises Exception on any failure and logs the error.
        """
        headers = {
            'accept': 'application/json',
        }
        auth_params = self._get_auth_req_params()
        try:
            auth_resp = requests.post(self.auth_url, headers=headers, params=auth_params, timeout=self.req_timeout)
            auth_json = auth_resp.json()
            if auth_json:
                self.auth_jwt = auth_json
                self.auth_ts = datetime.now().timestamp()  # store last timestamp
                self._logger.info("get auth e-matica sucessful for: {}".format(self.user))
        except TimeoutError as e:
            self._logger.error("e-Matica authenticate timed out for #user {}".format(self.user))
            raise
        except Exception as e:
            self._logger.error("e-Matica authenticate failed with err:\n{}".format(e))
            raise

    
    def get_djelatnik(self, code, subcode):
        """Makes authorized GET request to e-matice /api/Djelatnik.
        Requests authorization if session is not authenticated (jwt not present).
        Raises error if url to /api/Djelatnik is not provided (not present in self.resources map).
        API rsponse is a JSON containing company employees; company speficied with code, subcode args.
        Supported url parameters:
            REQUIRED:
                Sifra:string                    
                Podsifra:string
            OPTIONAL (pagination params):
                CurrentPage:int32                    
                PageSize:int32                    
                NumberOfItemsToSkip:int32                    
                NumberOfItemsToTake:int32
        """
        if not self.auth_jwt:
            self.authenticate()

        auth_headers = self._get_auth_headers()            
        params = {
            'Sifra': code,
            'Podsifra': subcode,
        }

        url = self.resources.get("GetDjelatnik")
        if not url:
            raise ValueError("GetDjelatnik url not supported or not provided")
        resp = requests.get(url, headers=auth_headers, params=params, timeout=self.req_timeout)
        emps_list = resp.json()['entities']
        self._logger.info("get_djelatnici successful for #user {} with params: {} {}".format(self.user, code, subcode))
        return emps_list

    def get_djelatnik_oib(self, oib):
        """Makes authorized GET request to e-matice /api/Djelatnik/OIB.
        Requests authorization if session is not authenticated (jwt not present).
        Raises error if url to /api/Djelatnik/OIB is not provided (not present in self.resources map).
        API rsponse is a JSON containing single employee data speficied by employee OIB.
        Supported url parameters:
            REQUIRED:
                Oib:string                    
        """
        if not self.auth_jwt:
            self.authenticate()

        auth_headers = self._get_auth_headers()            
        params = {
            'Oib': oib,
        }

        url = self.resources.get("GetDjelatnikOIB")
        if not url:
            raise ValueError("GetDjelatnikOIB url not supported or not provided")
        resp = requests.get(url, headers=auth_headers, params=params, timeout=self.req_timeout)
        employee = resp.json()
        self._logger.info("get_djelatnici_oib successful for #user {} with params: {}".format(self.user, oib))
        return employee

    def get_skolske_godine(self, code, subcode):
        """Makes authorized GET request to e-matice /api/SkolskeGodine.
        Requests authorization if session is not authenticated (jwt not present).
        Raises error if url to /api/SkolskeGodine is not provided (not present in self.resources map).
        API rsponse is a JSON containing ALL available active and inactive school years.
        This is primarily used to fetch the CURRENTLY ACTIVE school year from list of years.
        Fetching this data is required for requesting /Odjeljenja, since that call requires SkolskaGodinaID from e-Matica system.
        Supported url parameters:
            OPTIONAL:
                CurrentPage::int32
                PageSize::int32
                NumberOfItemsToSkip::int32
                NumberOfItemsToTake::int32
        """
        if not self.auth_jwt:
            self.authenticate()
        auth_headers = self._get_auth_headers()
        params = {
            'Sifra': code,
            'Podsifra': subcode,
        }

        url = self.resources.get("GetSkolskeGodine")
        if not url:
            raise ValueError("GetSkolskeGodine url not supported or not provided")
        resp = requests.get(url, headers=auth_headers, params=params, timeout=self.req_timeout)
        years_list = resp.json()['entities']
        self._logger.info("get_skolske_godine successful for #user {} with params: {} {}".format(self.user, code, subcode))
        return years_list

    def get_odjeljenja(self, code, subcode):
        """Makes authorized GET request to e-matice /Odjeljenja
        Requests authorization if session is not authenticated (jwt not present).
        Raises error if url to /Odjeljenja is not provided (not present in self.resources map).
        API rsponse is a JSON containing date for all Sections (odjeljenja) speficied by required params code, subcode.

        Current school year (SkolskaGodinaId) is fetched before requesting /Odjeljenja. 
        Supported url parameters:
            REQUIRED:
                Sifra:string                    
                Podsifra:string
                SkolskaGodinaId:int32
            OPTIONAL:
                Oznaka::string
                Razred::string
                CurrentPage::int32
                PageSize::int32
                NumberOfItemsToSkip::int32
                NumberOfItemsToTake::int32
        Returns:
            SECTIONS in list form (odjeljenja)
            CURRENT SCHOOL YEAR NAME
        """
        def filter_yr(entities, year):
            for l in entities:
                for sl in l['skolskeGodine']:
                    if sl["skolskaGodinaId"] == year:
                        return sl["odjeljenja"]
            return {}

        if not self.auth_jwt:
            self.authenticate()
        auth_headers = self._get_auth_headers()
        # fetch current year ID
        year_resp = self.get_skolske_godine(code, subcode)
        year = list(filter(lambda y: y['trenutna'] == True, year_resp))[0]
        year_name = year.get('naziv')
        params = {
            'Sifra': code,
            'Podsifra': subcode,
            'SkolskaGodina': year['id'],
        }

        url = self.resources.get("GetOdjeljenja")
        if not url:
            raise ValueError("GetOdjeljenja url not supported or not provided")
        resp = requests.get(url, headers=auth_headers, params=params, timeout=self.req_timeout)
        # return only target year - this is just in case a call is made with empty SkolskaGodina
        deps_list = filter_yr(resp.json()['entities'], year["id"])
        self._logger.info("get_odjeljenja successful for #user {} with params: {} {}".format(self.user, code, subcode))
        # with open("odjeljenje-{}-{}.json".format(code, subcode), 'w') as out:
            # out.write(json.dumps(resp.json()))
        return deps_list, year_name

    def get_ucenici(self, code, subcode, yearID=None):
        """Makes authorized GET request to e-matice /api/Ucenik/GetFromUstanova.
        Requests authorization if session is not authenticated (jwt not present).
        Raises error if url to /api/Ucenik/GetFromUstanova is not provided (not present in self.resources map).
        API rsponse is a JSON containing date for all Ucenik (students) speficied by required params code, subcode.

        NOTE: only students (ucenici) for the current year are fetched. The current year is defined with 
        URL parameter "SkolskaGodinaId".
        Supported url parameters:
            REQUIRED:
                Sifra:string                    
                Podsifra:string
                SkolskaGodinaId:int32
            OPTIONAL:
                CurrentPage::int32
                PageSize::int32
                NumberOfItemsToSkip::int32
                NumberOfItemsToTake::int32
        """
        if not self.auth_jwt:
            self.authenticate()
        auth_headers = self._get_auth_headers()
        params = {
            'Sifra': code,
            'Podsifra': subcode,
        }
        # fetch current year ID if not provided
        if not yearID:
            year_resp = self.get_skolske_godine(code, subcode)
            fetched_yearID = list(filter(lambda y: y['trenutna'] == True, year_resp))[0]['id']
            params['SkolskaGodinaId'] = fetched_yearID # choose only current year students
        else:
            params['SkolskaGodinaId'] = yearID # choose only students for provided yearID

        url = self.resources.get("GetUcenici")
        if not url:
            raise ValueError("GetUcenici url not supported or not provided")
        resp = requests.get(url, headers=auth_headers, params=params, timeout=self.req_timeout)
        stud_list = resp.json()['entities']
        self._logger.info("get_ucenici successful for #user {} with params: {} {}".format(self.user, code, subcode))
        return stud_list

    def get_ucenik_oib(self, oib):
        """Makes authorized GET request to e-matice /api/Ucenik/{OIB}
        Requests authorization if session is not authenticated (jwt not present).
        Raises error if url to /api/Ucenik/is not provided (not present in self.resources map).
        API rsponse is a JSON containing single Ucenik (student) data speficied by Ucenik OIB.
        Supported url parameters:
            REQUIRED:
                OIB:string --> resource identifier, not an URL param
        """
        if not self.auth_jwt:
            self.authenticate()
        auth_headers = self._get_auth_headers()

        url = self.resources.get("GetUcenikOIB") + str(oib)
        if not url:
            raise ValueError("GetUcenikOIB url not supported or not provided")
        resp = requests.get(url, headers=auth_headers, timeout=self.req_timeout)
        student = resp.json()
        self._logger.info("get_ucenik_oib successful for #user {} with params: {}".format(self.user, oib))
        return student

    def get_razredi(self):
        """Makes authorized GET request to e-matice /api/Razredi
        Requests authorization if session is not authenticated (jwt not present).
        Raises error if url to /api/Razredi is not provided (not present in self.resources map).
        API rsponse is a JSON containing all razredi data (classes).
        Supported url parameters:
        """
        if not self.auth_jwt:
            self.authenticate()
        auth_headers = self._get_auth_headers()

        url = self.resources.get("GetRazredi")
        if not url:
            raise ValueError("GetRazredi url not supported or not provided")
        resp = requests.get(url, headers=auth_headers, timeout=self.req_timeout)
        resp_json = resp.json()
        razredi_dict = {e['id']:e for e in resp_json['entities']}
        self._logger.info("get_razredi successful for #user {}".format(self.user))
        return razredi_dict

    def async_get_ucenici_oib(self, oib_lst, loop):
        """Makes async authorized GET requests to e-Matice /api/Ucenik/{OIB}
        using grequests library.
        Request parameter OIB is an element of oib_list.
        The request header contains required auth Bearer Token.
        The async http get requests are not blocking but the 
        async_get_ucenici_oib function is blocking. 
        
        Limit is the maximum number of concurrent api calls.

        Returns a list of requests AND errors.
        """
        if not oib_lst:
            self._logger.error("ASYNC get_ucenici_OIB got empty oibs list. Aborted.")
            return []

        if not self.auth_jwt:
            self.authenticate()
        auth_headers = self._get_auth_headers()
    
        async def fetch(session, url):
            # NOTE:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=600, sock_connect=self.sock_connect, sock_read=self.sock_read), raise_for_status=True) as response:            
                return await response.json()

        async def fetch_all(urls):
            tasks = []
            # Fetch all responses within one Client session,
            # keep connection alive for all requests.
            async with aiohttp.ClientSession(headers=auth_headers) as session:
                for url in urls:
                    task = asyncio.ensure_future(fetch(session, url))
                    tasks.append(task)
                responses = await asyncio.gather(*tasks, return_exceptions=True)
                return responses
        
        urls = []
        for oib in oib_lst:
            urls.append(self.resources.get("GetUcenikOIB") + str(oib))

        future = asyncio.ensure_future(fetch_all(urls))
        resp = loop.run_until_complete(future)

        resp_json = [r for r in resp if not isinstance(r, Exception)]
        self._logger.info("Finished async_get_ucenici_oib. Done: {} Failed: {}".format(len(resp_json), len(oib_lst)-len(resp_json)))
        return resp_json


if __name__ == "__main__":
    from pprint import pformat
    # basic test - do authenticate since there is no /ping method on the API 
    # test confirms authentication can be successfully performed
    svc = EmaticaService()
    print(svc.user, svc.password, svc.token, sep="\n")
    sifra = '10-317-001'
    podsifra = '0-0'
    # averages 15 seconds in test environment
    print("Waiting on authenticate")
    svc.authenticate()
    print(svc.auth_jwt, svc.auth_ts, sep="\n")

    # get djelatnici from API -> confirm auth OK and  fetch /api/Djelatnik OK
    # 'Sifra': '10-317-001',
    # 'Podsifra': '0-0',
    # emps = svc.get_djelatnik('10-317-001', '0-0')
    # print(pformat(emps))

    # test employee OIB: 76195363193
    # print("Waiting on get_djelatnik_oib")
    # emp = svc.get_djelatnik_oib('76195363193')
    # print(pformat(emp))

    # 2019./2020. is id=20
    # years = svc.get_skolske_godine(sifra, podsifra)
    # print(pformat(years))

    # sections = svc.get_odjeljenja(sifra, podsifra)
    # print(pformat(sections))

    # students = svc.get_ucenici(sifra, podsifra)
    # print(pformat(students))

    loop = asyncio.get_event_loop()    
    oib_list = ["02361140078", "43708356074"]
    res = svc.async_get_ucenici_oib(oib_list, loop)
    print(pformat(res))
    print(len(res))