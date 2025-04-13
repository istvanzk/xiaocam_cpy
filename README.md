# CircuitPython code for time-lapse with XIAO ESP32S3 Sense camera

![Exp](https://img.shields.io/badge/Dev-Experimental-orange.svg)
[![Lic](https://img.shields.io/badge/License-MIT-green)](https://mit-license.org)
![CircuitPy](https://img.shields.io/badge/CircuitPython-9.2.6+-green)
![Ver](https://img.shields.io/badge/Version-0.1-blue)


## Implementation

This implementation has been developed and tested on [Seeed Studio XIAO ESP32S3 Sense](https://wiki.seeedstudio.com/xiao_esp32s3_getting_started/)
with [Adafruit CircuitPython](https://circuitpython.org/board/seeed_xiao_esp32s3_sense/). 
To install CircuitPython, follow the [Installing CircuitPython on ESP32](https://learn.adafruit.com/circuitpython-with-esp32-quick-start/installing-circuitpython) instructions.

### main

**TODO**


### [local_time](./local_time.py)

This is a simple API implemenation to get the local time from an internet time server and set the RTC time of the board. 

The primary time server used is the [Adafruit IO time server](https://learn.adafruit.com/shadow-box-internet-clock-with-neopixel-visualization/getting-the-date-time). 
To use this you need an Adafruit IO account and IO key. The Adafruit IO username and key need to be inserted in the `settings.toml` file, as the values for ADAFRUIT_AIO_USERNAME and ADAFRUIT_AIO_KEY variables, respectively, [see below](#settingstoml-the-configuration-file-with-all-the-environment-variables-used).

The secondary time server which ca be used is the [TimeAPI](https://www.timeapi.io/), which does not require any account or key for access.

### [dropbox_cpy](./dropbox_cpy.py)

This is a minimal CircuiPython implementation of the wire protocol for making requests to the Dropbox API V2 server.
It is based on the official Dropbox [API V2 SDK for Python](https://github.com/dropbox/dropbox-sdk-python/tree/main), Release 95, v12.0.2, June 2024.
Several of the original parameters and functionalities have been removed.
Error handling is simplified and only the most common errors are handled.
The code is not intended to be a full implementation of the Dropbox API.

In order to use the Dropbox API implemented here, you need to have a Dropbox account and set up an App in your [Dropbox App Console](https://www.dropbox.com/developers/reference/getting-started). 
Then follow the [OAuth flow](https://github.com/dropbox/dropbox-sdk-python/blob/main/example/oauth/commandline-oauth-scopes.py), which can be run on a development machine (not the XIAO board), to obtain the _access_token_ and _refresh_token_ tokens and the _expires_at_ value. 
These need to be inserted in the `settings.toml` file, as the values for the corresponding DBX_* variables.
Don't forget to set also all the other DBX_* variables, [see below](#settingstoml-the-configuration-file-with-all-the-environment-variables-used).

### [adafruit_requests_fix](./adafruit_requests_fix.py)

The modified official Adafruit CircuitPython Requests library, Release 97, v4.1.10, March 2025.

**NOTE**: This may be an error specific to the XIAO boards and/or due to certain Dropbox API server behaviour. Test on [XIAO ESP32C3](https://circuitpython.org/board/seeed_xiao_esp32c3/) in CircuitPython 9.2.7 resulted in the same problem and same solution.
To be further tested with other boards.

A modification was needed to avoid `OSError: [Errno 116] ETIMEDOUT` from `socket.recv_into()`.
See [Issue #209](https://github.com/adafruit/Adafruit_CircuitPython_Requests/issues/209). 
```
class Session:
...
  @staticmethod
  def _send(socket: SocketType, data: bytes):
  total_sent = 0
  while total_sent < len(data):
    try:
        sleep(0.02) # Added to avoid `OSError: [Errno 116] ETIMEDOUT` from socket.recv_into()
        sent = socket.send(data[total_sent:])
... 
```

*I recommend you start with the most up to date official Adafruit CircuitPython Requests library.
Only in case you encounter the `OSError: [Errno 116] ETIMEDOUT` error then try switching to this 'fixed' version.*
The `adafruit_requests` or `adafruit_requests_fix` is used in the following modules: `local_time`, `dropbox_cpy`, `wifitime_test` and `dbx_test`.


### [settings.toml](./settings.toml)

The configuration file with all the environment variables used.
Must include the following [environment variables](https://docs.circuitpython.org/en/latest/docs/environment.html) (see explanations above):
```
# WiFi
CIRCUITPY_WIFI_SSID = "<WiFi SSID>"
CIRCUITPY_WIFI_PASSWORD = "<WiFi password>"

# Time server
ADAFRUIT_AIO_USERNAME = "<Adafruit IO user name>"
ADAFRUIT_AIO_KEY = "<Adafruit IO key/token>"
TIMEZONE = "<Time zone>" # Timezone names from http://worldtimeapi.org/timezones, e.g. Europe/Amsterdam

# Dropbox
DBX_APP_KEY = "<App key>"
DBX_APP_SECRET = "<App secret>"
DBX_REFRESH_TOKEN = "<tokens["oauth_result"].refresh_token>"
DBX_ACCESS_TOKEN = "<tokens["oauth_result"].access_token>"
DBX_EXPIRES_AT = <tokens["oauth_result"].expires_at>
```

### camconfig

The configuration file with camera and time-lapse parameters.

**TODO**


### Dependencies

* [Adafruit CircuitPython for XIAO ESPP32S3 Sense](https://circuitpython.org/board/seeed_xiao_esp32s3_sense/)
* [adafruit_requests](https://docs.circuitpython.org/projects/requests/en/latest/api.html)
* [adafruit_connection_manager](https://docs.circuitpython.org/projects/connectionmanager/en/latest/api.html)


## Testing

There are a few test scripts included in the repo to test independent features: 
  * [cam_test.py](./cam_test.py) for camera and image file saving to SD card
  * [dbx_test.py](./dbx_test.py) for Dropbox access
  * [wifitime_test.py](./wifitime_test.py) for WiFi connectivity and Time Server access
