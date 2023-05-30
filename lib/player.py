import time

from discord import Colour

from .constant import CHARACTER_LEVEL_LIMIT
from .entity import Entity


class Player(Entity):
    def __init__(self, *, data: dict = {}):
        super().__init__(data=data)

        self.blessing = data.get("blessing", [])

        # equips
        self.head = data.get("head", "")
        self.necklace = data.get("necklace", "")
        self.body = data.get("body", "")
        self.pants = data.get("pants", "")
        self.gloves = data.get("gloves", "")
        self.boots = data.get("boots", "")
        self.weapon = data.get("weapon", "")
        self.ring = data.get("ring", "")

        equip_stats = data.get("equip_stats", {})
        self.equip_stats.vit = equip_stats.get("vit", 0)
        self.equip_stats.dex = equip_stats.get("dex", 0)
        self.equip_stats.sta = equip_stats.get("sta", 0)
        self.equip_stats.mys = equip_stats.get("mys", 0)
        self.equip_stats.luk = equip_stats.get("luk", 0)

        # data
        self.health = data.get("health", 0)
        self.exp = data.get("exp", 0)
        self.remain_stat = data.get("remain_stat", {})
        self.job = data.get("job", "novice")

        self.monster_cnt = data.get("monster_cnt", 0)
        self.max_dmg = data.get("max_dmg", 0)
        self.cum_dmg = data.get("cum_dmg", 0)

        self.allowed_inventory = data.get("allowed_inventory", 20)
        self.inventory = data.get("inventory", [])  # list of item uuid
        self.chest = data.get("chest", 0)  # loot from killed monsters
        self.soulstone = data.get("soulstone", 0)

        self.status = data.get("status", "")
        self.colour = Colour(
            data.get("colour", Colour.blurple().value)
        )  # store with colour value

        # hidden
        self.seen = data.get("seen", 0)  # todo: if 0, then perma
        self.petty = data.get("petty", 0)
        self.prev_ts = data.get("prev_ts", 0)
        self.dungeon = data.get("dungeon", None)  # UUID of dungeon

    def __dict__(self) -> dict:
        return {
            "vit": self.vit,
            "dex": self.dex,
            "sta": self.sta,
            "mys": self.mys,
            "luk": self.luk,
            "vit_mod": self.vit_mod,
            "dex_mod": self.dex_mod,
            "sta_mod": self.sta_mod,
            "mys_mod": self.mys_mod,
            "luk_mod": self.luk_mod,
            "blessing": self.blessing,
            "head": self.head,
            "necklace": self.necklace,
            "body": self.body,
            "pants": self.pants,
            "gloves": self.gloves,
            "boots": self.boots,
            "weapon": self.weapon,
            "ring": self.ring,
            "equip_stats": self.equip_stats.__dict__(),
            "health": self.health,
            "level": self.level,
            "exp": self.exp,
            "remain_stat": self.remain_stat,
            "job": self.job,
            "monster_cnt": self.monster_cnt,
            "max_dmg": self.max_dmg,
            "cum_dmg": self.cum_dmg,
            "allowed_inventory": self.allowed_inventory,
            "inventory": self.inventory,
            "chest": self.chest,
            "soulstone": self.soulstone,
            "status": self.status,
            "colour": self.colour.value,
            "seen": self.seen,
            "petty": self.petty,
            "prev_ts": self.prev_ts,
            "dungeon": self.dungeon,
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

    def _check_levelup(self) -> bool:
        """
        Checks player exp for leveling
        """
        if self.level == CHARACTER_LEVEL_LIMIT:
            return False
            if self.exp >= self.exp_required(self.level):
                self.level += 1
                self.exp = 0
                self.remain_stat += 3
                return True
            return False

    def add_exp(self, exp: int) -> None:
        """
        Add exp to player
        """
        self.exp += exp

    def refresh_health(self) -> int:
        """
        Refresh health for regen
        """
        max_health = self._max_health
        if self.prev_ts == 0:
            self.health = max_health
        elif self.health == max_health:
            pass
        else:
            self.health = min(
                int(time.time() / 60 * self.stamina * 2.5 + self.health), max_health
            )
        return self.health

    def reset_stats(self) -> None:
        """
        Halves player level to reset stats
        """
        self.level = int(self.level / 2)
        self.stats.vit = 3
        self.stats.dex = 3
        self.stats.sta = 3
        self.stats.mys = 3

        self.remain_stat = (self.level - 1) * 3
