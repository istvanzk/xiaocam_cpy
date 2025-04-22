import time
class RTC:
    @property
    def datetime(self):
        return time.localtime()
    @datetime.setter
    def datetime(self, value):
        pass