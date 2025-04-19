# -*- coding: utf-8 -*-
# Test the LocalTimeAPI implementation
import os
import wifi
from adafruit_connection_manager import get_radio_socketpool, get_radio_ssl_context
from adafruit_requests_fix import Session
import time
from local_time import LocalTimeAPI

def url_encode(url):
    """ A simple function to perform minimal URL encoding """
    return url.replace(" ", "+").replace("%", "%25").replace(":", "%3A").replace("/", "%2F")


# Initialize WiFi, when setup in settings.toml
ssid = os.getenv("CIRCUITPY_WIFI_SSID")
password = os.getenv("CIRCUITPY_WIFI_PASSWORD")
if ssid is not None and password is not None:
    rssi = wifi.radio.ap_info.rssi
    ip = wifi.radio.ipv4_address
    print(f"Signal Strength: {rssi}")
    print(f"IP Address: {ip}")
    print(f"\nConnecting to {ssid}...")
    wifi_available = True
    try:
        # Connect to the Wi-Fi network
        wifi.radio.connect(ssid, password)
    except OSError as e:
        wifi_available = False
        print(f"❌ OSError: {e}")
    print("✅ WiFi connected")
else:
    print(f"❌ WiFi credentials not found in settings.toml. No WiFi connection.")

# Initalize Socket Pool, Request Session
requests_session = None
if wifi_available:
    pool = get_radio_socketpool(wifi.radio)
    ssl_context = get_radio_ssl_context(wifi.radio)
    requests_session = Session(pool, ssl_context)

# Test only if wifi and requests session are available
if wifi_available and requests_session is not None:
    
    # Local Time API instance
    time_api = LocalTimeAPI(requests_session)

    # Get the current time
    # time_api.get_timeserver_time()
    # print(f"Current time: {time_api.servertime}")

    # Set the RTC time
    if time_api.set_datetime():
        print(f"Current server time: {time_api.servertime}")

        # Simple loop for testing
        while True:
            print(f"Current RTC time: {time_api.get_datetime()}")
            print(f"mktime: {time.mktime(time_api.get_datetime())}")
            print(f"localtime: {time.localtime()}")
            print(f"monotonic: {time.monotonic()}")
            print(f"sleeping ...")
            time.sleep(15)
    else:
        print("❌ Failed to set RTC time")

else:
    print("😞 Bye!")