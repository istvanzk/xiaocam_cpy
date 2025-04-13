# -*- coding: utf-8 -*-
# Test the CircuitPython DropboxAPI implementation
import os
import board
import adafruit_connection_manager as cm
import adafruit_requests_fix as requests
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
    try:
        # Connect to the Wi-Fi network
        wifi.radio.connect(ssid, password)
    except OSError as e:
        wifi_available = False
        print(f"❌ OSError: {e}")

    ip = wifi.radio.ipv4_address
    print(f"✅ WiFi connected: {ip}")
else:
    print(f"❌ Wifi credentials not found in settings.toml. No WiFi connection.")

session = None
# Nothing to do without WiFi connection
if not wifi_available:
    print("😞 Bye!")
    exit(1)

# Initalize Socket Pool, Request Session
# See https://github.com/adafruit/Adafruit_CircuitPython_ConnectionManager/blob/42073559468d0c8af9bb1fe5e06fccd4d1d9a845/adafruit_connection_manager.py#L130
pool = cm.get_radio_socketpool(wifi.radio)
ssl_context = cm.get_radio_ssl_context(wifi.radio)
session = requests.Session(pool, ssl_context)
## Alternative
## https://docs.circuitpython.org/en/latest/shared-bindings/ssl/index.html
# import socketpool
# import ssl
# ssl_context = ssl.create_default_context()
## curl -vvI --insecure https://api.dropboxapi.com
## curl -w %{certs} https://api.dropboxapi.com > cacert.pem
## 5 years OLD: dropbox/trusted-certs.crt
# with open("cacert.pem", "rb") as certfile:
#     ssl_context.load_verify_locations(cadata=certfile.read())
# ssl_context.set_default_verify_paths()
# pool = socketpool.SocketPool(wifi.radio)
# session = requests.Session(pool, ssl_context)

# print("-" * 40)
# print("Nothing yet opened")
# connection_manager = cm.get_connection_manager(pool)
# print(f"Managed Sockets: {connection_manager.managed_socket_count}")
# print(f"Available Managed Sockets: {connection_manager.available_socket_count}")

print("-" * 80)
print("Init Time API instance and set RTC time...")
time_api = LocalTimeAPI(session)
time_api.set_datetime()
print(f"✅ Current RTC time: {time_api.get_datetime()}")
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
    dbx_access_token_expiration = os.getenv("DBX_EXPIRES_AT") # = tokens["oauth_result"].expires_at converted to seconds
    #print(dbx_access_token_expiration)

    # Init client
    print("  Init client...") 
    from dropbox_cpy import DropboxAPI
    dbx = DropboxAPI(
        oauth2_access_token=dbx_access_token,
        user_agent='XiaoCPY1/0.0.1',
        oauth2_access_token_expiration=dbx_access_token_expiration, #seconds, not datetime.datetime!
        oauth2_refresh_token=dbx_refresh_token,
        session=session,
        app_key=dbx_app_key,
        app_secret=dbx_app_secret
    )
    print("  ✅ Passed")

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
    print("  Get user account info...") 
    info = dbx.users_get_current_account()
    # info._all_field_names_ =
    # {'account_id', 'is_paired', 'locale', 'email', 'name', 'team', 'country', 'account_type', 'referral_link'}
    print(f"  Current account info:\n  {info}\n  ✅ Passed")

    # print("-" * 40)
    # print("  Create folder...") 
    # create_folder = dbx.files_create_folder("/120425")
    # print(f"  Create folder result:\n  {create_folder}\n  ✅ Passed")

    # print("-" * 40)
    # print("  Upload image from SD card...") 
    # with open("/sd/image.jpg", "rb") as f:
    #     res = dbx.files_upload(f, "/120425/image.jpg")
    #     print(f"  Upload file result:\n  {res}\n  ✅ Passed")

    # print("-" * 40)
    # print("  List folder content...") 
    # files_list_folder = dbx.files_list_folder("/120425")
    # print(f"  List folder result:\n  {files_list_folder}\n  ✅ Passed")

    print("✅ Passed. Test Dropbox API: Done")

except Exception as e:
    print(f"❌ Error. {e}")
    raise
finally:
    print("-" * 80)
