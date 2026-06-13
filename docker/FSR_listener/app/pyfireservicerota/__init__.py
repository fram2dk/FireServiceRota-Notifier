"""Python 3 API wrapper for FireServiceRota and BrandweerRooster."""
from collections import deque
import datetime
import json
import logging
import pytz
import threading
import time
import os
from typing import Optional
from paho.mqtt import client as mqtt_client

import oauthlib.oauth2
import requests
from requests.exceptions import HTTPError, RequestException, Timeout
import websocket

from .const import (
    FSR_DEFAULT_TIMEOUT,
    FSR_ENDPOINT_DUTY_STANDBY_FUNCTION,
    FSR_ENDPOINT_INCIDENT_RESPONSES,
    FSR_ENDPOINT_INCIDENTS,
    FSR_ENDPOINT_MEMBERSHIPS,
    FSR_ENDPOINT_SKILLS,
    FSR_ENDPOINT_TOKEN,
    FSR_ENDPOINT_USER,
)
from .errors import ExpiredTokenError, InvalidAuthError, InvalidTokenError


_LOGGER = logging.getLogger("pyfireservicerota")


class FireServiceRota(object):
    """Class for communicating with the fireservicerota API."""

    def __init__(
        self,
        base_url=None,
        username: str = None,
        password: str = None,
        token_info: dict = None,
    ):
        """Init module"""
        self._base_url = f"https://{base_url}"
        self._username = username
        self._password = password
        self._token_info = token_info
        self._user = None

    def request_tokens(self) -> bool:
        """Request API tokens."""

        oauth_client = oauthlib.oauth2.LegacyApplicationClient(client_id=None)
        request_body = oauth_client.prepare_request_body(
            username=self._username, password=self._password
        )
        response = self._request(
            "POST",
            endpoint=FSR_ENDPOINT_TOKEN,
            log_msg_action="request tokens",
            params=str.encode(request_body),
            auth_request=True,
        )

        try:
            self._token_info = response
            _LOGGER.debug(
                f"Obtained tokens: access {self._token_info['access_token']}, "
                f"refresh {self._token_info['refresh_token']}"
            )
            return self._token_info
        except (KeyError, TypeError) as err:
            _LOGGER.debug(f"Error obtaining tokens: {err}")
            return False

    def refresh_tokens(self) -> bool:
        """Refresh existing API tokens."""

        if not self._token_info:
            return

        oauth_client = oauthlib.oauth2.LegacyApplicationClient(client_id=None)
        request_body = oauth_client.prepare_refresh_body(
            refresh_token=self._token_info["refresh_token"]
        )
        response = self._request(
            "POST",
            endpoint=FSR_ENDPOINT_TOKEN,
            log_msg_action="refresh tokens",
            params=str.encode(request_body),
            auth_request=True,
        )

        try:
            self._token_info = response
            _LOGGER.debug("Refreshed access tokens.")
            return self._token_info
        except (KeyError, TypeError) as err:
            _LOGGER.debug(f"Error refreshing tokens: {err}")
            return False

    def get_user(self):
        """Get user data."""

        self._user = self._request(
            "GET",
            endpoint=FSR_ENDPOINT_USER,
            log_msg_action="get user",
            auth_request=False,
        )

        return self._user

    def get_schedules(self, tz,memid):
        """Get user schedules."""

        if not self._user:
            self.get_user()

        today = datetime.datetime.now(tz)
        tomorrow = today + datetime.timedelta(days=1)
        if memid is not None:
           id = memid
        else:
           id = self._user["memberships"][0]["id"]
        endpoint = FSR_ENDPOINT_MEMBERSHIPS.format(id)

        params = {
            "start_time": today.strftime("%Y-%m-%dT00:00:00%z"),
            "end_time": tomorrow.strftime("%Y-%m-%dT00:00:00%z"),
        }

        response = self._request(
            "GET",
            endpoint=endpoint,
            params=params,
            log_msg_action="get schedule memberships",
            auth_request=False,
        )

        return response

    def get_skills(self):
        """Get skills."""

        response = self._request(
            "GET",
            endpoint=FSR_ENDPOINT_SKILLS,
            log_msg_action="get skills",
            auth_request=False,
        )

        return response

    def get_standby_function(self, id):
        """Get standby function."""

        endpoint = FSR_ENDPOINT_DUTY_STANDBY_FUNCTION.format(id)

        response = self._request(
            "GET",
            endpoint=endpoint,
            log_msg_action="get standby function",
            auth_request=False,
        )

        return response

    def set_incident_response(self, id, status):
        """Set incident response for one incident."""

        endpoint = FSR_ENDPOINT_INCIDENT_RESPONSES.format(id)

        if status:
            params = {"status": "acknowledged"}
        else:
            params = {"status": "rejected"}

        self._request(
            "POST",
            endpoint=endpoint,
            log_msg_action="set incident response",
            params=params,
            auth_request=False,
        )

    def get_incident_response(self, id):
        """Get status of incident response for one incident."""

        if not self._user:
            self.get_user()

        endpoint = FSR_ENDPOINT_INCIDENTS.format(id)

        response = self._request(
            "GET",
            endpoint=endpoint,
            log_msg_action="get incident response",
            auth_request=False,
        )

        for r in response["incident_responses"]:
            if self._user["id"] == r["user_id"]:
                return r

        return None

    def get_availability(self, tzstring,memid=None):
        """Get user availablity."""
        tz = pytz.timezone(tzstring)
        response = self.get_schedules(tz,memid)

        if response:
            for interval in response["intervals"]:
                if interval["available"] == True:
                    now = datetime.datetime.now().astimezone()
                    if now > datetime.datetime.strptime(
                        interval["start_time"], "%Y-%m-%dT%H:%M:%S.%f%z"
                    ) and now < datetime.datetime.strptime(
                        interval["end_time"], "%Y-%m-%dT%H:%M:%S.%f%z"
                    ):
                        if "standby_duty" in interval["detailed_availability"]:
                            interval["type"] = "standby_duty"
                        elif "exception" in interval["detailed_availability"]:
                            interval["type"] = "exception"
                        elif "recurring" in interval["detailed_availability"]:
                            interval["type"] = "recurring"
                        else:
                            interval["type"] = "unknown"

                        if interval["assigned_function_ids"]:
                            for func in interval["assigned_function_ids"]:
                                interval[
                                    "assigned_function"
                                ] = self.get_standby_function(func)["name"]

                        return interval

        return {"available": False}

    def _request(
        self,
        method: str,
        endpoint: str,
        log_msg_action: str,
        params: dict = None,
        body: dict = None,
        auth_request: bool = False,
    ) -> Optional[str]:
        """Makes a request to the fireservicerota API."""
        url = f"{self._base_url}/{endpoint}"
        headers = dict()

        if not auth_request:
            url = f"{self._base_url}/api/v2/{endpoint}"
            headers = {
                "Content-Type": "application/json;charset=UTF-8",
                "Authorization": f"Bearer {self._token_info['access_token']}",
            }

        _LOGGER.debug(
            f"Making request to {endpoint} endpoint to {log_msg_action}: "
            f"url: {url}, headers: {headers}, params: {params}, body: {body}"
        )

        try:
            response = requests.request(
                method,
                url,
                headers=headers,
                params=params,
                json=body,
                timeout=FSR_DEFAULT_TIMEOUT,
            )

            try:
                log_msg = response.json()
            except:
                log_msg = response.text

            _LOGGER.debug(f"Request response: {response.status_code}: {log_msg}")

            response.raise_for_status()
            return response.json()
        except HTTPError:
            json_payload = {}
            try:
                json_payload = response.json()
            except json.decoder.JSONDecodeError:
                _LOGGER.debug("Invalid JSON payload received")

            if auth_request:
                if (
                    response.status_code == 401
                    and json_payload.get("error") == "invalid_grant"
                ):
                    raise InvalidAuthError(
                        "Invalid credentials or refresh token invalid"
                    )
                else:
                    _LOGGER.error(
                        f"Error requesting authorization: "
                        f"{response.status_code}: {json_payload}"
                    )
            elif response.status_code == 401:
                error = json_payload.get("error")
                if error == "token_invalid":
                    raise InvalidTokenError(
                        "Access token invalid; re-authentication required"
                    )
                elif error == "token_revoked":
                    raise ExpiredTokenError(
                        "Access token revoked; token refresh required"
                    )
                elif error == "token_expired":
                    raise ExpiredTokenError(
                        "Access token expired; token refresh required"
                    )
                else:
                    _LOGGER.error(
                        f"Error while attempting to {log_msg_action}: "
                        f"{error}: {json_payload.get('status', {}).get('message', 'Unknown error')}"
                    )
            else:
                _LOGGER.error(
                    f"Error while attempting to {log_msg_action}: "
                    f"{response.status_code}: {json_payload}"
                )
        except Timeout:
            _LOGGER.error(
                f"Connection timed out while attempting to {log_msg_action}. "
                f"Possible connectivity outage."
            )
        except (RequestException, json.decoder.JSONDecodeError):
            _LOGGER.error(
                f"Error connecting while attempting to {log_msg_action}. "
                f"{response.status_code}: {json_payload}"
            )

        return None


class FireServiceRotaIncidents:

    is_running = True
    mqttConnected = False

    def __init__(self,on_incident=None,on_message=None,on_statechange=None):
        """
        :param on_incident: function that get's called on received incident
        """
        self.on_incident = on_incident
        self.on_infomessage = on_message
        self.on_statechange = on_statechange
        self.ws = None
        self._backoff = 9

    def start(self, url):
        self._url = url
        self._recent_incidents = deque(maxlen=30)
        self.on_statechange({"trigger":"start","message":str("Websocket socket client starting")})

        _LOGGER.debug("Websocket client start")

        self.ws = websocket.WebSocketApp(
            self._url,
            on_open=self.__on_open,
            on_error=self.__on_error,
            on_message=self.__on_message,
            on_close=self.__on_close,
        )
        _LOGGER.debug("Websocket client start 1")
        self.wst = threading.Thread(target=lambda: self.ws.run_forever(ping_interval=15,ping_timeout=5,))
        self.wst.daemon = True
        _LOGGER.debug("Websocket client start 2")
        self.wst.start()
        _LOGGER.debug("Websocket client start 3")


    def stop(self):
        """
        close websocket
        """
        self.is_running = False
        self.ws.close()
        _LOGGER.debug("Websocket client stopped")

    def restart(self):
        _LOGGER.debug("Websocket forced restart")
        self.is_running = False
        self.ws.close()


        self.ws = websocket.WebSocketApp(
            self._url,
            on_open=self.__on_open,
            on_error=self.__on_error,
            on_message=self.__on_message,
            on_close=self.__on_close,
            on_pong=self.__on_pong,
        )
        self.on_statechange({"trigger":"restart","message":str("Websocket forced to restart now")})
        self.wst = threading.Thread(target=lambda: self.ws.run_forever(ping_interval=15,ping_timeout=5,))
        self.wst.daemon = True
        self.wst.start()
        self.is_running = True

    def __on_pong(self, ws, message):
        _LOGGER.debug("Pong recieved:"+str(message))
        self.on_statechange({"trigger":"pong","message":str("Pong recieved:"+str(message))})

    def __on_open(self, ws):
        _LOGGER.debug("Websocket open")
        self.on_statechange({"trigger":"open","message":str("Websocket opened")})

    def __on_close(self, ws, close_status_code, close_msg):
        """
        On Close Listener
        """
        self._backoff = getattr(self, "_backoff", 1)
        self._backoff = min(self._backoff, 300)  # max 300 sek
        time.sleep(self._backoff)

        _LOGGER.debug("Websocket closed code:"+str(close_status_code)+" reason:"+str(close_msg)+" - and will restart after close")
        if self.is_running:
            self.ws = websocket.WebSocketApp(
                self._url,
                on_open=self.__on_open,
                on_error=self.__on_error,
                on_message=self.__on_message,
                on_close=self.__on_close,
            )
            self.on_statechange({"trigger":"close","message":str("Websocket closed. because:"+str(close_msg)+" - will try restart now")})
            self.wst = threading.Thread(target=lambda: self.ws.run_forever(ping_interval=15,ping_timeout=5,))
            self.wst.daemon = True
            self.wst.start()

    def __on_message(self, ws, message):
        _LOGGER.debug("Websocket data:" + message)
        try:
            message = json.loads(message)
            if "identifier" in message:
                log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','logfiles')
                files = sorted([f for f in os.listdir(log_dir) if os.path.isfile(os.path.join(log_dir, f))]) # Hent og sorter filnavne alfabetisk
                logdays = 10
                if len(files) > logdays:
                  for f in files[9:]:
                    filepath = os.path.join(log_dir, f)
                    os.remove(filepath)

                today = str(datetime.datetime.now().astimezone().strftime("%Y%m%d"))
                now = str(datetime.datetime.now().astimezone().strftime("%Y%m%d %H%M%S.%f"))
                with open(os.path.join(log_dir,'data'+today+'.json'), 'a+') as outfile:
                    msgOut = {'timestamp':now,'content':message}
                    json.dump(msgOut, outfile)
                    outfile.write('\r\n')
            #mqtt stuff end
            if "type" not in message:
               incident = message["message"]
               """mark new and update messages"""
               incident_id = incident["id"]
               if incident_id not in self._recent_incidents:
                  self._recent_incidents.append(incident_id)
                  incident["trigger"] = "new"
                  _LOGGER.debug("New incident received")
               else:
                  incident["trigger"] = "update"
                  _LOGGER.debug("Incident update received")
                  self.on_incident(incident)
            elif message["type"] == "welcome":
                self.on_infomessage(message)
                _LOGGER.debug("Subscribing to the incidents channel")
                self.ws.send(
                    json.dumps(
                        {
                            "command": "subscribe",
                            "identifier": json.dumps(
                                {"channel": "IncidentNotificationsChannel"}
                            ),
                        }
                    )
                )
            elif message["type"] == "confirm_subscription":
                self.on_infomessage(message)
                _LOGGER.debug("Succesfully subscribed to incidents channel")
                self._backoff = 1
            elif message["type"] == "ping":
                self.on_infomessage(message)
            elif message["type"] == "disconnect":
              if message.get("reconnect") is False:
                self._backoff = 255
              self.ws.close() # server has closed - so we do to
              self.on_infomessage(message)
            else:
                self.on_infomessage(message)
                _LOGGER.debug(f"Received unknown type: {message}")
        except Exception as e:
            _LOGGER.exception(e)

    def __on_error(self, ws, error):
        """Handle websocket error with simple backoff and Retry-After."""
        _LOGGER.warning("Websocket error: %s", error)

        # Lazy create backoff
        if not hasattr(self, "_backoff"):
            self._backoff = 1
        max_backoff = 300  # 5 minutter

        # Detect 429 Too Many Requests
        msg = str(error)
        retry_after = None

        if "429" in msg:
            _LOGGER.warning("Received 429 Too Many Requests")

            # If websocket error object contains headers (depends on lib)
            if hasattr(error, "headers"):
                retry_after = error.headers.get("Retry-After")

            if retry_after:
                wait = int(retry_after)
                _LOGGER.warning(f"Respecting Retry-After: waiting {wait}s")
                time.sleep(wait+2)
                self._backoff = 1
                return

        # Normal error → exponential backoff
        warningmsg = f"Backing off {self._backoff}s before reconnect…"
        _LOGGER.warning(warningmsg)
        self.on_statechange({"trigger":"error","backofftime":self._backoff,"errormsg":msg,"message":str(warningmsg)})

        self._backoff = min(self._backoff * 2, max_backoff)
