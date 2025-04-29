# -*- coding: utf-8 -*-
# Simple configuration file for the camera and timelapse
# Usage: from camcfg import camConfig, camTimerConfig, camDirConfig, camDbxConfig
#
# MIT License (MIT), see LICENSE - Copyright (c) 2025 Istvan Z. Kovacs
#

# Camera configuration
camConfig = {
  'cam_id': 'CAM1',
  'image_rot': 180, # 0 or 180
  'image_res': 'SVGA', # See https://docs.circuitpython.org/en/latest/shared-bindings/espcamera/index.html#espcamera.FrameSize
  'jpg_qual': 5, # 0=high quality to 63=low quality
}

# Camera timer configuration
camTimerConfig = {
  'start_datetime': '2025-01-01T00:00:00',
  'stop_datetime': '2025-12-31T23:59:59',
  'interval_sec': [30, 45],
  'dark_hours': [20, 7], 
  'dark_mins': [0, 0],
}

# Local storage configuration (SD card)
camDirConfig = {
  'image_dir': 'webcam',
  'list_size': 20,
}

# Remote storage configuration (Dropbox)
camDbxConfig = {
  'image_dir': 'webcam',
  'image_crt': 'cam1.jpg',
}