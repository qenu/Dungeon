import random

from .base import Stats
from .constant import LEGENDARY_SETS


class Item(Stats):
    def __init__(self, *, data: dict = {}):
        super().__init__(
            vit=data.get("vit", 0),
            dex=data.get("dex", 0),
            sta=data.get("sta", 0),
            mys=data.get("mys", 0),
            luk=data.get("luk", 0),
        )
        self._type = data.get("_type", "")
        self.level = data.get("level", 1)
        self.name = data.get("name", "")
        self.description = data.get("description", "")

        self._set = data.get("_set", False)

        self.reinforced = data.get("reinforced", 0)
        self.attempts = data.get("attempts", 0)
        self.state = data.get("state", True)

        r_stats = data.get("reinforced_stats", {})
        self.r_stats = Stats()
        self.r_stats.vit = r_stats.get("vit", 0)
        self.r_stats.dex = r_stats.get("dex", 0)
        self.r_stats.sta = r_stats.get("sta", 0)
        self.r_stats.mys = r_stats.get("mys", 0)

    def __copy__(self) -> "Item":
        return Item(data=self.__dict__())

    def __dict__(self) -> dict:
        return {
            "_type": self._type,
            "level": self.level,
            "name": self.name,
            "description": self.description,
            "vit": self.vit,
            "dex": self.dex,
            "sta": self.sta,
            "mys": self.mys,
            "luk": self.luk,
            "_set": self._set,
            "reinforced": self.reinforced,
            "attempts": self.attempts,
            "state": self.state,
            "r_stats": self.r_stats.__dict__(),
        }

    def _refresh_r_stats(self) -> None:
        """adjusts stats based on reinforcement"""
        rate = 0.3 if self.set in LEGENDARY_SETS else 0.15
        if self.reinforced <= 10:
            rate *= 1.5
        elif self.reinforced <= 15:
            rate *= 2
        elif self.reinforced <= 20:
            rate *= 2.5
        else:
            rate *= 3
        self.r_stats.vit = int(self.vit * (self.reinforced * rate))
        self.r_stats.dex = int(self.dex * (self.reinforced * rate))
        self.r_stats.sta = int(self.sta * (self.reinforced * rate))
        self.r_stats.mys = int(self.mys * (self.reinforced * rate))

    def _reinforce(self) -> bool:
        """only accounts for success, drop and destroy, doesn't calculate stats"""
        if not self.state:
            return False
        self.reinforce_attempts += 1
        if self.set in LEGENDARY_SETS:
            if 0.5 > random.random():
                self.reinforced += 1
                return True
            elif 0.9 > random.random() and self.reinforced not in [0, 5, 10, 15]:
                if min(0.3, self.reinforced * 0.05) > random.random():
                    return None
                self.reinforced -= 1
            return False

        else:
            if max(0.03, 0.9 - (self.reinforced * 0.05)) > random.random():
                self.reinforced += 1
                return True
            else:
                if not (self.reinforced <= 5 or self.reinforced in [10, 15]):
                    if min(3, (self.reinforced - 10)) * 0.1 > random.random():
                        return None
                    self.reinforced -= 1
                return False
