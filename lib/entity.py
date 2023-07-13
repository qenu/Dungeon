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
        self.pdef = data.get("pdef", 0)  # physical defense
        self.mdef = data.get("mdef", 0)  # magical defense
        self.pdi = data.get("pdi", 0)  # physical defense ignore
        self.mdi = data.get("mdi", 0)  # magical defense ignore
        self.speed = data.get("speed", 75)  # base speed should be 75
        self.enmity = data.get("enmity", 75)  # enmity

        # data
        self.level = data.get("level", 1)

    @property
    def _vitality(self) -> float:
        return round(self.vit * self.vit_mod - self.mys / 100, 4)

    @property
    def vitality(self) -> int:
        return max(int(self._vitality + self.equip_stats.vit), 0)

    @property
    def _dexterity(self) -> float:
        return round(self.dex * self.dex_mod - self.sta / 100, 4)

    @property
    def dexterity(self) -> int:
        return max(int(self._dexterity + self.equip_stats.dex), 0)

    @property
    def _stamina(self) -> float:
        return round(self.sta * self.sta_mod - self.dex / 100, 4)

    @property
    def stamina(self) -> int:
        return max(int(self._stamina + self.equip_stats.sta), 0)

    @property
    def _mystic(self) -> float:
        return round(self.mys * self.mys_mod - self.vit / 100, 4)

    @property
    def mystic(self) -> int:
        return max(int(self._mystic + self.equip_stats.mys), 0)

    @property
    def _luck(self) -> int:
        return int(self.luk * self.luk_mod)

    @property
    def luck(self) -> int:
        return max(int(self._luck + self.equip_stats.luk), 0)

    @property
    def _max_health(self) -> int:
        return int(self.level + self.stamina + max(self.level / 10, 1) * 50)

    @property
    def regen(self) -> float:
        """Health recovered every 10 seconds"""
        return round(self.stamina * 2.5, 4)

    @property
    def accuracy(self) -> float:
        """Accuracy is a percentage in int, not a number"""
        return round(
            self.dexterity
            * 100
            / ((self.vitality + self.mystic) * 1.6 + self.dexterity * 0.2),
            4,
        )

    @property
    def _physical_base_damage(self) -> int:
        return int(min(self.vitality * self.accuracy, self.vitality * 0.9))

    @property
    def _physical_max_damage(self) -> int:
        return int(max(self.vitality * self.accuracy, self.vitality * 1.1))

    @property
    def pdmg(self) -> int:
        return random.randint(self._physical_base_damage, self._physical_max_damage)

    @property
    def _magical_base_damage(self) -> int:
        return int(min(self.mystic * self.accuracy, self.mystic * 0.9))

    @property
    def _magical_max_damage(self) -> int:
        return int(max(self.mystic * self.accuracy, self.mystic * 1.1))

    @property
    def mdmg(self) -> int:
        return random.randint(self._magical_base_damage, self._magical_max_damage)
