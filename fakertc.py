# -*- coding: utf-8 -*-
# A simple RTC shim, which allows running some parts of the code in a CPython environment (development machine).
#
# MIT License (MIT), see LICENSE - Copyright (c) 2025 Istvan Z. Kovacs
#
import time
class RTC:
    @property
    def datetime(self):
        return time.localtime()
    @datetime.setter
    def datetime(self, value):
        pass