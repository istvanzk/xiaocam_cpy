# -*- coding: utf-8 -*-
# The main function to handle XIAO camera, save images locally, upload images to Dropbox.
#
# MIT License (MIT), see LICENSE - Copyright (c) 2025 Istvan Z. Kovacs
#
import os
#import io
#import binascii
import board
import busio
import time
import wifi
import sdcardio
import storage
import espcamera
import rtc
import gc
import atexit
from sys import exit

from adafruit_connection_manager import connection_manager_close_all, get_radio_socketpool, get_radio_ssl_context
from adafruit_requests import Session
import adafruit_logging as logging

# Get the local modules
from tlconfig import camConfig, camTimerConfig, camDirConfig, camDbxConfig
from loghandlers import MainLogHandler, LogBatchFileHandler, AIOHandler
from local_time import LocalTimeAPI
from dropbox_cpy import DropboxAPI

# Global variables
pool = None
vfs = None
cam = None
dbx = None


#
# Configure logging handlers and levels
#
LOG_MAIN_LEVEL = logging.INFO # Always enabled
LOG_TO_SD  = False
LOG_TO_SD_LEVEL = logging.DEBUG
LOG_TO_AIO = False
LOG_TO_AIO_LEVEL = logging.INFO


class ProcUploadSpeedKBps():
    """
    Measure the processing+upload speed in KByte/s.
    Use a moving average to smooth the values.
    The moving average is calculated over a window of size window_size.
    """
    def __init__(self, window_size: int = 10):
        self.start_time = 0
        self.stop_time = 0
        self.file_size = 0
        self.window_size = window_size
        self.upload_speed_vals = []
        self.upload_speed_avg = 0

    def start(self):
        """
        Start the proc+upload speed measurement.
        """
        self.start_time = time.monotonic()
        self.file_size = 0
        self.upload_speed_avg = 0
        return self.start_time
    
    def avg_elapsed_time_sec(self, file_size: int) -> float:
        """
        Stop the proc+upload speed measurement and
        return the averaged elapsed time in sec, based on moving-averaged proce+upload speed
        """
        self.stop_time = time.monotonic()
        self.file_size = file_size

        # Calculate the upload speed in KByte/s
        _upload_speed = float((file_size/1024) / (self.stop_time - self.start_time))
        self.upload_speed_vals.append(_upload_speed)
        if len(self.upload_speed_vals) > self.window_size:
            self.upload_speed_vals.pop(0)   
        self.upload_speed_avg = sum(self.upload_speed_vals) / len(self.upload_speed_vals)

        # Reset the start and stop time
        self.start_time = 0
        self.stop_time = 0

        return float((file_size/1024)/self.upload_speed_avg)
    
    def reset(self):
        """
        Reset the proc+upload speed measurement.
        """
        self.start_time = 0
        self.stop_time = 0
        self.file_size = 0
        self.upload_speed_avg = 0
        self.upload_speed_vals.clear()

def debug_print_exception(exc):
    from traceback import print_exception
    print_exception(exc)

def cleanup_atexit():
    global cam
    global vfs
    global pool

    # Deinitialize the camera
    if cam is not None:
        cam.deinit()
        camlog.info(f"Camera deinitialized")

    # Unmount the SD card
    if vfs is not None:
        storage.umount(vfs)
        _sd.deinit()
        del vfs
        camlog.info(f"SD card unmounted")

    # Close all open sockets for pool, do not release references
    if pool is not None:
        connection_manager_close_all(pool)
        camlog.info(f"All open sockets closed")
        
    # Free up memory
    gc.collect()

    time.sleep(1)
    camlog.info(f"Timelapse stopped. Bye.")



def _path_exists(path: str, file_dir: str) -> bool:
    """ Check if the file/dir exists in local path """
    if file_dir in os.listdir(path):
        return True
    return False


def _gen_list_folders_start_stop_datetime(
    start_datetime: time.struct_time,
    stop_datetime: time.struct_time,
) -> list[str]:
    """
    Generate list of folder names for the images between start and stop datetime 
    
    :param start_datetime: Start datetime
    :param stop_datetime: Stop datetime
    :return: List of folder names, in YMD format
    """
    # Initialize the list of folder names
    folders_list = []

    # Generate the list of folders between start and stop datetime
    _datetime = start_datetime
    while _datetime <= stop_datetime:
        folders_list.append(f"{_datetime.tm_year:04d}{_datetime.tm_mon:02d}{_datetime.tm_mday:02d}")
        _datetime = time.localtime(time.mktime(start_datetime) + 86400)

#
# Register the cleanup function to be called on exit
#
atexit.register(cleanup_atexit)

#
# Initialize the logger and handlers
#
camlog = logging.getLogger('cammain')
camlog.setLevel(LOG_MAIN_LEVEL)
# More handlers can be added later after the SD card is mounted and WiFi is connected
main_handler = MainLogHandler()
main_handler.setLevel(LOG_MAIN_LEVEL)
camlog.addHandler(main_handler)
assert camlog.hasHandlers()


#
# Mount SD card
#
if not hasattr(board, 'SDCS'):
    camlog.critical("No SD card detected")
    exit(1)
_sd = sdcardio.SDCard(board.SPI(), board.SDCS)
vfs = storage.VfsFat(_sd)
storage.mount(vfs, '/sd')
camlog.info("SD card mounted on /sd")

# Logging to SD card
if LOG_TO_SD:
    file_handler = LogBatchFileHandler('/sd/camlog.txt')
    file_handler.setLevel(LOG_TO_SD_LEVEL)
    camlog.addHandler(file_handler)


#
# WiFi init, with params from settings.toml
#
ssid = os.getenv("CIRCUITPY_WIFI_SSID")
password = os.getenv("CIRCUITPY_WIFI_PASSWORD")
if ssid is not None and password is not None:
    rssi = wifi.radio.ap_info.rssi
    ip = wifi.radio.ipv4_address
    camlog.debug(f"Signal Strength: {rssi}")
    camlog.debug(f"IP Address: {ip}")
    camlog.debug(f"Connecting to {ssid}...")
    wifi_available = True
    try:
        # Connect to the Wi-Fi network
        #wifi.radio.mtu = 1400
        wifi.radio.connect(ssid, password)
    except OSError as e:
        wifi_available = False
        camlog.critical(f"OSError: {e}")
        exit(1)
    camlog.info("WiFi connected")
else:
    camlog.critical("WiFi SSID and/or PASSWORD not configured in settings.toml")
    exit(1)

#
# Initalize Socket Pool, Request Session
#
pool = get_radio_socketpool(wifi.radio)
ssl_context = get_radio_ssl_context(wifi.radio)
requests_other = Session(pool, ssl_context)
requests_dropbox = Session(pool, ssl_context, session_id="dbx")

# Logging to Adafruit IO
if LOG_TO_AIO:
    aio_handler = AIOHandler('xiaocam', requests_other)
    aio_handler.setLevel(LOG_TO_AIO_LEVEL)
    camlog.addHandler(aio_handler)

#
# Local Time API init
#
time_api = LocalTimeAPI(requests_other)
if time_api.set_datetime():
    camlog.info(f"RTC time set {time_api.get_datetime()}")
else:
    camlog.critical("RTC time not set")
    exit(1)

#
# Timer init
#
if camTimerConfig['start_datetime'] is not None:
    date_start, time_start = camTimerConfig['start_datetime'].split('T')
    _ymd = date_start.split('-')
    _hms = time_start.split(':')
    _wday = 0 # TODO: Get the weekday from the start date
    start_time = time.struct_time((
        int(_ymd[0]),
        int(_ymd[1]),
        int(_ymd[2]),
        int(_hms[0]),
        int(_hms[1]),
        int(_hms[2]),
        _wday,
        -1,
        -1
    ))
else:
    start_time = time_api.get_datetime()

if camTimerConfig['stop_datetime'] is not None: 
    date_stop, time_stop = camTimerConfig['stop_datetime'].split('T')
    _ymd = date_stop.split('-')
    _hms = time_stop.split(':')
    _wday = 0 # TODO: Get the weekday from the stop date
    stop_time = time.struct_time((
        int(_ymd[0]),
        int(_ymd[1]),
        int(_ymd[2]),
        int(_hms[0]),
        int(_hms[1]),
        int(_hms[2]),
        _wday,
        -1,
        -1
    ))
else:
    stop_time = None

# Set the time interval
# The minimum is approx. [30, 45] due to image upload speed limit
if camTimerConfig['interval_sec'] is not None:
    interval_sec = camTimerConfig['interval_sec']
    if interval_sec[0] < 30:
        interval_sec[0] = 30
    if len(interval_sec) == 1:
        interval_sec.append(interval_sec[0]+15)
    else:
        if interval_sec[1] < 45:
            interval_sec[1] = 45
else:
    interval_sec = [30, 45]


# Set the dark hours and minutes (None indicates not set/used)
dark_hours_mins = [None, None]
if camTimerConfig['dark_hours'] is not None:
    dark_hours_mins[0] = camTimerConfig['dark_hours'][0] * 60 
    dark_hours_mins[1] = camTimerConfig['dark_hours'][1] * 60
    if camTimerConfig['dark_mins'] is not None:
        dark_hours_mins[0] += camTimerConfig['dark_mins'][0]
        dark_hours_mins[1] += camTimerConfig['dark_mins'][1]

camlog.info("Camera timer initialized")
camlog.debug(f"Start time: {start_time}, Stop time: {stop_time}, Interval: {interval_sec}sec, Dark hours_mins: {dark_hours_mins}")

#
# Camera init
# https://docs.circuitpython.org/en/latest/shared-bindings/espcamera/index.html
#
if camConfig['cam_id'] is not None:
    cam_i2c = busio.I2C(board.CAM_SCL, board.CAM_SDA)
    cam = espcamera.Camera(
        data_pins=board.CAM_DATA,
        external_clock_pin=board.CAM_XCLK,
        pixel_clock_pin=board.CAM_PCLK,
        vsync_pin=board.CAM_VSYNC,
        href_pin=board.CAM_HREF,
        pixel_format=espcamera.PixelFormat.JPEG,
        frame_size=eval(f"espcamera.FrameSize.{camConfig['image_res']}"), #R240X240, SVGA, VGA, SVGA, XGA, SXGA, UXGA
        i2c=cam_i2c,
        external_clock_frequency=20_000_000,
        #framebuffer_count=2,
        grab_mode=espcamera.GrabMode.WHEN_EMPTY)

    # Set the camera parameters
    if camConfig['image_rot'] == 180:
        cam.hmirror = True
        cam.vflip   = True
    else:
        cam.hmirror = False
        cam.vflip   = False

    cam.whitebal      = True
    cam.exposure_ctrl = True
    cam.saturation = 0 #  -2 to +2 inclusive
    cam.brightness = 0 #  -2 to +2 inclusive
    cam.contrast   = 0 #  -2 to +2 inclusive
    #cam.aec2       = False # When True the sensor’s “night mode” is enabled, extending the range of automatic gain control

    # Capture the first image
    cam.take(1)

    camlog.info("Camera initialized")
    camlog.debug(f"Sensor: {cam.sensor_name}")
    if cam.supports_jpeg:
        cam.quality = camConfig['jpg_qual']
    else:
        camlog.critical("Sensor can not capture images in JPEG format")
        exit(1)

else:
    camlog.critical("Camera not configured")
    exit(1)

#
# SD Card init
#
if camDirConfig['image_dir'] is not None:

    if not _path_exists("/sd", f"{camDirConfig['image_dir']}"):
        os.mkdir(f"/sd/{camDirConfig['image_dir']}")

    camlog.info(f"SD card folder initialized: /sd/{camDirConfig['image_dir']}")
    camlog.debug(f"Folder /sd/{camDirConfig['image_dir']} initialized. List size: {camDirConfig['list_size']}")

else:
    camlog.critical("SD card not configured")
    exit(1)

#
# Dropbox API init
#
if camDbxConfig['image_dir'] is not None:
    # Load tokens from the environment variables stored in settings.toml
    # These correspond to info in tokens["oauth_result"] as returned from the Dropbox OAuth2 flow
    dbx_app_key       = os.getenv("DBX_APP_KEY")       # = tokens["oauth_result"].app_key
    dbx_app_secret    = os.getenv("DBX_APP_SECRET")    # = tokens["oauth_result"].app_secret
    dbx_access_token  = os.getenv("DBX_ACCESS_TOKEN")  # = tokens["oauth_result"].access_token
    dbx_refresh_token = os.getenv("DBX_REFRESH_TOKEN") # = tokens["oauth_result"].refresh_token
    dbx_access_token_expiration = int(os.getenv("DBX_EXPIRES_AT")) # = tokens["oauth_result"].expires_at converted to seconds
    #print(dbx_access_token_expiration)

    # Init client
    dbx = DropboxAPI(
        oauth2_access_token=dbx_access_token,
        user_agent='XiaoCPY1/0.5.0',
        oauth2_access_token_expiration=dbx_access_token_expiration, #seconds, not datetime.datetime!
        oauth2_refresh_token=dbx_refresh_token,
        session=requests_dropbox,
        timeout=20,
        app_key=dbx_app_key,
        app_secret=dbx_app_secret
    )
    camlog.info("Dropbox Client API initialized")

    # The upload root folder
    time.sleep(1)
    if not dbx.path_exists(f"/{camDbxConfig['image_dir']}"):
        dbx.files_create_folder(f"/{camDbxConfig['image_dir']}", autorename=False)

    # The estimated processsing+upload time (sec) in KByte per second.
    # This estimate will be adjusted based on actual file size and measured processsing+upload speed
    # The upload time value is substracted from the configured timelapse interval, interval_sec
    avg_proc_speed_KBps = ProcUploadSpeedKBps()

    camlog.info(f"Dropbox folder initialized")
    camlog.debug(f"Upload folder: {camDbxConfig['image_dir']}")
    time.sleep(1)

else:
    camlog.critical("Dropbox not configured")
    exit(1)


#
# Main loop
#
camlog.info("Start timelapse")
prev_dark_mode = False
prev_ymd = ""
run_timelapse = True
image_count = 0
while run_timelapse:
    try:
        # Check if the current time is within the start and stop time
        current_time = time_api.get_datetime()
        time_interval_adj = 0
        if start_time <= current_time <= stop_time:

            # Check if the current time is within the dark hours
            dark_mode = False
            if dark_hours_mins[0] is not None:

                # Current hour & minutes in minutes
                current_time_mins = current_time.tm_hour * 60 + current_time.tm_min

                # If the dark hours span midnight, adjust the condition
                if dark_hours_mins[1] < dark_hours_mins[0]:
                    if current_time_mins >= dark_hours_mins[0] or current_time_mins <= dark_hours_mins[1]:
                        dark_mode = True
                else:
                    if current_time_mins >= dark_hours_mins[0] and current_time_mins <= dark_hours_mins[1]:
                        dark_mode = True

            # Select the configured time interval
            if not dark_mode:
                time_interval = interval_sec[0]
            else:
                time_interval = interval_sec[1]

            # Change camera settings only when switching between dark mode and dayligh mode
            if not prev_dark_mode and dark_mode:
                prev_dark_mode = True

                # Set camera to "night mode"
                cam.brightness = 2
                cam.aec2 = True
                
                #cam.agc_gain = 20 # from 0 to 30.

                #cam.gain_ctrl = True
                #cam.gain_ceiling = espcamera.GainCeiling.GAIN_8X

                #cam.exposure_ctrl = False
                #cam.aec_value = 200 #from 0 to 1200

                camlog.info(f"Night mode: {time_interval}sec")

            elif prev_dark_mode and not dark_mode:
                prev_dark_mode = False
                
                # Set camera to day/normal mode
                cam.brightness = 0
                cam.aec2   = False

                #cam.agc_gain = 0 # from 0 to 30.
                cam.gain_ctrl = True
                cam.exposure_ctrl = True

                camlog.info(f"Daylight mode: {time_interval}sec")

            # Capture an image
            frame = cam.take(1)
            #while not cam.frame_available:
            #    time.sleep(0.1)
            if isinstance(frame, memoryview):
                # Start estimate procesing+upload speed
                avg_proc_speed_KBps.start()

                image_count += 1
                camlog.debug(f"Image #{image_count} available")
                
                current_time = time_api.get_datetime()
                ymd_str = f"{current_time.tm_year:04d}{current_time.tm_mon:02d}{current_time.tm_mday:02d}"
                hms_str = f"{current_time.tm_hour:02d}{current_time.tm_min:02d}{current_time.tm_sec:02d}"
                dir_img_path = f"/{camDirConfig['image_dir']}/{ymd_str}/{ymd_str}-{hms_str}-{camConfig['cam_id']}.jpg"
                dbx_img_path = f"/{camDbxConfig['image_dir']}/{ymd_str}/{ymd_str}-{hms_str}-{camConfig['cam_id']}.jpg"

                # Save the image locally on the SD card
                if prev_ymd != ymd_str:
                    if not _path_exists(f"/sd/{camDirConfig['image_dir']}", f"{ymd_str}"):
                        os.mkdir(f"/sd/{camDirConfig['image_dir']}/{ymd_str}")
                with open(f"/sd{dir_img_path}", "wb") as f:
                    f.write(frame)
                camlog.debug(f"Image #{image_count} saved locally")

                # Upload to Dropbox
                if prev_ymd != ymd_str:
                    dbx.files_create_folder(f"/{camDbxConfig['image_dir']}/{ymd_str}", autorename=False)
                with open(f"/sd{dir_img_path}", "rb") as f:
                    res = dbx.files_upload(f, dbx_img_path)
                #encoded_data = binascii.b2a_base64(frame).strip()
                #res = dbx.files_upload(frame, dbx_img_path)
                camlog.debug(f"Image #{image_count} uploaded")

                # Update previous ymd value to avoid folder operations
                if prev_ymd != ymd_str:
                    prev_ymd == ymd_str

                # The average time interval adjustement value
                time_interval_adj = avg_proc_speed_KBps.avg_elapsed_time_sec(len(frame))

                # Free the memory
                del frame
                gc.collect()
                camlog.info(f"Image {image_count:03d} saved locally and uploaded to Dropbox")
            else:
                camlog.error("New image not available from camera!")

            # Check if the image count reached the list size
            if image_count >= camDirConfig['list_size']:
                camlog.error(f"Image list size ({image_count}) reached, stopping timelapse")
                run_timelapse = False
                continue

        else:
            camlog.warning("Outside of timer range, no image capture")

        # Sleep for the specified interval
        camlog.info(f"Sleep {time_interval-time_interval_adj}sec...")
        time.sleep(time_interval-time_interval_adj)

    except KeyboardInterrupt:
        camlog.info(f"KeyboardInterrupt: Stopped with CTRL-C")
        run_timelapse = False
        exit(0)

    except Exception as exc:
        camlog.critical(f"Exception: {exc}")
        #debug_print_exception(exc)
        run_timelapse = False
        exit(1)

