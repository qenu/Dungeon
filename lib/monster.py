import random
from typing import Optional

from .base import MonsterInfo
from .entity import Entity


class Monster(Entity):
    def __init__(
        self, *, info: MonsterInfo, level: int = 1, elite: Optional[bool] = None
    ):
        super().__init__(data={})  # no data needed
        self.elite = random.random() < 0.1 if elite is None else elite

        # MonsterInfo
        self.name = info.name
        self.description = info.description
        drops = info.drops

        # stats
        stats = [max(int(self.level * 0.6), 1)] * 4
        for _ in range(self.level):
            stats[random.randrange(len(stats))] += 1
        if self.elite:
            stats[random.randrange(len(stats))] *= 1.2
        self.vit, self.dex, self.sta, self.mys = stats
        # prefix
        if self.elite:
            top_stat = max([self.vitality, self.dexterity, self.stamina, self.mystic])
            if top_stat == self.vitality:
                prefix = "蠻橫的"
            elif top_stat == self.dexterity:
                prefix = "靈敏的"
            elif top_stat == self.stamina:
                prefix = "不滅的"
            elif top_stat == self.mystic:
                prefix = "神秘的"
            self.name = f"{prefix}{self.name}"
            self.drop = random.choice(drops)
        else:
            self.drop = random.choice([*drops, *[False] * 37])
