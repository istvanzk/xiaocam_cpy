# -*- coding: utf-8 -*-
# Test the CircuitPython DropboxAPI implementation
#
# MIT License (MIT), see LICENSE - Copyright (c) 2025 Istvan Z. Kovacs
#
import os
import board
from adafruit_connection_manager import get_radio_socketpool, get_radio_ssl_context
from adafruit_requests import Session
import wifi
import sdcardio
import storage
from local_time import LocalTimeAPI


# SD Card Init
# https://docs.circuitpython.org/en/latest/shared-bindings/sdcardio/index.html
sd = sdcardio.SDCard(board.SPI(), board.SDCS)
vfs = storage.VfsFat(sd)
storage.mount(vfs, '/sd')


# Initialize WiFi, when setup in settings.toml
ssid = os.getenv("CIRCUITPY_WIFI_SSID")
password = os.getenv("CIRCUITPY_WIFI_PASSWORD")
if ssid is not None and password is not None:
    rssi = wifi.radio.ap_info.rssi
    print(f"\nConnecting to {ssid}...")
    print(f"Signal Strength: {rssi}")
    wifi_available = True
    print(f"WiFi connection...", end="")
    try:
        # Connect to the Wi-Fi network
        wifi.radio.connect(ssid, password)
        ip = wifi.radio.ipv4_address
        print(f" ✅ Pass.\n  IP: {ip}")
    except OSError as e:
        wifi_available = False
        print(f" ❌ Failed.\n  Error: {e}")
else:
    print(f"❌ Wifi credentials not found in settings.toml. No WiFi connection.")

requests_session = None
# Nothing to do without WiFi connection
if not wifi_available:
    print("😞 Bye!")
    exit(1)

# Initalize Socket Pool, Request Session
# See https://github.com/adafruit/Adafruit_CircuitPython_ConnectionManager/blob/42073559468d0c8af9bb1fe5e06fccd4d1d9a845/adafruit_connection_manager.py#L130
pool = get_radio_socketpool(wifi.radio)
ssl_context = get_radio_ssl_context(wifi.radio)
requests_other = Session(pool, ssl_context)
requests_dropbox = Session(pool, ssl_context, session_id="dbx")

# print("-" * 40)
# print("Nothing yet opened")
# connection_manager = get_connection_manager(pool)
# print(f"Managed Sockets: {connection_manager.managed_socket_count}")
# print(f"Available Managed Sockets: {connection_manager.available_socket_count}")

print("-" * 80)
print("Init Time API instance and set RTC time...", end="")
time_api = LocalTimeAPI(requests_other)
time_api.set_datetime()
print(f" ✅ Pass.\n  {time_api.get_datetime()}")
print("-" * 80)

# print("-" * 40)
# print("1st request opened & closed")
# print(f"Managed Sockets: {connection_manager.managed_socket_count}")
# print(f"Available Managed Sockets: {connection_manager.available_socket_count}")

print("-" * 80)
print("Test Dropbox API: Start.")
try:
    # Load tokens from the environment variables stored in settings.toml
    # These correspond to info in tokens["oauth_result"] as returned from the Dropbox OAuth2 flow
    dbx_app_key       = os.getenv("DBX_APP_KEY")       # = tokens["oauth_result"].app_key
    dbx_app_secret    = os.getenv("DBX_APP_SECRET")    # = tokens["oauth_result"].app_secret
    dbx_access_token  = os.getenv("DBX_ACCESS_TOKEN")  # = tokens["oauth_result"].access_token
    dbx_refresh_token = os.getenv("DBX_REFRESH_TOKEN") # = tokens["oauth_result"].refresh_token
    dbx_access_token_expiration = int(os.getenv("DBX_EXPIRES_AT")) # = tokens["oauth_result"].expires_at converted to seconds
    #print(dbx_access_token_expiration)

    # Init client
    print("  Init client...", end="") 
    from dropbox_cpy import DropboxAPI
    dbx = DropboxAPI(
        oauth2_access_token=dbx_access_token,
        user_agent='XiaoCPY1/0.0.1',
        oauth2_access_token_expiration=dbx_access_token_expiration, #seconds, not datetime.datetime!
        oauth2_refresh_token=dbx_refresh_token,
        session=requests_dropbox,
        timeout=6,
        app_key=dbx_app_key,
        app_secret=dbx_app_secret
    )
    print(" ✅ Pass.")

    # print("-" * 40)
    # print("2nd request opened & closed")
    # print(f"Managed Sockets: {connection_manager.managed_socket_count}")
    # print(f"Available Managed Sockets: {connection_manager.available_socket_count}")
    # print("-" * 40)
    # print("Closing everything in the pool")
    # cm.connection_manager_close_all(pool)
    # print(f"Managed Sockets: {connection_manager.managed_socket_count}")
    # print(f"Available Managed Sockets: {connection_manager.available_socket_count}")
    # time.sleep(1)

    print("-" * 40)
    print("  Get user account info...", end="") 
    info = dbx.users_get_current_account()
    # info._all_field_names_ =
    # {'account_id', 'is_paired', 'locale', 'email', 'name', 'team', 'country', 'account_type', 'referral_link'}
    print(f" ✅ Pass.\n    Account:\n    {info}")

    # print("-" * 40)
    # print("  Create folder...", end="") 
    # create_folder = dbx.files_create_folder("/120425")
    # print(f" ✅ Pass.\n    Create folder result:\n    {create_folder}")

    # print("-" * 40)
    # print("  Upload image from SD card...", end="") 
    # with open("/sd/image.jpg", "rb") as f:
    #     res = dbx.files_upload(f, "/120425/image.jpg")
    #     print(f" ✅ Pass.\n    Upload file result:\n    {res}")

    # print("-" * 40)
    # print("  List folder content...", end="") 
    # files_list_folder = dbx.files_list_folder("/120425")
    # print(f"  ✅ Pass.\n    List folder result:\n    {files_list_folder}")

    print("Test Dropbox API: ✅ Pass.")

except Exception as e:
    print(f"❌ Failed.\n  Error: {e}")
    raise
finally:
    print("-" * 80)
