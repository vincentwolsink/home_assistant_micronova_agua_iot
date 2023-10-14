"""py_agua_iot provides controlling heating devices connected via
the IOT Agua platform of Micronova
"""
import asyncio
import jwt
import json
import logging
import re
import time
import httpx

_LOGGER = logging.getLogger(__name__)

API_PATH_APP_SIGNUP = "/appSignup"
API_PATH_LOGIN = "/userLogin"
API_PATH_REFRESH_TOKEN = "/refreshToken"
API_PATH_DEVICE_LIST = "/deviceList"
API_PATH_DEVICE_INFO = "/deviceGetInfo"
API_PATH_DEVICE_REGISTERS_MAP = "/deviceGetRegistersMap"
API_PATH_DEVICE_BUFFER_READING = "/deviceGetBufferReading"
API_PATH_DEVICE_JOB_STATUS = "/deviceJobStatus/"
API_PATH_DEVICE_WRITING = "/deviceRequestWriting"
API_LOGIN_APPLICATION_VERSION = "1.6.0"
DEFAULT_TIMEOUT_VALUE = 30

HEADER_ACCEPT = "application/json, text/javascript, */*; q=0.01"
HEADER_CONTENT_TYPE = "application/json"
HEADER = {"Accept": HEADER_ACCEPT, "Content-Type": HEADER_CONTENT_TYPE}


def parser(string):
    string = string.replace(" ", "")

    def splitby(string, separators):
        lis = []
        current = ""
        for ch in string:
            if ch in separators:
                lis.append(current)
                lis.append(ch)
                current = ""
            else:
                current += ch
        lis.append(current)
        return lis

    lis = splitby(string, "+-")

    def evaluate_mul_div(string):
        lis = splitby(string, "x*/")
        if len(lis) == 1:
            return lis[0]

        output = float(lis[0])
        lis = lis[1:]

        while len(lis) > 0:
            operator = lis[0]
            number = float(lis[1])
            lis = lis[2:]

            if operator == "x":
                output *= number

            elif operator == "*":
                output *= number

            elif operator == "/":
                output /= number

        return output

    for i in range(len(lis)):
        lis[i] = evaluate_mul_div(lis[i])

    output = float(lis[0])
    lis = lis[1:]

    while len(lis) > 0:
        operator = lis[0]
        number = float(lis[1])
        lis = lis[2:]

        if operator == "+":
            output += number
        elif operator == "-":
            output -= number

    return int(output)


class aguaiot(object):
    def __init__(
        self,
        api_url,
        customer_code,
        email,
        password,
        unique_id,
        login_api_url=None,
        brand_id=1,
        api_login_application_version=API_LOGIN_APPLICATION_VERSION,
    ):
        self.api_url = api_url.rstrip("/")
        self.customer_code = str(customer_code)
        self.email = email
        self.password = password
        self.unique_id = unique_id
        self.brand_id = str(brand_id)
        self.login_api_url = login_api_url
        self.api_login_application_version = api_login_application_version
        self.token = None
        self.token_expires = None
        self.refresh_token = None
        self.devices = list()

    async def connect(self):
        await self.register_app_id()
        await self.login()
        await self.fetch_devices()
        await self.fetch_device_information()

    def _headers(self):
        """Correctly set headers for requests to Agua IOT."""

        return {
            "Accept": HEADER_ACCEPT,
            "Content-Type": HEADER_CONTENT_TYPE,
            "Origin": "file://",
            "id_brand": self.brand_id,
            "customer_code": self.customer_code,
        }

    async def register_app_id(self):
        """Register app id with Agua IOT"""

        url = self.api_url + API_PATH_APP_SIGNUP

        payload = {
            "phone_type": "Android",
            "phone_id": self.unique_id,
            "phone_version": "1.0",
            "language": "en",
            "id_app": self.unique_id,
            "push_notification_token": self.unique_id,
            "push_notification_active": False,
        }
        payload = json.dumps(payload)

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    data=payload,
                    headers=self._headers(),
                    follow_redirects=False,
                    timeout=DEFAULT_TIMEOUT_VALUE,
                )
        except httpx.TransportError:
            raise ConnectionError(str.format("Connection to {0} not possible", url))

        if response.status_code != 201:
            _LOGGER.error(
                "Failed to register app id. Code: %s, Response: %s",
                response.status_code,
                response.text,
            )
            raise UnauthorizedError("Failed to register app id")

        return True

    async def login(self):
        """Authenticate with email and password to Agua IOT"""

        url = self.api_url + API_PATH_LOGIN

        payload = {"email": self.email, "password": self.password}
        payload = json.dumps(payload)

        extra_headers = {"local": "true", "Authorization": self.unique_id}

        headers = self._headers()
        headers.update(extra_headers)

        if self.login_api_url is not None:
            extra_login_headers = {
                "applicationversion": self.api_login_application_version,
                "url": API_PATH_LOGIN.lstrip("/"),
            }
            headers.update(extra_login_headers)
            url = self.login_api_url

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    data=payload,
                    headers=headers,
                    follow_redirects=False,
                    timeout=DEFAULT_TIMEOUT_VALUE,
                )
        except httpx.TransportError:
            raise ConnectionError(str.format("Connection to {0} not possible", url))

        if response.status_code != 200:
            _LOGGER.error(
                "Failed to login. Code: %s, Response: %s",
                response.status_code,
                response.text,
            )
            raise UnauthorizedError("Failed to login, please check credentials")

        res = response.json()
        self.token = res["token"]
        self.refresh_token = res["refresh_token"]

        claimset = jwt.decode(
            res["token"], options={"verify_signature": False}, algorithms=["none"]
        )
        self.token_expires = claimset.get("exp")

        return True

    async def do_refresh_token(self):
        """Refresh auth token for Agua IOT"""

        url = self.api_url + API_PATH_REFRESH_TOKEN

        payload = {"refresh_token": self.refresh_token}
        payload = json.dumps(payload)

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    data=payload,
                    headers=self._headers(),
                    follow_redirects=False,
                    timeout=DEFAULT_TIMEOUT_VALUE,
                )
        except httpx.TransportError:
            raise ConnectionError(str.format("Connection to {0} not possible", url))

        if response.status_code != 201:
            _LOGGER.warning("Refresh auth token failed, forcing new login...")
            self.login()
            return

        res = response.json()
        self.token = res["token"]

        claimset = jwt.decode(
            res["token"], options={"verify_signature": False}, algorithms=["none"]
        )
        self.token_expires = claimset.get("exp")

        return True

    async def fetch_devices(self):
        """Fetch heating devices"""
        url = self.api_url + API_PATH_DEVICE_LIST

        payload = {}
        payload = json.dumps(payload)

        res = await self.handle_webcall("POST", url, payload)
        if res is False:
            raise AguaIOTError("Error while fetching devices")

        for dev in res["device"]:
            url = self.api_url + API_PATH_DEVICE_INFO

            payload = {"id_device": dev["id_device"], "id_product": dev["id_product"]}
            payload = json.dumps(payload)

            res2 = await self.handle_webcall("POST", url, payload)
            if res2 is False:
                raise AguaIOTError("Error while fetching device info")

            self.devices.append(
                Device(
                    dev["id"],
                    dev["id_device"],
                    dev["id_product"],
                    dev["product_serial"],
                    dev["name"],
                    dev["is_online"],
                    dev["name_product"],
                    res2["device_info"][0]["id_registers_map"],
                    self,
                )
            )

    async def fetch_device_information(self):
        """Fetch device information of heating devices"""
        for dev in self.devices:
            await dev.update_mapping()
            await dev.update()

    async def update(self):
        for dev in self.devices:
            await dev.update()

    async def handle_webcall(self, method, url, payload):
        if time.time() > self.token_expires:
            self.do_refresh_token()

        extra_headers = {"local": "false", "Authorization": self.token}

        headers = self._headers()
        headers.update(extra_headers)

        try:
            if method == "POST":
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        url,
                        data=payload,
                        headers=headers,
                        follow_redirects=False,
                        timeout=DEFAULT_TIMEOUT_VALUE,
                    )
            else:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        url,
                        params=payload,
                        headers=headers,
                        follow_redirects=False,
                        timeout=DEFAULT_TIMEOUT_VALUE,
                    )
        except httpx.TransportError:
            raise ConnectionError(str.format("Connection to {0} not possible", url))

        if response.status_code == 401:
            await self.do_refresh_token()
            return await self.handle_webcall(method, url, payload)
        elif response.status_code != 200:
            _LOGGER.error(
                "Webcall failed. Code: %s, Response: %s",
                response.status_code,
                response.text,
            )
            return False

        return response.json()


class Device(object):
    """Agua IOT heating device representation"""

    def __init__(
        self,
        id,
        id_device,
        id_product,
        product_serial,
        name,
        is_online,
        name_product,
        id_registers_map,
        aguaiot,
    ):
        self.id = id
        self.id_device = id_device
        self.id_product = id_product
        self.product_serial = product_serial
        self.name = name
        self.is_online = is_online
        self.name_product = name_product
        self.id_registers_map = id_registers_map
        self.__aguaiot = aguaiot
        self.__register_map_dict = dict()
        self.__information_dict = dict()

    async def update_mapping(self):
        await self.__update_device_registers_mapping()

    async def update(self):
        await self.__update_device_information()

    async def __update_device_registers_mapping(self):
        url = self.__aguaiot.api_url + API_PATH_DEVICE_REGISTERS_MAP
        registers = dict()

        payload = {
            "id_device": self.id_device,
            "id_product": self.id_product,
            "last_update": "2018-06-03T08:59:54.043",
        }
        payload = json.dumps(payload)

        res = await self.__aguaiot.handle_webcall("POST", url, payload)
        if res is False:
            raise AguaIOTError("Error while fetching registers map")

        for registers_map in res["device_registers_map"]["registers_map"]:
            if registers_map["id"] == self.id_registers_map:
                registers = {
                    reg["reg_key"].lower(): reg for reg in registers_map["registers"]
                }

        self.__register_map_dict = registers

    async def __update_device_information(self):
        url = self.__aguaiot.api_url + API_PATH_DEVICE_BUFFER_READING

        payload = {
            "id_device": self.id_device,
            "id_product": self.id_product,
            "BufferId": 1,
        }
        payload = json.dumps(payload)

        res = await self.__aguaiot.handle_webcall("POST", url, payload)
        if res is False:
            raise AguaIOTError("Error while fetching device information")

        id_request = res["idRequest"]
        url = self.__aguaiot.api_url + API_PATH_DEVICE_JOB_STATUS + id_request

        payload = {}
        payload = json.dumps(payload)

        retry_count = 0
        res = await self.__aguaiot.handle_webcall("GET", url, payload)
        while (
            res is False or res["jobAnswerStatus"] != "completed"
        ) and retry_count < 10:
            await asyncio.sleep(1)
            res = await self.__aguaiot.handle_webcall("GET", url, payload)
            retry_count = retry_count + 1

        if res is False or res["jobAnswerStatus"] != "completed":
            raise AguaIOTError("Error while fetching device information")

        current_i = 0
        information_dict = dict()
        try:
            for item in res["jobAnswerData"]["Items"]:
                information_dict.update(
                    {item: res["jobAnswerData"]["Values"][current_i]}
                )
                current_i = current_i + 1
        except KeyError:
            raise AguaIOTError("Error while fetching device information")

        self.__information_dict = information_dict

    def __prepare_value_for_writing(self, item, value):
        value = int(value)
        set_min = self.__register_map_dict[item]["set_min"]
        set_max = self.__register_map_dict[item]["set_max"]

        if value < set_min or value > set_max:
            raise ValueError(
                "Value must be between {0} and {1}".format(set_min, set_max)
            )

        formula = self.__register_map_dict[item]["formula_inverse"]
        formula = formula.replace("#", str(value))
        eval_formula = parser(formula)
        return int(eval_formula)

    async def __request_writing(self, item, values):
        url = self.__aguaiot.api_url + API_PATH_DEVICE_WRITING

        items = [int(self.__register_map_dict[item]["offset"])]
        masks = [int(self.__register_map_dict[item]["mask"])]

        payload = {
            "id_device": self.id_device,
            "id_product": self.id_product,
            "Protocol": "RWMSmaster",
            "BitData": [8],
            "Endianess": ["L"],
            "Items": items,
            "Masks": masks,
            "Values": values,
        }
        payload = json.dumps(payload)

        res = await self.__aguaiot.handle_webcall("POST", url, payload)
        if res is False:
            raise AguaIOTError("Error while request device writing")

        id_request = res["idRequest"]

        url = self.__aguaiot.api_url + API_PATH_DEVICE_JOB_STATUS + id_request

        payload = {}
        payload = json.dumps(payload)

        retry_count = 0
        res = await self.__aguaiot.handle_webcall("GET", url, payload)
        while (
            res is False or res["jobAnswerStatus"] != "completed"
        ) and retry_count < 10:
            await asyncio.sleep(1)
            res = await self.__aguaiot.handle_webcall("GET", url, payload)
            retry_count = retry_count + 1

        if (
            res is False
            or res["jobAnswerStatus"] != "completed"
            or "Cmd" not in res["jobAnswerData"]
        ):
            raise AguaIOTError("Error while request device writing")

    @property
    def registers(self):
        return list(self.__register_map_dict.keys())

    def get_register(self, key):
        try:
            register = self.__register_map_dict[key]
            register["value_raw"] = str(
                self.__information_dict[register["offset"]] & register["mask"]
            )
            formula = register["formula"].replace("#", register["value_raw"])
            register["value"] = parser(formula)

            return register
        except (KeyError, ValueError):
            return {}

    def get_register_value(self, key):
        return self.get_register(key).get("value")

    def get_register_value_min(self, key):
        return self.get_register(key).get("set_min")

    def get_register_value_max(self, key):
        return self.get_register(key).get("set_max")

    def get_register_value_formatted(self, key):
        return str.format(
            self.get_register(key).get("format_string"),
            self.get_register(key).get("value"),
        )

    def get_register_value_description(self, key):
        options = self.get_register_value_options(key)
        if options:
            return options.get(
                self.get_register_value(key), self.get_register_value(key)
            )
        else:
            return self.get_register_value(key)

    def get_register_value_options(self, key):
        if "enc_val" in self.get_register(key):
            return {
                item["value"]: item["description"]
                for item in self.get_register(key).get("enc_val")
                if item["lang"] == "ENG"
            }
        return {}

    def get_register_enabled(self, key):
        enable_key = key.rsplit("_", 1)[0] + "_enable"
        if enable_key not in self.registers:
            # Always enabled if no enable register present
            return True

        if self.get_register(enable_key).get("reg_type") != "ENABLE":
            raise AguaIOTError(f"Not a register of type ENABLE: {key}")

        if "enable_val" in self.get_register(enable_key):
            enabled_values = [
                d["value"] for d in self.get_register(enable_key).get("enable_val")
            ]
            return self.get_register_value(enable_key) in enabled_values
        else:
            return self.get_register_value(enable_key) == 1

    async def set_register_value(self, key, value):
        values = [self.__prepare_value_for_writing(key, value)]
        try:
            await self.__request_writing(key, values)
        except AguaIOTError:
            raise AguaIOTError(f"Error while trying to set: {item}")

    async def set_register_value_description(self, key, value_description):
        try:
            options = self.get_register_value_options(key)
            value = list(options.keys())[
                list(options.values()).index(value_description)
            ]
        except (AttributeError, ValueError):
            value = value_description

        await self.set_register_value(key, value)


class AguaIOTError(Exception):
    """Exception type for Agua IOT"""

    def __init__(self, message):
        Exception.__init__(self, message)


class UnauthorizedError(AguaIOTError):
    """Unauthorized"""

    def __init__(self, message):
        super().__init__(message)


class ConnectionError(AguaIOTError):
    """Connection error"""

    def __init__(self, message):
        super().__init__(message)
