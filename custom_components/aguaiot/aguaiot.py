"""py_agua_iot provides controlling heating devices connected via
the IOT Agua platform of Micronova
"""

import asyncio
import jwt
import logging
import time
import httpx
from simpleeval import simple_eval

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

HEADER_ACCEPT = "application/json, text/javascript, */*; q=0.01"
HEADER_CONTENT_TYPE = "application/json"
HEADER = {"Accept": HEADER_ACCEPT, "Content-Type": HEADER_CONTENT_TYPE}


class aguaiot(object):
    def __init__(
        self,
        api_url,
        customer_code,
        email,
        password,
        unique_id,
        login_api_url=None,
        brand_id=None,
        brand=None,
        application_version="1.9.7",
        async_client=None,
        air_temp_fix=False,
        reading_error_fix=False,
        language="ENG",
        http_timeout=30,
        buffer_read_timeout=30,
    ):
        self.api_url = api_url.rstrip("/")
        self.customer_code = customer_code
        self.email = email
        self.password = password
        self.unique_id = unique_id
        self.brand_id = brand_id
        self.brand = brand
        self.login_api_url = login_api_url
        self.application_version = application_version
        self.token = None
        self.token_expires = None
        self.refresh_token = None
        self.devices = list()
        self.async_client = async_client
        self.http_timeout = http_timeout
        self.buffer_read_timeout = buffer_read_timeout

        # Vendor specific fixes
        self.air_temp_fix = air_temp_fix
        self.reading_error_fix = reading_error_fix
        self.language = language

        if not self.async_client:
            self.async_client = httpx.AsyncClient()

    async def connect(self):
        await self.register_app_id()
        await self.login()
        await self.fetch_devices()
        await self.fetch_device_information()

    def _headers(self):
        """Correctly set headers for requests to Agua IOT."""

        headers = {
            "Accept": HEADER_ACCEPT,
            "Content-Type": HEADER_CONTENT_TYPE,
            "Origin": "file://",
            "id_brand": self.brand_id if self.brand_id is not None else "1",
            "customer_code": self.customer_code,
        }
        if self.brand is not None:
            headers["brand"] = self.brand

        return headers

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

        try:
            _LOGGER.debug(
                "POST Register app - HEADERS: %s DATA: %s", self._headers(), payload
            )
            async with self.async_client as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers=self._headers(),
                    follow_redirects=False,
                    timeout=self.http_timeout,
                )
                _LOGGER.debug(
                    "RESPONSE Register app - CODE: %s DATA: %s",
                    response.status_code,
                    response.text,
                )
        except httpx.TransportError as e:
            raise AguaIOTConnectionError(f"Connection error to {url}: {e}")

        if response.status_code != 201:
            _LOGGER.error(
                "Failed to register app id. Code: %s, Response: %s",
                response.status_code,
                response.text,
            )
            raise AguaIOTUnauthorized("Failed to register app id")

        return True

    async def login(self):
        """Authenticate with email and password to Agua IOT"""

        url = self.api_url + API_PATH_LOGIN

        payload = {"email": self.email, "password": self.password}
        extra_headers = {"local": "true", "Authorization": self.unique_id}

        headers = self._headers()
        headers.update(extra_headers)

        if self.login_api_url is not None:
            extra_login_headers = {
                "applicationversion": self.application_version,
                "url": API_PATH_LOGIN.lstrip("/"),
                "userid": "null",
                "aguaid": "null",
            }
            headers.update(extra_login_headers)
            url = self.login_api_url

        try:
            _LOGGER.debug("POST Login - HEADERS: %s DATA: ***", headers)
            async with self.async_client as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers=headers,
                    follow_redirects=False,
                    timeout=self.http_timeout,
                )
                _LOGGER.debug(
                    "RESPONSE Login - CODE: %s DATA: %s",
                    response.status_code,
                    response.text,
                )
        except httpx.TransportError as e:
            raise AguaIOTConnectionError(f"Connection error to {url}: {e}")

        if response.status_code != 200:
            _LOGGER.error(
                "Failed to login. Code: %s, Response: %s",
                response.status_code,
                response.text,
            )
            raise AguaIOTUnauthorized("Failed to login, please check credentials")

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

        try:
            _LOGGER.debug(
                "POST Refresh token - HEADERS: %s DATA: %s", self._headers(), payload
            )
            async with self.async_client as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers=self._headers(),
                    follow_redirects=False,
                    timeout=self.http_timeout,
                )
                _LOGGER.debug(
                    "RESPONSE Refresh token - CODE: %s DATA: %s",
                    response.status_code,
                    response.text,
                )
        except httpx.TransportError as e:
            raise AguaIOTConnectionError(f"Connection error to {url}: {e}")

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

        res = await self.handle_webcall("POST", url, payload)
        if res is False:
            raise AguaIOTError("Error while fetching devices")

        for dev in res["device"]:
            url = self.api_url + API_PATH_DEVICE_INFO

            payload = {"id_device": dev["id_device"], "id_product": dev["id_product"]}
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

    async def update(self):
        for dev in self.devices:
            await dev.update()

    async def handle_webcall(self, method, url, payload):
        if time.time() > self.token_expires:
            await self.do_refresh_token()

        extra_headers = {"local": "false", "Authorization": self.token}

        headers = self._headers()
        headers.update(extra_headers)

        try:
            _LOGGER.debug("%s %s - HEADERS: %s DATA: %s", method, url, headers, payload)
            if method == "POST":
                async with self.async_client as client:
                    response = await client.post(
                        url,
                        json=payload,
                        headers=headers,
                        follow_redirects=False,
                        timeout=self.http_timeout,
                    )
            else:
                async with self.async_client as client:
                    response = await client.get(
                        url,
                        params=payload,
                        headers=headers,
                        follow_redirects=False,
                        timeout=self.http_timeout,
                    )
            _LOGGER.debug(
                "RESPONSE %s - CODE: %s DATA: %s",
                url,
                response.status_code,
                response.text,
            )
        except httpx.TransportError as e:
            raise AguaIOTConnectionError(f"Connection error to {url}: {e}")

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

        res_req = await self.__aguaiot.handle_webcall("POST", url, payload)
        if res_req is False:
            raise AguaIOTError("Error while making device buffer read request.")

        async def buffer_read_loop(id_request):
            url = self.__aguaiot.api_url + API_PATH_DEVICE_JOB_STATUS + id_request
            sleep_secs = 1
            attempts = 1

            try:
                while True:
                    await asyncio.sleep(sleep_secs)

                    _LOGGER.debug("BUFFER READ (%s) ATTEMPT %s", id_request, attempts)
                    res_get = await self.__aguaiot.handle_webcall("GET", url, {})
                    _LOGGER.debug(
                        "BUFFER READ (%s) STATUS: %s",
                        id_request,
                        res_get.get("jobAnswerStatus"),
                    )
                    if res_get.get("jobAnswerStatus", "") != "waiting":
                        return res_get

                    sleep_secs += 1
                    attempts += 1
            except asyncio.CancelledError:
                raise

        try:
            res = await asyncio.wait_for(
                buffer_read_loop(res_req["idRequest"]),
                self.__aguaiot.buffer_read_timeout,
            )
        except asyncio.TimeoutError:
            raise AguaIOTTimeout(
                f"Timeout on waiting device buffer read to complete within {self.__aguaiot.buffer_read_timeout} seconds."
            )

        if not res:
            raise AguaIOTError("Error while reading device buffer response.")
        elif res.get("jobAnswerStatus", "") == "terminated":
            raise AguaIOTError(
                "Error while reading device buffer response: Cloud terminated request."
            )

        current_i = 0
        information_dict = dict()
        try:
            for item in res["jobAnswerData"]["Items"]:
                information_dict.update(
                    {item: res["jobAnswerData"]["Values"][current_i]}
                )
                current_i = current_i + 1
        except KeyError:
            raise AguaIOTError("Error in data received from device.")

        self.__information_dict = information_dict

    def __prepare_value_for_writing(self, item, value, limit_value_raw=False):
        set_min = self.__register_map_dict[item]["set_min"]
        set_max = self.__register_map_dict[item]["set_max"]

        if not limit_value_raw and (float(value) < set_min or float(value) > set_max):
            raise ValueError(f"Value must be between {set_min} and {set_max}: {value}")

        formula = self.__register_map_dict[item]["formula_inverse"]
        formula = formula.replace("#", str(value))
        formula = formula.replace("Mod", "%")
        eval_formula = simple_eval(
            formula,
            functions={"IF": lambda a, b, c: b if a else c, "int": lambda a: int(a)},
        )
        value = int(eval_formula)

        if limit_value_raw and (float(value) < set_min or float(value) > set_max):
            raise ValueError(
                f"Raw value must be between {set_min} and {set_max}: {value}"
            )

        if self.__register_map_dict[item]["is_hex"]:
            value = int(f"0x{value}", 16)

        return value

    async def __request_writing(self, items):
        url = self.__aguaiot.api_url + API_PATH_DEVICE_WRITING

        set_items = []
        set_masks = []
        set_bits = []
        set_endians = []
        set_values = []

        for key in items:
            set_items.append(int(self.__register_map_dict[key]["offset"]))
            set_masks.append(int(self.__register_map_dict[key]["mask"]))
            set_values.append(items[key])
            set_bits.append(8)
            set_endians.append("L")

        payload = {
            "id_device": self.id_device,
            "id_product": self.id_product,
            "Protocol": "RWMSmaster",
            "BitData": set_bits,
            "Endianess": set_endians,
            "Items": set_items,
            "Masks": set_masks,
            "Values": set_values,
        }

        res = await self.__aguaiot.handle_webcall("POST", url, payload)
        if res is False:
            raise AguaIOTError("Error while request device writing")

        id_request = res["idRequest"]

        url = self.__aguaiot.api_url + API_PATH_DEVICE_JOB_STATUS + id_request

        payload = {}

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
            formula = formula.replace("Mod", "%")
            register["value"] = simple_eval(
                formula,
                functions={
                    "IF": lambda a, b, c: b if a else c,
                    "int": lambda a: int(a),
                },
            )

            return register
        except (KeyError, ValueError):
            return {}

    def get_register_value(self, key):
        value = self.get_register(key).get("value")

        # Fix for reading errors from wifi module
        if (
            self.__aguaiot.reading_error_fix
            and int(self.get_register(key).get("value_raw", 0)) == 32768
        ):
            _LOGGER.debug(
                f"Applied reading_error_fix. Dropped value {value} for register {key}"
            )
            return

        # Fix for stoves abusing air temp register
        if (
            self.__aguaiot.air_temp_fix
            and key.endswith("air_get")
            and value
            and int(value) > 100
        ):
            _LOGGER.debug(
                f"Applied air_temp_fix. Dropped value {value} for register {key}"
            )
            return

        return value

    def get_register_value_min(self, key):
        return self.get_register(key).get("set_min")

    def get_register_value_max(self, key):
        return self.get_register(key).get("set_max")

    def get_register_value_formatted(self, key):
        return str.format(
            self.get_register(key).get("format_string"),
            self.get_register(key).get("value"),
        )

    def get_register_value_description(self, key, language=None):
        options = self.get_register_value_options(key, language)
        if options:
            return options.get(
                self.get_register_value(key), self.get_register_value(key)
            )
        else:
            return self.get_register_value(key)

    def get_register_value_options(self, key, language=None):
        if "enc_val" in self.get_register(key):
            lang = language if language else self.__aguaiot.language
            if lang not in self.get_register_value_options_languages(key):
                lang = "ENG"

            return {
                item["value"]: item["description"]
                for item in self.get_register(key).get("enc_val")
                if item["lang"] == lang
            }
        return {}

    def get_register_value_options_languages(self, key):
        if "enc_val" in self.get_register(key):
            return {item["lang"] for item in self.get_register(key).get("enc_val")}
        return set()

    def get_register_enabled(self, key):
        enable_key = key.rsplit("_", 1)[0] + "_enable"
        if enable_key not in self.registers or not self.get_register(enable_key):
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

    async def set_register_value(self, key, value, limit_value_raw=False):
        if value is None:
            raise AguaIOTError(f"Error while trying to set '{key}' to None")

        value = self.__prepare_value_for_writing(
            key, value, limit_value_raw=limit_value_raw
        )
        items = {key: value}

        try:
            await self.__request_writing(items)
        except AguaIOTError:
            raise AguaIOTError(f"Error while trying to set: key={key} value={value}")

    async def set_register_values(self, items, limit_value_raw=False):
        for key in items:
            items[key] = self.__prepare_value_for_writing(
                key, items[key], limit_value_raw=limit_value_raw
            )

        try:
            await self.__request_writing(items)
        except AguaIOTError:
            raise AguaIOTError(f"Error while trying to set: items={items}")

    async def set_register_value_description(
        self, key, value_description, value_fallback=None, language=None
    ):
        try:
            options = self.get_register_value_options(key, language)
            value = list(options.keys())[
                list(options.values()).index(value_description)
            ]
        except (AttributeError, ValueError):
            value = value_description
        try:
            value = float(value)
        except ValueError:
            value = value_fallback

        await self.set_register_value(key, value)


class AguaIOTError(Exception):
    """Exception type for Agua IOT"""

    def __init__(self, message):
        Exception.__init__(self, message)


class AguaIOTUnauthorized(AguaIOTError):
    """Unauthorized"""

    def __init__(self, message):
        super().__init__(message)


class AguaIOTConnectionError(AguaIOTError):
    """Connection error"""

    def __init__(self, message):
        super().__init__(message)


class AguaIOTTimeout(AguaIOTError):
    """Connection error"""

    def __init__(self, message):
        super().__init__(message)
