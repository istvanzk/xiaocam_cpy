# CircuitPython code for time-lapse with XIAO ESP32S3 Sense camera

![Exp](https://img.shields.io/badge/Dev-Experimental-orange.svg)
[![Lic](https://img.shields.io/badge/License-MIT-green)](https://mit-license.org)
![CircuitPy](https://img.shields.io/badge/CircuitPython-9.2.7-green)
![Ver](https://img.shields.io/badge/Version-0.1-blue)


## Implementation

The code was built for and tested with:
* [Seeed Studio XIAO ESP32S3 Sense](https://wiki.seeedstudio.com/xiao_esp32s3_getting_started/)
* [Adafruit CircuitPython 9.2.7](https://circuitpython.org/board/seeed_xiao_esp32s3_sense/). To install CircuitPython, follow the [Installing CircuitPython on ESP32](https://learn.adafruit.com/circuitpython-with-esp32-quick-start/installing-circuitpython) instructions.
* [mpy-cross-\*-9.2.7-32\*](https://adafruit-circuit-python.s3.amazonaws.com/index.html?prefix=bin/mpy-cross/)

### main

**TODO**


### [local_time](./local_time.py)

This is a simple API implemenation to get the local time from an internet time server and set the RTC time of the board. 

The primary time server used is the [Adafruit IO time server](https://io.adafruit.com/istvank/services/time).
The simplest are the `/time` requests, which can be used without authenticating.
To use the `/integration` requests you need an Adafruit IO account and IO key. The Adafruit IO username and key need to be inserted in the `settings.toml` file, as the values for ADAFRUIT_AIO_USERNAME and ADAFRUIT_AIO_KEY variables, respectively, [see below](#settingstoml-the-configuration-file-with-all-the-environment-variables-used).

Another time server which ca be used is the [TimeAPI](https://www.timeapi.io/), which does not require authentication either.

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

The [dropbox_cpy.py](./dropbox_cpy.py) can be [compiled to mpy format](https://learn.adafruit.com/welcome-to-circuitpython/frequently-asked-questions#faq-3105290) to save space.

### [adafruit_requests_fix](./adafruit_requests_fix.py)

The modified official Adafruit CircuitPython Requests library, Release 97, v4.1.10, March 2025.
The modification was needed to avoid `OSError: [Errno 116] ETIMEDOUT` from `socket.recv_into()`.
See [Issue #209](https://github.com/adafruit/Adafruit_CircuitPython_Requests/issues/209). 

**NOTE**: This is not an error specific to the XIAO boards, rather is due Dropbox API server behaviour. 
E.g. was tested on [XIAO ESP32C3](https://circuitpython.org/board/seeed_xiao_esp32c3/) in CircuitPython 9.2.7 resulted in the same problem and same solution.

*I recommend you start with the most up to date official Adafruit CircuitPython Requests library.
Only in case you encounter the `OSError: [Errno 116] ETIMEDOUT` error then try switching to this 'fixed' version.*
The `adafruit_requests` or `adafruit_requests_fix` is used in the following modules: `local_time`, `dropbox_cpy`, `wifitime_test` and `dbx_test`.

The [adafruit_requests_fix](./adafruit_requests_fix.py) can be [compiled to mpy format](https://learn.adafruit.com/welcome-to-circuitpython/frequently-asked-questions#faq-3105290) to save space.

<details>
<summary>Attempts to solve `OSError: [Errno 116] ETIMEDOUT`</summary> 

**Observations**: 
* The upload time for 50KB image file is very large, around 20 seconds! This is not normal, nor experienced when using the official Dropbox Python SDK V2. With [MQTT image upload to Adafruit IO](https://learn.adafruit.com/capturing-camera-images-with-circuitpython/example-webcam-with-adafruit-io) the large upload times are not observed either.
* The connection seems to be randomly dropped (by the server?) and the code hangs in the `socket.send()`, without throwing any errors.
* ...


**Attempt \#1**:
Insert `time.sleep(0.02)` in `adafruit_requests._send()`:
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
**Result #1: Solves the problem**. 

**Attempt \#2**:
Use the [socket options to enable keep-alive](https://github.com/psf/requests/issues/3353#issuecomment-722772458):
  ```
  socket.setsockopt(socket_pool.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
  socket.setsockopt(socket_pool.IPPROTO_TCP, socket.TCP_KEEPIDLE, 1)
  socket.setsockopt(socket_pool.IPPROTO_TCP, socket.TCP_KEEPINTVL, 3)
  socket.setsockopt(socket_pool.IPPROTO_TCP, socket.TCP_KEEPCNT, 5)
  ```

Most of the above constants are not defined in CircuitPython 9.2.7, but defined in the [underlying lwIP implementation](https://github.com/adafruit/Adafruit_CircuitPython_Requests/issues/209#issuecomment-2816247084)
in `circuitpython/ports/espressif/esp-idf/components/lwip/lwip/src/include/lwip/sockets.h`:
  ```
  /* Socket protocol types (TCP/UDP/RAW) */
  #define SOCK_STREAM     1
  #define SOCK_DGRAM      2
  #define SOCK_RAW        3

  #define  SOL_SOCKET  0xfff    /* options for socket level */

  # Socket protocols
  https://stackoverflow.com/questions/5385312/ipproto-ip-vs-ipproto-tcp-ipproto-udp
  #define IPPROTO_IP      0
  #define IPPROTO_ICMP    1
  #define IPPROTO_TCP     6
  #define IPPROTO_UDP     17
  #define IPPROTO_RAW     255

  #define SO_KEEPALIVE   0x0008 /* keep connections alive */

  /*
  * Options for level IPPROTO_IP
  */
  #define IP_TOS             1
  #define IP_TTL             2
  #define IP_PKTINFO         8

  /*
  * Options for level IPPROTO_TCP
  */
  #define TCP_NODELAY    0x01    /* don't delay send to coalesce packets */
  #define TCP_KEEPALIVE  0x02    /* send KEEPALIVE probes when idle for pcb->keep_idle milliseconds */
  #define TCP_KEEPIDLE   0x03    /* set pcb->keep_idle  - Same as TCP_KEEPALIVE, but use seconds for get/setsockopt */
  #define TCP_KEEPINTVL  0x04    /* set pcb->keep_intvl - Use seconds for get/setsockopt */
  #define TCP_KEEPCNT    0x05    /* set pcb->keep_cnt   - Use number of probes sent for get/setsockopt */
              
  ```
Insert the sequence below in `adafruit_requests.request()`, after the socket is created:

  ```
  socket.setsockopt(0xfff, 0x0008, 1)
  #socket.setsockopt(6, 0x2, 3) #KEEPALIVE
  socket.setsockopt(6, 0x3, 1) #KEEPIDLE
  socket.setsockopt(6, 0x4, 3) #KEEPINTVL
  socket.setsockopt(6, 0x5, 5) #KEEPCNT
  ```
**Result #2: Does not solve the problem!**

</details>

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

* [Adafruit CircuitPython 9.2.7+ for XIAO ESPP32S3 Sense](https://circuitpython.org/board/seeed_xiao_esp32s3_sense/)
  - To install follow the [Installing CircuitPython on ESP32](https://learn.adafruit.com/circuitpython-with-esp32-quick-start/installing-circuitpython) 
  - For command line [esptool](https://docs.espressif.com/projects/esptool/en/latest/esp32/index.html#quick-start), in boot mode (replace the port with yours):
    ```
    esptool.py --chip esp32s3 --port /dev/tty.usbmodem14401 erase_flash

    esptool.py --port /dev/tty.usbmodem14401 write_flash -z 0x0 adafruit-circuitpython-seeed_xiao_esp32_s3_sense-en_GB-9.2.7.bin
    ```
* Libraries (in /lib):
  - [adafruit_connection_manager](https://docs.circuitpython.org/projects/connectionmanager/en/latest/api.html)
  - [adafruit_requests](https://docs.circuitpython.org/projects/requests/en/latest/api.html) or the modified version [adafruit_requests_fix](#adafruit_requests_fix)


## Testing

There are a few test scripts included in the repo to test independent features: 
  * [cam_test.py](./cam_test.py) for camera and image file saving to SD card
  * [dbx_test.py](./dbx_test.py) for Dropbox access
  * [wifitime_test.py](./wifitime_test.py) for WiFi connectivity and Time Server access
