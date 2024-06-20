"""REST API web scraper for Eaton UPS measure data."""
import json

from requests import Session, Response
from requests.exceptions import (
        ConnectionError,
        InvalidURL,
        MissingSchema,
        ReadTimeout,
        SSLError,
        )
# pyre-ignore[21]: pyre thinks urllib3 is not part of requests
from requests.packages import urllib3
from prometheus_eaton_ups_exporter import create_logger
from prometheus_eaton_ups_exporter.scraper_globals import (
        AUTHENTICATION_FAILED,
        CERTIFICATE_VERIFY_FAILED,
        CONNECTION_ERROR,
        INPUT_MEMBER_ID,
        INVALID_URL_ERROR,
        LOGIN_DATA,
        LoginFailedException,
        MISSING_SCHEMA_ERROR,
        OUTPUT_MEMBER_ID,
        REQUEST_TIMEOUT,
        REST_AUTH_PATH,
        REST_MANAGER_PATH,
        REST_POWER_PATH,
        REST_TEMPERATURES_PATH,
        SSL_ERROR,
        TIMEOUT_ERROR,
        )
from typing import Tuple


class UPSScraper:
    """
    Create a UPS Scraper based on the Eaton UPS's API.

    :param ups_address: str
        Address to a UPS, either an IP address or a DNS hostname
    :param authentication: (username: str, password: str)
        Username and password for the web UI of the UPS
    :param name: str
        Name of the UPS.
        Used as identifier to differentiate between multiple UPSs.
    :param insecure: bool
        Whether to connect to UPSs with self-signed SSL certificates
    :param verbose: bool
        Allow logging output for development
    :param login_timeout: float
        Login timeout for authentication
    """
    def __init__(self,
                 ups_address: str,
                 authentication: Tuple[str, str],
                 name: str | None = None,
                 insecure: bool = False,
                 verbose: bool = False,
                 login_timeout: int = 3) -> None:
        self.ups_address = ups_address
        self.username, self.password = authentication
        self.name = name
        self.login_timeout = login_timeout
        self.session = Session()
        self.logger = create_logger(__name__, not verbose)

        # ignore self signed certificate
        self.session.verify = not insecure
        # disable warnings created because of ignoring certificates
        if not self.session.verify:
            # pyre-ignore[16]: pyre thinks urllib3 is not part of requests
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        self.token_type, self.access_token = None, None

    def login(self) -> Tuple[str, str]:
        """
        Login to the UPS Web UI.

        Based on analysing the UPS Web UI, this will create a POST request
        with the authentication details to successfully create a session
        on the specified UPS.

        :return: two for the authentication necessary string values
        """
        try:
            data = LOGIN_DATA
            data["username"] = self.username
            data["password"] = self.password

            login_request = self.session.post(
                self.ups_address + REST_AUTH_PATH,
                data=json.dumps(data),  # needs to be JSON encoded
                timeout=self.login_timeout
            )
            login_response = login_request.json()

            token_type = login_response['token_type']
            access_token = login_response['access_token']

            self.logger.debug(
                "Authentication successful on (%s) with %s %s",
                self.ups_address, token_type, access_token
            )

            return token_type, access_token
        except KeyError:
            raise LoginFailedException(
                AUTHENTICATION_FAILED,
                "Authentication failed"
            ) from None
        except SSLError as err:
            if 'CERTIFICATE_VERIFY_FAILED' in str(err):
                # print("Try -k to allow insecure server "
                #       "connections when using SSL")
                raise LoginFailedException(
                    CERTIFICATE_VERIFY_FAILED,
                    "Invalid certificate, connection to host failed"
                ) from None
            raise LoginFailedException(
                SSL_ERROR,
                "Connection refused due to an SSL Error"
            ) from None
        except ConnectionError:
            raise LoginFailedException(
                CONNECTION_ERROR,
                "Connection refused, host might be out of reach."
            ) from None
        except ReadTimeout:
            raise LoginFailedException(
                TIMEOUT_ERROR,
                f"Login Timeout > {self.login_timeout} seconds"
            ) from None
        except MissingSchema:
            raise LoginFailedException(
                MISSING_SCHEMA_ERROR,
                "Invalid URL, no schema supplied"
            ) from None
        except InvalidURL:
            raise LoginFailedException(
                INVALID_URL_ERROR,
                "Invalid URL, no host supplied"
            ) from None

    def load_page(self,
                  url: bytes | str) -> Response:
        """
        Load a webpage of the UPS Web UI or API.

        This will try to load the page by the given URL.
        If authentication is needed first, the login function gets executed
        before loading the specified page.

        :param url: ups web url
        :return: request.Response
        """
        headers = {
            "Connection": "keep-alive",
            "Authorization": f"{self.token_type} {self.access_token}",
        }

        try:
            request = self.session.get(
                url,
                headers=headers,
                timeout=REQUEST_TIMEOUT
            )

            # Session might be expired, connect again
            try:
                print(str(request))
                if "errorCode" in request.json():
                    self.logger.debug('Session expired, reconnect')
                    self.token_type, self.access_token = self.login()
                    return self.load_page(url)
            except ValueError:
                pass

            # try to login, if not authorized
            if "Unauthorized" in request.text or request.status_code == 401:
                self.logger.debug('Unauthorized, try to login')
                try:
                    self.token_type, self.access_token = self.login()
                    return self.load_page(url)
                except LoginFailedException as err:
                    if err.error_code == TIMEOUT_ERROR:
                        raise LoginFailedException(
                            AUTHENTICATION_FAILED,
                            "Authentication failed"
                        ) from err
                    # else
                    raise err

            self.logger.debug('GET %s', url)
            return request
        except ConnectionError:
            self.logger.debug('Connection Error try to login again')
            try:
                self.token_type, self.access_token = self.login()
                return self.load_page(url)
            except LoginFailedException:
                raise
        except LoginFailedException:
            raise

    def get_system(self) -> dict:
        system = dict()
        try:
            manager_request = self.load_page(
                self.ups_address+REST_MANAGER_PATH
            )
            manager_overview = manager_request.json()

            system = manager_overview['identification']

        except LoginFailedException as err:
            self.logger.error(err)
            print(f"{err.__class__.__name__} - ({self.ups_address}): "
                  f"{err.message}")
        except json.decoder.JSONDecodeError as err:
            self.logger.debug("Failed to decode system response")
            self.logger.error(err)
        except Exception:
            raise

        return system


    def get_temperature(self) -> dict:
        temperature = dict()
        try:
            temperatures_request = self.load_page(
                self.ups_address+REST_TEMPERATURES_PATH
            )
            temperatures_overview = temperatures_request.json()

            temperature_path = temperatures_overview['members'][0]['@id']
            temperature_request = self.load_page(
                self.ups_address+temperature_path
            )
            temperature = temperature_request.json()

        except LoginFailedException as err:
            self.logger.error(err)
            print(f"{err.__class__.__name__} - ({self.ups_address}): "
                  f"{err.message}")
        except json.decoder.JSONDecodeError as err:
            self.logger.debug("Failed to decode temperature response")
            self.logger.error(err)
        except Exception:
            raise

        return temperature


    def get_measures(self) -> dict:
        """
        Get most relevant UPS metrics.

        :return: {
            "ups_id": self.name,
            "ups_inputs": inputs,
            "ups_outputs": outputs,
            "ups_powerbank": powerbank
            }
        """
        measurements = dict()
        try:
            power_dist_request = self.load_page(
                self.ups_address+REST_POWER_PATH
            )
            power_dist_overview = power_dist_request.json()

            if not self.name:
                self.name = f"ups_{power_dist_overview['id']}"

            ups_inputs_api = power_dist_overview['inputs']['@id']
            ups_ouptups_api = power_dist_overview['outputs']['@id']

            inputs_request = self.load_page(
                self.ups_address + ups_inputs_api + f'/{INPUT_MEMBER_ID}'
            )
            inputs = inputs_request.json()

            outputs_request = self.load_page(
                self.ups_address + ups_ouptups_api + f'/{OUTPUT_MEMBER_ID}'
            )
            outputs = outputs_request.json()

            ups_backup_sys_api = power_dist_overview['backupSystem']['@id']
            backup_request = self.load_page(
                self.ups_address + ups_backup_sys_api
            )
            backup = backup_request.json()
            ups_powerbank_api = backup['powerBank']['@id']
            powerbank_request = self.load_page(
                self.ups_address + ups_powerbank_api
            )
            powerbank = powerbank_request.json()

            measurements = {
                "ups_id": self.name,
                "ups_inputs": inputs,
                "ups_outputs": outputs,
                "ups_powerbank": powerbank
            }

        except LoginFailedException as err:
            self.logger.error(err)
            print(f"{err.__class__.__name__} - ({self.ups_address}): "
                  f"{err.message}")
        except json.decoder.JSONDecodeError as err:
            self.logger.debug("Failed to decode measure response")
            self.logger.error(err)
        except Exception:
            raise

        return measurements

    def get_data(self) -> dict:
        data = dict()
        data['system'] = self.get_system()
        data['temperature'] = self.get_temperature()
        data['measures'] = self.get_measures()
        return data