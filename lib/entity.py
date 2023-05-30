import random

from .base import Stats, StatsModified


class Entity(StatsModified):
    def __init__(self, *, data: dict = {}):
        super().__init__(data=data)
        # stats
        self.vit = data.get("vit", 3)
        self.dex = data.get("dex", 3)
        self.sta = data.get("sta", 3)
        self.mys = data.get("mys", 3)
        self.luk = data.get("luk", 5)
        self.equip_stats = Stats()
        self.speed = data.get("speed", 75)  # base speed should be 75

        # data
        self.level = data.get("level", 1)

    @property
    def _vitality(self) -> int:
        return int(max(self.vit * self.vit_mod), 0)

    @property
    def vitality(self) -> int:
        return int(self._vitality + self.equip_stats.vit)

    @property
    def _dexterity(self) -> int:
        return int(max(self.dex * self.dex_mod), 0)

    @property
    def dexterity(self) -> int:
        return int(self._dexterity + self.equip_stats.dex)

    @property
    def _stamina(self) -> int:
        return int(max(self.sta * self.sta_mod), 0)

    @property
    def stamina(self) -> int:
        return int(self._stamina + self.equip_stats.sta)

    @property
    def _mystic(self) -> int:
        return int(max(self.mys * self.mys_mod), 0)

    @property
    def mystic(self) -> int:
        return int(self._mystic + self.equip_stats.mys)

    @property
    def _luck(self) -> int:
        return int(max(self.luk * self.luk_mod), 0)

    @property
    def luck(self) -> int:
        return int(self._luck + self.equip_stats.luk)

    @property
    def _max_health(self) -> int:
        return int(self.level + self.stamina + max(self.level / 10, 1) * 50)

    @property
    def regen(self) -> int:
        return int(self.stamina * 2.5)

    @property
    def accuracy(self) -> float:
        return self.dexterity / ((self.vitality + self.mystic) * 1.6)

    @property
    def _physical_base_damage(self) -> int:
        return int(min(self.vitality * self.accuracy, self.vitality * 0.9))

    @property
    def _physical_max_damage(self) -> int:
        return int(max(self.vitality * self.accuracy, self.vitality * 1.1))

    @property
    def physical_damage(self) -> int:
        return random.randint(self._physical_base_damage, self._physical_max_damage)

    @property
    def _magical_base_damage(self) -> int:
        return int(min(self.mystic * self.accuracy, self.mystic * 0.9))

    @property
    def _magical_max_damage(self) -> int:
        return int(max(self.mystic * self.accuracy, self.mystic * 1.1))

    @property
    def magical_damage(self) -> int:
        return random.randint(self._magical_base_damage, self._magical_max_damage)
