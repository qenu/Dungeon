import random
from dataclasses import dataclass
from typing import Optional

import discord


class Item(Stats):
    def __init__(self, *, data: dict = {}):
        super().__init__(
            str=data.get("str", 0),
            dex=data.get("dex", 0),
            con=data.get("con", 0),
            wis=data.get("wis", 0),
            luk=data.get("luk", 0),
        )
        self.category = data.get("category", "")
        self.level = data.get("level", 1)
        self.name = data.get("name", "")
        self.description = data.get("description", "")
        self.range_adjustment = data.get("range_adjustment", 0)

        self.set = data.get("set", False)  # the name of the legendary boss

        self.reinforced = data.get("reinforced", 0)
        self.reinforce_attempts = data.get("reinforce_attempts", 0)
        reinforced_stats = data.get("reinforced_stats", {})
        self.reinforced_stats = Stats()
        self.reinforced_stats.str = reinforced_stats.get("str", 0)
        self.reinforced_stats.dex = reinforced_stats.get("dex", 0)
        self.reinforced_stats.con = reinforced_stats.get("con", 0)
        self.reinforced_stats.wis = reinforced_stats.get("wis", 0)

    def __copy__(self) -> "Item":
        return Item(data=self.__dict__())

    def __dict__(self) -> dict:
        return {
            "category": self.category,
            "level": self.level,
            "name": self.name,
            "description": self.description,
            "range_adjustment": self.range_adjustment,
            "str": self.str,
            "dex": self.dex,
            "con": self.con,
            "wis": self.wis,
            "luk": self.luk,
            "set": self.set,
            "reinforced": self.reinforced,
            "reinforce_attempts": self.reinforce_attempts,
            "reinforced_stats": self.reinforced_stats.__dict__(),
        }

    def stats_adjustment(self) -> None:
        self.str = int(self.str * self.level)
        self.dex = int(self.dex * self.level)
        self.con = int(self.con * self.level)
        self.wis = int(self.wis * self.level)
        self.luk = int(self.luk * self.level)

    def _reinforce_adjustment(self) -> None:
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
        self.reinforced_stats.str = int(self.str * (self.reinforced * rate))
        self.reinforced_stats.dex = int(self.dex * (self.reinforced * rate))
        self.reinforced_stats.con = int(self.con * (self.reinforced * rate))
        self.reinforced_stats.wis = int(self.wis * (self.reinforced * rate))

    def _reinforce(self) -> bool:
        """only accounts for success, drop and destroy, doesn't calculate stats"""
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


class Job:  # read-only
    def __init__(self, *, data: dict = {}):
        self.name = data.get("name", "")
        self.icon = data.get("icon", "")
        self.description = data.get("description", "")

        self.str_mod = data.get("str_mod", 1.0)
        self.dex_mod = data.get("dex_mod", 1.0)
        self.con_mod = data.get("con_mod", 1.0)
        self.wis_mod = data.get("wis_mod", 1.0)

        self.luk_mod = data.get("luk_mod", 1.0)


class Mob:
    def __init__(self, *, data: dict = {}):
        self.name = data.get("name", "")
        self.description = data.get("description", "")

        self.str_mod = data.get("str_mod", 1.0)
        self.dex_mod = data.get("dex_mod", 1.0)
        self.con_mod = data.get("con_mod", 1.0)
        self.wis_mod = data.get("wis_mod", 1.0)

        self.luk_mod = data.get("luk_mod", 1.0)
        self.drop = data.get("drop", [])


class ServerWorld:
    def __init__(self, *, data: dict = {}):
        # custom
        self.name = data.get("name", "Unknown")
        self.status = data.get("status", "")
        self.colour = discord.Colour(data.get("colour", discord.Colour.blurple().value))
        self.adv_channel_id = data.get("adv_channel_id", 0)

        # guild stats
        self.level = data.get("level", 1)
        self.exp = data.get("exp", 0)

        # guild record
        self.killed_bosses = data.get("killed_bosses", 0)
        self.killed_mobs = data.get("killed_mobs", 0)
        self.leaderboard = data.get("leaderboard", {})  # top 10 by level
        self.raidresult = data.get("raidresult", [])  # difficulty adjustment
        self.mob_level = data.get("mob_level", 1)
        self.last_seen = data.get("last_seen", 0)

    def __dict__(self) -> dict:
        """
        Convert server to dict
        """
        return {
            "name": self.name,
            "status": self.status,
            "colour": self.colour.value,
            "adv_channel_id": self.adv_channel_id,
            "level": self.level,
            "exp": self.exp,
            "killed_bosses": self.killed_bosses,
            "killed_mobs": self.killed_mobs,
            "leaderboard": self.leaderboard,
            "raidresult": self.raidresult,
            "mob_level": self.mob_level,
            "last_seen": self.last_seen,
        }

    def exp_required(self, level: int) -> int:
        return round(
            22.069 * pow(level, 7)
            + 42.069 * pow(level, 5)
            + 69.69 * pow(level, 4)
            + 74.8 * pow(level, 3)
            + 97.5 * pow(level, 2)
            + 116.55 * (level)
        )

    def check_levelup(self) -> bool:
        if self.level == WORLD_LEVEL_LIMIT:
            return False
        if self.exp >= self.exp_required(self.level):
            self.level += 1
            self.exp = 0
            return True
        return False

    def add_exp(self, exp: int) -> None:
        self.exp += exp

    def adjust_difficulty(self) -> None:
        streak = len(self.raidresult)
        if self.raidresult[0]:  # is True
            streak = max(streak - 3, 0)
        if self.raidresult[0]:
            self.mob_level += streak
        else:
            self.mob_level -= streak
        self.mob_level = min(max(self.mob_level, 1), (self.level) * 50)

    def raid_result(self, result: bool) -> None:
        if len(self.raidresult) == 0 or self.raidresult[0] == result:
            self.raidresult.append(result)
        else:
            self.raidresult = [result]
        self.adjust_difficulty()


class RaidHandler:
    def __init__(
        self,
        interaction: discord.Interaction,
        mob_level: int,
        mob_object: Mob,
    ):
        self.guild_id = interaction.guild.id
        self.channel_id = interaction.channel.id
        self.is_elite = False
        self.mob = self.generate_mob(mob_level)
        self.preptime = 50
        self.hint = "前方通道看起來充滿了危險!"
        self.mob_name = mob_object.name
        self.mob_description = mob_object.description
        self.mob.str_mod = mob_object.str_mod
        self.mob.dex_mod = mob_object.dex_mod
        self.mob.con_mod = mob_object.con_mod
        self.mob.wis_mod = mob_object.wis_mod
        self.mob.luk_mod = mob_object.luk_mod
        self.mob.range_adjustment = 85

        if self.make_elite():
            self.mob_drop = random.choice(mob_object.drop)
        else:
            self.mob_drop = random.choice([*mob_object.drop, *[False] * 37])

    def generate_mob(self, level: int) -> Character:
        mob = Character()
        mob.level = level
        base_stats = int(level * (0.75 * int(level / 10)))
        stats = [base_stats] * 4
        for _ in range(level):
            idx = random.randrange(len(stats))
            stats[idx] += 1
        if random.random() < 0.1:
            self.is_elite = True
            idx = random.randrange(len(stats))
            stats[idx] = int(stats[idx] * 1.2)
        mob.stats.str = stats[0]
        mob.stats.dex = stats[1]
        mob.stats.con = stats[2]
        mob.stats.wis = stats[3]
        return mob

    def make_elite(self):
        if not self.is_elite:
            return
        highstat = max(
            self.mob.strength,
            self.mob.dexterity,
            self.mob.constitution,
            self.mob.wisdom,
        )
        if highstat == self.mob.strength:
            prefix = "強大的"
        elif highstat == self.mob.dexterity:
            prefix = "銳利的"
        elif highstat == self.mob.constitution:
            prefix = "強壯的"
        elif highstat == self.mob.wisdom:
            prefix = "睿智的"
        self.preptime = 90
        self.mob.level += 10
        self.mob_name = prefix + self.mob_name
        self.hint = f"前方感受到了{prefix}存在!"
        return True


class CrusadeHandler:
    def __init__(
        self,
        interaction: discord.Interaction,
        mob_level: int,
        mob_object: Mob,
    ):
        self.crusade_commander = interaction.user.id
        self.guild_id = interaction.guild.id
        self.channel_id = interaction.channel.id
        self.is_elite = False
        self.mob = self.generate_mob(mob_level)
        self.preptime = 3600
        self.mob_name = mob_object.name
        self.mob_description = mob_object.description
        self.mob.str_mod = mob_object.str_mod
        self.mob.dex_mod = mob_object.dex_mod
        self.mob.con_mod = mob_object.con_mod
        self.mob.wis_mod = mob_object.wis_mod
        self.mob.luk_mod = mob_object.luk_mod
        self.mob.range_adjustment = 80
        self.hint = "冒險者們即將組隊前往遠方挑戰世界首領，請注意挑戰失敗時將有機會失去身上裝備。"

    def generate_mob(self, level: int) -> Character:
        mob = Character()
        mob.level = level
        mob.stats.str = level * 2
        mob.stats.dex = level * 2
        mob.stats.con = level * 2
        mob.stats.wis = level * 2
        return mob
