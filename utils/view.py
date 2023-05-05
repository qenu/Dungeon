import random
import time

import discord
from discord import SelectOption
from loguru import logger as log


class info_base_view(discord.ui.View):
    def __init__(self, author: discord.User):
        self.value: str = ""
        self.author = author
        super().__init__(timeout=30)

    @discord.ui.select(
        placeholder="基本資訊",
        options=[
            SelectOption(
                label="角色屬性&討伐紀錄", description="玩家角色屬性以及紀錄", value="statsrecord"
            ),
            SelectOption(label="角色裝備欄位", description="目前所配戴的裝備欄位", value="equipments"),
        ],
    )
    async def dropdown(
        self, interaction: discord.Interaction, item: discord.ui.Item
    ) -> None:
        await interaction.response.defer()
        self.value = item.values[0]
        self.stop()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.author.id:
            return True
        await interaction.response.send_message("你沒有權限操作這個介面。", ephemeral=True)
        return False

    async def on_error(
        self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item
    ) -> None:
        log.error(f"{error}")


class equip_view(discord.ui.View):
    def __init__(self, author: discord.User):
        super().__init__(timeout=30)
        self.value: str = ""
        self.author = author

    @discord.ui.button(label="<< 返回角色資料 ", row=1)
    async def ret(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.value = "ret"
        self.stop()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.author.id:
            return True
        await interaction.response.send_message("你沒有權限操作這個介面。", ephemeral=True)
        return False


class stats_view(discord.ui.View):
    def __init__(self, author: discord.User, remain: int):
        super().__init__(timeout=30)
        self.value: str = ""
        self.author = author
        self.add_str.disabled = not bool(remain)
        self.add_dex.disabled = not bool(remain)
        self.add_con.disabled = not bool(remain)
        self.add_wis.disabled = not bool(remain)

    @discord.ui.button(label="力量+1", row=0, style=discord.ButtonStyle.blurple)
    async def add_str(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()
        self.value = "str"
        self.stop()

    @discord.ui.button(label="敏捷+1", row=0, style=discord.ButtonStyle.blurple)
    async def add_dex(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()
        self.value = "dex"
        self.stop()

    @discord.ui.button(label="體質+1", row=0, style=discord.ButtonStyle.blurple)
    async def add_con(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()
        self.value = "con"
        self.stop()

    @discord.ui.button(label="智慧+1", row=0, style=discord.ButtonStyle.blurple)
    async def add_wis(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()
        self.value = "wis"
        self.stop()

    @discord.ui.button(label="<< 返回角色資料 ", row=1)
    async def ret(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.value = "ret"
        self.stop()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.author.id:
            return True
        await interaction.response.send_message("你沒有權限操作這個介面。", ephemeral=True)
        return False


class inventory_dropdown(discord.ui.Select):
    def __init__(self, embeds: dict):
        self.embeds = embeds
        self.selection = str(list(embeds.keys())[0])
        super().__init__(
            placeholder="物品欄",
            options=[
                SelectOption(
                    label=f"{v.title}",
                    description=f"{v.description}",
                    value=f"{k}",
                )
                for k, v in self.embeds.items()
            ],
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.view.selection = self.values[0]
        await interaction.message.edit(
            embed=self.embeds[self.view.selection], view=self.view
        )


class inventory_view(discord.ui.View):
    def __init__(self, author: discord.User, embeds: dict):
        super().__init__(timeout=60)
        self.value: str = ""
        self.author = author
        self.embeds = embeds
        self.selection = str(list(embeds.keys())[0])
        self.dropdown = self.add_item(inventory_dropdown(self.embeds))

    @discord.ui.button(label="裝備/解除", row=1, style=discord.ButtonStyle.blurple)
    async def equip(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.value = "equip"
        self.stop()

    @discord.ui.button(label="🗑️", row=1, style=discord.ButtonStyle.red)
    async def drop(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.value = "drop"
        self.stop()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.author.id:
            return True
        await interaction.response.send_message("你沒有權限操作這個介面。", ephemeral=True)
        return False


class leaderboard_view(discord.ui.View):
    def __init__(self, author: discord.User, embeds: list):
        super().__init__(timeout=60)
        self.author = author
        self.embeds = embeds
        self.index = 0

    @discord.ui.button(label="◀️", row=0, style=discord.ButtonStyle.blurple)
    async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.index = max(self.index - 1, 0)
        await interaction.message.edit(embed=self.embeds[self.index], view=self)

    @discord.ui.button(label="❌", row=0, style=discord.ButtonStyle.red)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.stop()
        self.index = "close"

    @discord.ui.button(label="▶️", row=0, style=discord.ButtonStyle.blurple)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.index = min(self.index + 1, len(self.embeds) - 1)
        await interaction.message.edit(embed=self.embeds[self.index], view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.author.id:
            return True
        await interaction.response.send_message("你沒有權限操作這個介面。", ephemeral=True)
        return False


class react_chest(discord.ui.View):
    def __init__(self, bot, item, world_level):
        super().__init__()
        self.redeemed = []
        self.bot = bot
        self.item: dict = item
        self.level_limit = world_level * 10

    @discord.ui.button(label="領取寶箱", style=discord.ButtonStyle.blurple)
    async def redeem(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.redeemed.append(interaction.user.id)
        c = self.bot.get_cog("Dungeon")
        item = random.choice(list(self.item.values()))
        player = await c.get_player(interaction.user)
        item = c.create_item(item, min(player.level, self.level_limit))
        await c.give_item(interaction.user, item)
        await interaction.response.send_message(
            f"領取成功，你獲得了{item.name}！", ephemeral=True
        )

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id in self.redeemed:
            await interaction.response.send_message("你已經領過了。", ephemeral=True)
            return False
        else:
            return True


class job_advancement(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.value = None

    @discord.ui.button(label="聖騎士", style=discord.ButtonStyle.blurple)
    async def paladin(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()
        self.value = "paladin"
        self.stop()

    @discord.ui.button(label="狂戰士", style=discord.ButtonStyle.blurple)
    async def berserker(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()
        self.value = "berserker"
        self.stop()

    @discord.ui.button(label="掠奪者", style=discord.ButtonStyle.blurple)
    async def rogue(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.value = "rogue"
        self.stop()

    @discord.ui.button(label="魔導師", style=discord.ButtonStyle.blurple)
    async def wizard(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.value = "wizard"
        self.stop()

    @discord.ui.button(label="神職者", style=discord.ButtonStyle.blurple)
    async def bishop(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.value = "bishop"
        self.stop()


class raid_init_view(discord.ui.View):
    def __init__(self, bot, preptime: int):
        self.bot = bot
        self.value: set = set()
        self.start_time = int(time.time() + preptime)
        super().__init__(timeout=preptime)

    def update_label(self):
        self.join_count.label = f"討伐人數: {len(self.value)}"

    @discord.ui.button(label="討伐人數: 0", style=discord.ButtonStyle.grey, disabled=True)
    async def join_count(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        pass

    @discord.ui.button(label="參加", style=discord.ButtonStyle.green)
    async def join_raid(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()
        cog = self.bot.get_cog("Dungeon")
        if interaction.user.id in cog.char_raid_lock.keys():
            if cog.char_raid_lock[interaction.user.id][0] == interaction.channel_id:
                await interaction.followup.send("你已經參加了討伐。", ephemeral=True)
            else:
                await interaction.followup.send(
                    "你正在戰鬥中，無法重複參加討伐\n討伐位置:"
                    f" <#{cog.char_raid_lock[interaction.user.id][0]}>",
                    ephemeral=True,
                )
            message: discord.Message = interaction.message
            bucket = self.bot.spam_control.get_bucket(message)
            current = message.created_at.timestamp()
            retry_after = bucket.update_rate_limit(current)
            author_id = message.author.id
            if retry_after and author_id != self.bot.owner_id:
                self.bot._auto_spam_count[author_id] += 1
                if self.bot._auto_spam_count[author_id] >= 5:
                    await self.bot.add_to_blacklist(author_id)
                    del self.bot._auto_spam_count[author_id]
                    await self.bot.log_spammer(
                        None, message, retry_after, autoblock=True
                    )
                else:
                    self.bot.log_spammer(None, message, retry_after)
            else:
                self.bot._auto_spam_count.pop(author_id, None)
            return
        else:
            cog.char_raid_lock[interaction.user.id] = [
                interaction.channel_id,
                self.start_time,
            ]
            await interaction.followup.send("成功參加討伐！", ephemeral=True)
        self.value.add(str(interaction.user.id))
        self.update_label()
        await interaction.edit_original_response(view=self)


class captcha(discord.ui.Modal):
    def __init__(self):
        super().__init__()
