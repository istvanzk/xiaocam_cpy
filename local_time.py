# -*- coding: utf-8 -*-
# Simple class to get the current local time from a time server
#
# MIT License (MIT), see LICENSE - Copyright (c) 2025 Istvn Z. Kovacs
#
import os
import sys
import time
from adafruit_requests import Session

if sys.implementation.name == "circuitpython":
    from rtc import RTC
else:
    from fakertc import RTC


def _url_encode(url):
    """ A simple function to perform minimal URL encoding """
    return url.replace(" ", "+").replace("%", "%25").replace(":", "%3A").replace("/", "%2F")

class LocalTimeAPI(object):
    """ 
    A simple class to get the current local time from a time server. 
    
    Uses information read from the settings.toml file to connect to the WiFi network and get the current time from a time server.
    The authentication for the Adafruit IO Time server for /integration requests is configured in the settings.toml file. 
    If no authentication for time server is configured, the class will use one of the default time servers:
    - The Adafruit IO Time server for /timer requests, OR
    - The timeapi.io server for /current/zone requests.
    The class will also set the RTC time using the current time from the time server.
    """

    # The timezone where the device is located
    # Timezone name from http://worldtimeapi.org/timezones
    timezone = os.getenv("TIMEZONE", "Europe/Amsterdam")

    # Adafruit IO Time server
    # https://io.adafruit.com/istvank/services/time
    TIME_URL_AIO = None
    TIME_URL = None
    aio_username = os.getenv("ADAFRUIT_AIO_USERNAME")
    aio_key = os.getenv("ADAFRUIT_AIO_KEY")
    if aio_username is not None and aio_key is not None:
        # https://jeffkayser.com/projects/date-format-string-composer/index.html
        #date_time_fmt = "%Y-%m-%dT%H:%M:%S.%L" # for "2025-03-27T18:32:36.747"
        date_time_fmt = "%Y-%m-%dT%H:%M:%S %w %j" # for "2025-03-27T18:32:36 4 086"
        TIME_URL_AIO = f"https://io.adafruit.com/api/v2/{aio_username}/integrations/time/strftime?x-aio-key={aio_key}&tz={timezone}"
        TIME_URL_AIO += f"&fmt={_url_encode(date_time_fmt)}"
    else:
        TIME_URL_AIO = f"https://io.adafruit.com/api/v2/time/seconds"
    
    # TIME_URL = f"https://www.timeapi.io/api/time/current/zone?timeZone={_url_encode(timezone)}"

    def __init__(self, requests_session: Session = None):
        # The requests session to use for making HTTP requests
        if requests_session is None:
            raise ValueError('No requests session provided!')
        self._session = requests_session

        # Date/time strings
        self.date_str, self.time_str = None, None
        self.wday_str, self.yday_str = None, None

        # The time as read from an internet time server
        self.servertime: time.struct_time = None

        # Initialize RTC (singleton)
        # https://docs.circuitpython.org/en/latest/shared-bindings/rtc/index.html
        # Any modifications here are visible across all instances in all modules
        self.rtc = RTC()

    def get_timeserver_time(self) -> time.struct_time:
        """ 
        Get the current time from the time server 

        Returns:
            time.struct_time: The current time read from a time server as a struct_time object 
        """
        if self._session is None:
            print("❌ No requests session available")
            return None
        
        if self.TIME_URL_AIO is not None:
            if "integrations" in self.TIME_URL_AIO:
                with self._session.get(
                    self.TIME_URL_AIO,
                    timeout=10,
                ) as response:
                    _timedata = response.text
                _date_time_str, self.wday_str, self.yday_str = _timedata.split(' ')
                self.date_str, self.time_str = _date_time_str.split('T')
            else:
                with self._session.get(
                    self.TIME_URL_AIO,
                    timeout=10,
                ) as response:
                    _timesec = response.text
                print(f"Seconds: {_timesec}")
                self.servertime = time.localtime(int(_timesec))

            #print(f"{time.monotonic()}, ✅ AIO server:: 📆 {self.date_str}, ⏱️ {self.time_str}")

        elif self.TIME_URL is not None:
            with self._session.get(
                self.TIME_URL,
                timeout=10,
            ) as response:
                _timedata = response.json()
            # {
            #   "year": 2025,
            #   "month": 3,
            #   "day": 27,
            #   "hour": 18,
            #   "minute": 32,
            #   "seconds": 36,
            #   "milliSeconds": 747,
            #   "dateTime": "2025-03-27T18:32:36.7473284",
            #   "date": "03/27/2025",
            #   "time": "18:32",
            #   "timeZone": "Europe/Amsterdam",
            #   "dayOfWeek": "Thursday",
            #   "dstActive": false
            # }
            self.date_str, _time_str = _timedata['dateTime'].split('T')
            self.time_str, _ = _time_str.split('.')
            self.wday_str = f"{['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'].index(_timedata['dayOfWeek'])}"
            self.yday_str = '-1'
            #print(f"{time.monotonic()}, ✅ TimeAPI server:: 📆 {self.date_str}, ⏱️ {self.time_str}")
        
        else:
            print("❌ No time server configured:: Current time data is not available.")
            self.servertime = None
            return None
        
        # Split the date and time strings into their components
        if self.servertime is None:
            if self.date_str is None or self.time_str is None:
                print("❌ Date and/or time could not be set from configured time server:: Current time data is not available.")
                self.servertime = None
                return None

            _ymd = self.date_str.split('-')
            _hms = self.time_str.split(':')
            self.servertime = time.struct_time((
                int(_ymd[0]),
                int(_ymd[1]),
                int(_ymd[2]),
                int(_hms[0]),
                int(_hms[1]),
                int(_hms[2]),
                int(self.wday_str),
                int(self.yday_str),
                -1
            ))

        return self.servertime

    def set_datetime(self) -> bool:
        """
        Set the RTC time using the current time from the time server.

        Returns:
            bool: True if the time was set successfully, False otherwise
        """
        self.get_timeserver_time()
        if self.servertime is None:
            print("❌ No time server data available to set RTC time")
            return False
        self.rtc.datetime = self.servertime
        return True
    
    def get_datetime(self) -> time.struct_time:
        """
        Get the current date and time from the RTC.

        Returns:
            time.struct_time: The current date and time as a struct_time object
        """
        return self.rtc.datetime