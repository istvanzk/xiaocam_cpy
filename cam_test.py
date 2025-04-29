# -*- coding: utf-8 -*-
# Test the espcamera functionalities
#
# MIT License (MIT), see LICENSE - Copyright (c) 2025 Istvan Z. Kovacs
#
import os
import board
import busio
import sdcardio
import storage
import espcamera

# dir(board)
# ['__class__', '__name__', 
# 'A0', 'A1', 'A2', 'A3', 'A4', 'A5', 
# 'CAM_D0', 'CAM_D1', 'CAM_D2', 'CAM_D3', 'CAM_D4', 'CAM_D5', 'CAM_D6', 'CAM_D7', 
# 'CAM_DATA', 'CAM_HREF', 'CAM_PCLK', 'CAM_SCL', 'CAM_SDA', 'CAM_VSYNC', 'CAM_XCLK', 
# 'D0', 'D1', 'D2', 'D3', 'D4', 'D5', 'D6', 'D7', 'D8', 'D9', 'D10',
# 'I2C', 'LED', 
# 'MIC_CLK', 'MIC_DATA', 
# 'MISO', 'MOSI',  'SCK', 
# 'SPI', 'SDCS', 
# 'SCL', 'SDA',  
# 'RX', 'TX', 'UART', 
# '__dict__', 'board_id']


def print_directory(path, tabs=0):
    for file in os.listdir(path):
        if file == "?":
            continue  # Issue noted in Learn
        stats = os.stat(path + "/" + file)
        filesize = stats[6]
        isdir = stats[0] & 0x4000

        if filesize < 1000:
            sizestr = str(filesize) + " B"
        elif filesize < 1000000:
            sizestr = "%0.1f KB" % (filesize / 1000)
        else:
            sizestr = "%0.1f MB" % (filesize / 1000000)

        prettyprintname = ""
        for _ in range(tabs):
            prettyprintname += "   "
        prettyprintname += file
        if isdir:
            prettyprintname += "/"
        print('{0:<40} {1:>10}'.format(prettyprintname, sizestr))

        # recursively print directory contents
        if isdir and not file.startswith(".Spotlight"):
            print_directory(path + "/" + file, tabs + 1)


# SD Card Init
# https://docs.circuitpython.org/en/latest/shared-bindings/sdcardio/index.html
sd = sdcardio.SDCard(board.SPI(), board.SDCS)
vfs = storage.VfsFat(sd)
storage.mount(vfs, '/sd')
#print(os.listdir('/sd'))

# Camera Init
# https://docs.circuitpython.org/en/latest/shared-bindings/espcamera/index.html#espcamera.Camera
cam_i2c = busio.I2C(board.CAM_SCL, board.CAM_SDA)
cam = espcamera.Camera(
    data_pins=board.CAM_DATA,
    external_clock_pin=board.CAM_XCLK,
    pixel_clock_pin=board.CAM_PCLK,
    vsync_pin=board.CAM_VSYNC,
    href_pin=board.CAM_HREF,
    pixel_format=espcamera.PixelFormat.JPEG,
    frame_size=espcamera.FrameSize.XGA, #R240X240, SVGA, VGA, SVGA, XGA, SXGA, UXGA
    i2c=cam_i2c,
    external_clock_frequency=20_000_000,
    framebuffer_count=2,
    grab_mode=espcamera.GrabMode.WHEN_EMPTY)

# Typical values range from 5 to 40
cam.quality = 20

# If pixel_format is PixelFormat.JPEG, the returned value is a read-only memoryview. 
# Otherwise, the returned value is a read-only displayio.Bitmap.
frame = cam.take(1)
if isinstance(frame, memoryview):
    print("JPEG image size: ", len(frame))
    with open("/sd/image.jpg", "wb") as f:
        f.write(frame)

else:
    print("Bitmap size: ", frame.width, frame.height)

cam.deinit()

print_directory("/sd")

storage.umount(vfs)
#sd.deinit()
