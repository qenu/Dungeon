from discord import Colour

from .constant import WORLD_LEVEL_LIMIT


class Guild:
    def __init__(self, *, data: dict = {}):
        # custom
        self.name = data.get("name", "Unknown")
        self.status = data.get("status", "")
        self.colour = Colour(data.get("colour", Colour.blurple().value))
        self.dungeon_channel = data.get("dungeon_channel", 0)

        # guild stats
        self.level = data.get("level", 1)
        self.exp = data.get("exp", 0)

        # guild record
        self.monster_cnt = data.get("monster_cnt", 0)
        self.leaderboard = data.get("leaderboard", {})  # top 10 by level
        self.results = data.get("results", [])  # difficulty adjustment
        self.spawn_level = data.get("spawn_level", 1)

        # guild data
        self.guild_id = data.get("guild_id", 0)
        self.seen = data.get("seen", 0)

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
            "monster_cnt": self.monster_cnt,
            "leaderboard": self.leaderboard,
            "results": self.results,
            "spawn_level": self.spawn_level,
            "seen": self.seen,
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

    def submit_result(self, result: bool) -> None:
        """
        Submit result to record and adjust difficulty

        Parameters
        ----------
        result: bool - True if win, False if lose
        """
        if len(self.results) == 0 or self.results[0] == result:
            self.results.append(result)
        else:
            self.results = [result]

        # Adjust difficulty
        streak = max(len(self.results) - 2, 0) if self.results[0] else len(self.results)
        self.spawn_level = (
            self.spawn_level + streak if self.results[0] else self.spawn_level - streak
        )
        self.spawn_level = min(max(self.spawn_level, 1), (self.level) * 10)
