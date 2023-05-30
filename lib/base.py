from dataclasses import dataclass


@dataclass
class Stats:
    vit: int = 0  # vitality 蠻力
    dex: int = 0  # dexerity 技巧
    sta: int = 0  # stamina 體質
    mys: int = 0  # mystic 神秘
    luk: int = 0  # luck 幸運

    def __dict__(self):
        return {
            "vit": self.vit,
            "dex": self.dex,
            "sta": self.sta,
            "mys": self.mys,
            "luk": self.luk,
        }


@dataclass
class StatsModified(Stats):
    def __init__(self, *, data: dict = {}):
        super().__init__()
        self.vit_mod = data.get("vit_mod", 1.0)
        self.dex_mod = data.get("dex_mod", 1.0)
        self.sta_mod = data.get("sta_mod", 1.0)
        self.mys_mod = data.get("mys_mod", 1.0)
        self.luk_mod = data.get("luk_mod", 1.0)


@dataclass
class Job(StatsModified):  # read-only
    def __init__(self, *, data: dict = {}):
        super().__init__(data=data)
        self.name = data.get("name", "")
        self.icon = data.get("icon", "")
        self.description = data.get("description", "")


@dataclass
class MonsterInfo(StatsModified):
    def __init__(self, *, data: dict = {}):
        super().__init__(data=data)
        self.name = data.get("name", "")
        self.description = data.get("description", "")
        self.drop = data.get("drop", [])
