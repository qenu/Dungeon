import random
from dataclasses import dataclass

from discord import Colour

from ..data.conf import CHARACTER_LEVEL_LIMIT


@dataclass()
class Stats:
    vit: int = 0  # vitality 蠻力
    dex: int = 0  # dexerity 技巧
    sta: int = 0  # stamina 體質
    psy: int = 0  # psychic 精神
    luk: int = 0  # luck 幸運

    def __dict__(self):
        return {
            "vit": self.vit,
            "dex": self.dex,
            "sta": self.sta,
            "psy": self.psy,
            "luk": self.luk,
        }


class Player:
    def __init__(self, *, data: dict = {}):
        # custom
        self.status = data.get("status", "")
        self.colour = Colour(
            data.get("colour", Colour.blurple().value)
        )  # store with colour value

        # stats
        self.level = data.get("level", 1)
        self.exp = data.get("exp", 0)
        self.job = data.get("job", "novice")
        stats = data.get("stats", {})
        self.stats = Stats()
        self.stats.str = stats.get("str", 3)
        self.stats.dex = stats.get("dex", 3)
        self.stats.con = stats.get("con", 3)
        self.stats.wis = stats.get("wis", 3)
        self.stats.luk = stats.get("luk", 5)

        # stats_mod
        self.str_mod = data.get("str_mod", 1.0)
        self.dex_mod = data.get("dex_mod", 1.0)
        self.con_mod = data.get("con_mod", 1.0)
        self.wis_mod = data.get("wis_mod", 1.0)
        self.luk_mod = data.get("luk_mod", 1.5)
        self.blessing = data.get("blessing", [])

        # inventory
        self.allowed_inventory = data.get("allowed_inventory", 20)
        self.inventory = data.get("inventory", [])  # list of uuid of items
        self.chest = data.get("chest", 0)  # loot from killed monsters
        self.legendary_chest = data.get(
            "legendary_chest", []
        )  # list of boss name killed
        self.soulshard = data.get("soulshard", 0)

        # equips
        self.head = data.get("head", "")
        self.necklace = data.get("necklace", "")

        self.body = data.get("body", "")
        self.pants = data.get("pants", "")

        self.gloves = data.get("gloves", "")
        self.boots = data.get("boots", "")

        self.weapon = data.get("weapon", "")
        self.ring = data.get("ring", "")

        self.equipment_stats = Stats()
        equipment_stats = data.get("equipment_stats", {})
        self.equipment_stats.str = equipment_stats.get("str", 0)
        self.equipment_stats.dex = equipment_stats.get("dex", 0)
        self.equipment_stats.con = equipment_stats.get("con", 0)
        self.equipment_stats.wis = equipment_stats.get("wis", 0)
        self.equipment_stats.luk = equipment_stats.get("luk", 0)

        self.range_adjustment = data.get("range_adjustment", 0)

        # record
        self.killed_bosses = data.get("killed_bosses", 0)
        self.killed_mobs = data.get("killed_mobs", 0)
        self.max_damage = data.get("max_damage", 0)
        self.total_damage = data.get("total_damage", 0)
        self.last_seen = data.get("last_seen", 0)  # todo: if 0, then perma
        self.petty = data.get("petty", 0)

    def __dict__(self) -> dict:
        return {
            "status": self.status,
            "colour": self.colour.value,
            "rebirth": self.rebirth,
            "level": self.level,
            "exp": self.exp,
            "job": self.job,
            "stats": {
                "str": self.stats.str,
                "dex": self.stats.dex,
                "con": self.stats.con,
                "wis": self.stats.wis,
                "luk": self.stats.luk,
            },
            "str_mod": self.str_mod,
            "dex_mod": self.dex_mod,
            "con_mod": self.con_mod,
            "wis_mod": self.wis_mod,
            "luk_mod": self.luk_mod,
            "blessing": self.blessing,
            "remain_stats": self.remain_stats,
            "potential": {
                "str": self.potential.str,
                "dex": self.potential.dex,
                "con": self.potential.con,
                "wis": self.potential.wis,
                "luk": self.potential.luk,
            },
            "allowed_inventory": self.allowed_inventory,
            "inventory": self.inventory,
            "chest": self.chest,
            "legendary_chest": self.legendary_chest,
            "soulshard": self.soulshard,
            "head": self.head,
            "necklace": self.necklace,
            "body": self.body,
            "pants": self.pants,
            "gloves": self.gloves,
            "boots": self.boots,
            "weapon": self.weapon,
            "ring": self.ring,
            "equipment_stats": {
                "str": self.equipment_stats.str,
                "dex": self.equipment_stats.dex,
                "con": self.equipment_stats.con,
                "wis": self.equipment_stats.wis,
                "luk": self.equipment_stats.luk,
            },
            "range_adjustment": self.range_adjustment,
            "killed_bosses": self.killed_bosses,
            "killed_mobs": self.killed_mobs,
            "max_damage": self.max_damage,
            "total_damage": self.total_damage,
            "last_seen": self.last_seen,
            "petty": self.petty,
        }

    def exp_required(self, level: int) -> int:
        """
        Get exp required to level up
        """
        return round(
            pow(level, 7) * 0.000000005
            + pow(level, 6) * 0.0000008
            + pow(level, 5) * 0.000018
            + pow(level, 4) * 0.0012
            + pow(level, 3) * 0.6
            + pow(level, 2) * 1.5
            + level * 12.2
        )

    def check_levelup(self) -> bool:
        if self.level == CHARACTER_LEVEL_LIMIT:
            return False
        if self.exp >= self.exp_required(self.level):
            self.level += 1
            self.exp = 0
            self.remain_stats += 3
            return True
        return False

    def add_exp(self, exp: int) -> None:
        """
        Add exp to player
        """
        self.exp += exp

    def get_rebirth(self) -> "Player":
        """
        Return a new player with rebirth stats
        """
        p = Player()
        p.rebirth = self.rebirth + 1
        p.potential.str = int(self.stats.str / 2) + self.potential.str
        p.potential.dex = int(self.stats.dex / 2) + self.potential.dex
        p.potential.con = int(self.stats.con / 2) + self.potential.con
        p.potential.wis = int(self.stats.wis / 2) + self.potential.wis
        p.potential.luk = 15 + self.potential.luk
        p.killed_bosses = self.killed_bosses
        p.killed_mobs = self.killed_mobs
        p.max_damage = self.max_damage
        p.total_damage = self.total_damage
        p.status = self.status
        p.colour = self.colour
        p.last_seen = self.last_seen
        p.soulshard = self.soulshard + 1

        return p

    def reset_ability_points(self) -> None:
        """
        Reset ability points
        """
        self.level -= 10
        self.stats.str = 3
        self.stats.dex = 3
        self.stats.con = 3
        self.stats.wis = 3

        self.remain_stats = (self.level - 1) * 3

    @property
    def damage_type(self) -> bool:
        return self._strength >= self._wisdom

    @property
    def _strength(self) -> int:
        return self.stats.str + self.potential.str + self.equipment_stats.str

    @property
    def strength(self) -> int:
        return max(int(self._strength * self.dex_mod), 1)

    @property
    def _dexterity(self) -> int:
        return self.stats.dex + self.potential.dex + self.equipment_stats.dex

    @property
    def dexterity(self) -> int:
        return max(int(self._dexterity * self.dex_mod), 1)

    @property
    def _constitution(self) -> int:
        return self.stats.con + self.potential.con + self.equipment_stats.con

    @property
    def constitution(self) -> int:
        return max(int(self._constitution * self.con_mod), 1)

    @property
    def _wisdom(self) -> int:
        return self.stats.wis + self.potential.wis + self.equipment_stats.wis

    @property
    def wisdom(self) -> int:
        return max(int(self._wisdom * self.wis_mod), 1)

    @property
    def _luck(self) -> int:
        return self.stats.luk + self.potential.luk + self.equipment_stats.luk

    @property
    def luck(self) -> int:
        return max(int(self._luck * self.luk_mod), 1)

    @property
    def agility(self) -> int:
        if self.damage_type:
            return self.dexterity
        return max(int(self.wisdom * 1.6), 1)

    @property
    def health(self) -> int:
        return int(self.constitution * 10 * max(self.level / 10, 1))

    @property
    def tenacity(self) -> float:
        return self.constitution * 1.2

    @property
    def high_damage(self) -> int:
        if self.damage_type:
            return int(self.strength * 3.1 + self.dexterity / 2 + self.constitution / 2)
        else:
            return int(self.wisdom * 4.2 + self.constitution / 4)

    @property
    def low_damage(self) -> int:
        return int(self.high_damage * min(self.range_adjustment, 100) / 100)

    @property
    def damage(self) -> int:
        return random.randint(self.low_damage, self.high_damage)

    @property
    def critical_chance(self) -> int:
        return int(self.dexterity / 100 + self.luck / 50) + 5 if self.damage_type else 0
