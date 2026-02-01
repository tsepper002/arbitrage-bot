import time


class ExchangeState:
    def __init__(self, name: str):
        self.name = name
        self.online = False
        self.last_update = 0
        self.error = None

    def set_online(self):
        self.online = True
        self.last_update = time.time()
        self.error = None

    def set_offline(self, error: str | None = None):
        self.online = False
        self.last_update = time.time()
        self.error = error

    def as_dict(self):
        return {
            "name": self.name,
            "online": self.online,
            "last_update": self.last_update,
            "error": self.error,
        }


STATE: dict[str, ExchangeState] = {}
