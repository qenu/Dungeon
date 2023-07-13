# Encoding: UTF-8
import datetime

import discord


def intword(num: int) -> str:
    """Display a number in a more human readable format.

    Args:
        num (int): The number to display.

    Returns:
        str: The human readable number.
    """
    postfix = ["", "K", "M", "B", "T", "Q"]
    fix = 0

    def _intword(num: int) -> str:
        nonlocal fix
        if num >= 1_000:
            fix += 1
            return _intword(num / 1_000)
        try:
            return f"{num:.2f}{postfix[fix]}"
        except IndexError:
            return "∞"

    return _intword(num)


def stamp_footer(self, e: discord.Embed) -> None:
    e.set_footer(text=f"{self.__class__.__name__} version: {self.__version__}")
    e.timestamp = datetime.now()


def get_embed(self, **kwargs) -> discord.Embed:
    e = discord.Embed(**kwargs)
    e.set_author(name=self.bot.user.name, icon_url=self.bot.user.display_avatar.url)
    e.set_footer(text=f"{self.__class__.__name__} version: {self.__version__}")
    e.timestamp = datetime.now()
    return e
