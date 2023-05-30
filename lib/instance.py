from .guild import Guild
from .monster import Monster, MonsterInfo


class InstanceHandler:
    def __init__(
        self,
        guild: Guild,
        info: MonsterInfo,
    ):
        self.guild_id = guild.id
        self.dungeon_channel = guild.dungeon_channel
        self.monster = Monster(info=info, level=guild.spawn_level)

        if self.monster.elite:
            self.preptime = 90
            self.intro = f"前方感受到了{self.monster.name[0:3]}存在!"
        else:
            self.preptime = 50
            self.intro = "前方通道看起來充滿了危險!"
