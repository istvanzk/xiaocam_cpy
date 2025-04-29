# -*- coding: utf-8 -*-
# Custom logging handlers
#
# MIT License (MIT), see LICENSE - Copyright (c) 2025 Istvan Z. Kovacs
#

import time
import sys
import os
from adafruit_logging import Handler, LogRecord
# https://docs.circuitpython.org/projects/adafruitio/en/latest/index.html
# https://github.com/adafruit/Adafruit_CircuitPython_AdafruitIO
from adafruit_io.adafruit_io import IO_HTTP

if sys.implementation.name == "circuitpython":
    from rtc import RTC
else:
    from fakertc import RTC


class MainLogHandler(Handler):
    """ Logging main function info. """

    def __init__(self):
        """Create an instance."""
        super().__init__()

    def format(self, record: LogRecord) -> str:
        """Generate a timestamped message.

        :param LogRecord record: The record (message object) to be logged
        """
        _rtc = RTC()
        _created = _rtc.datetime
        return f"{_created.tm_year:04d}-{_created.tm_mon:02d}-{_created.tm_mday:02d} {_created.tm_hour:02d}:{_created.tm_min:02d}:{_created.tm_sec:02d} - MainCam - {record.levelname} - {record.msg}"

    def emit(self, record: LogRecord):
        """Generate the message.

        :param LogRecord record: The record (message object) to be logged
        """
        print(self.format(record))

class AIOHandler(Handler):
    """ Logging to Adafruit IO. """

    def __init__(self, name, requests_session):
        """Create an instance."""
        super().__init__()

        self._log_feed_name=f"{name}-logging"
        self.io_http = IO_HTTP(
            os.getenv('ADAFRUIT_AIO_USERNAME'),
            os.getenv('ADAFRUIT_AIO_KEY'),
            requests_session,
        )
        self.log_feed = self.io_http.get_feed(self._log_feed_name)

    def format(self, record: LogRecord) -> str:
        """Generate a timestamped message.

        :param LogRecord record: The record (message object) to be logged
        """
        _rtc = RTC()
        _created = _rtc.datetime
        return f"{_created.tm_year:04d}-{_created.tm_mon:02d}-{_created.tm_mday:02d} {_created.tm_hour:02d}:{_created.tm_min:02d}:{_created.tm_sec:02d} - {record.levelname} - {record.msg}"

    def emit(self, record: LogRecord):
        """Generate the message and write it to the AIO Feed.

        :param LogRecord record: The record (message object) to be logged
        """
        self.io_http.send_data(self.log_feed['key'], self.format(record))


class LogBatchFileHandler(Handler):
    """ Logging to a list and saving to a file when the list length reaches list_size. """

    def __init__(self, name, list_size):
        """Create an instance."""
        super().__init__()
        self.list_size = list_size
        self.mesg_logs = []
        self._log_feed_name=f"{name}-batchlog"

    def format(self, record: LogRecord) -> str:
        """Generate a timestamped message.

        :param LogRecord record: The record (message object) to be logged
        """
        _rtc = RTC()
        _created = _rtc.datetime
        return f"{_created.tm_year:04d}-{_created.tm_mon:02d}-{_created.tm_mday:02d} {_created.tm_hour:02d}:{_created.tm_min:02d}:{_created.tm_sec:02d} - {record.levelname} - {record.msg}"

    def emit(self, record: LogRecord):
        """Generate the message and write it to the list.

        :param LogRecord record: The record (message object) to be logged
        """
        # Store log
        self.mesg_logs.append(self.format(record))

        # Save the logs to a text file
        if len(self.mesg_logs) == self.list_size:   
            all_logs = '\n'.join(self.mesg_logs)
            try: 
                with open(f"/sd/{self._log_feed_name}.txt", "w") as f:
                    f.write(all_logs)
            except OSError as e:
                print(f"Error writing to file: {e}")
            # Clear the list
            self.mesg_logs.clear()
