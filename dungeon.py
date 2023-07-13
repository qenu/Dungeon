import copy
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Union

import discord
from discord.ext import commands
from loguru import logger as log

from maki.cogs.utils.config import Config
from maki.core.bot import Maki

from .lib import FIBONACCI, LEGENDARY_SETS, Guild, Item, Job, Player
from .mixin import _DungeonMixin
from .utils import equip_view, intword, inventory_view, stamp_footer, stats_view


class Dungeon(commands.Cog, _DungeonMixin):
    __version__ = "3.4.alpha_0.1"

    def __init__(self, bot):
        self.bot: Maki = bot
        self._lockdown = False  # stops new instances from being created
        self.user_data = Config("dungeon_users.json", loop=bot.loop)
        self.user_inventory = Config("dungeon_inventory.json", loop=bot.loop)
        self.world_data = Config("dungeon_guild.json", loop=bot.loop)
        self.occupied_guild = {}  # type: dict[int, list(discord.TextChannel.id, int)]
        # self.char_raid_lock = {}  # type: dict[int, list(discord.TextChannel.id, int)]
        self.load_dungeon()
        # self.auto_check.start()

        # load context menu
        # self.ctx_menu = discord.app_commands.ContextMenu(
        #     name="角色資訊",
        #     callback=self.checkusercontext,
        # )
        # self.bot.tree.add_command(self.ctx_menu)

    async def cog_unload(self):
        self.auto_check.cancel()
        await super().cog_unload()

    # @tasks.loop(minutes=10)
    # async def auto_check(self) -> None:
    #     """Auto check."""
    #     log.info("Checking for unremoved locks.")
    #     removal_list = []
    #     for k, v in self.world_raid_lock.items():
    #         if v[1] <= time.time() - 180:
    #             removal_list.append(k)
    #     if removal_list:
    #         log.info("Removed %d world raid locks.", len(removal_list))
    #         for k in removal_list:
    #             self.world_raid_lock.pop(k)
    #     removal_list = []
    #     for k, v in self.char_raid_lock.items():
    #         if v[1] <= time.time() - 180:
    #             removal_list.append(k)
    #     if removal_list:
    #         log.info("Removed %d user raid locks.", len(removal_list))
    #         for k in removal_list:
    #             self.char_raid_lock.pop(k)

    # command functions
    def fib_index(self, n: int) -> int:
        for i, v in enumerate(FIBONACCI):
            if v > n:
                return max(i, 1)
        return len(FIBONACCI)

    # def stamp_footer(self, e: discord.Embed) -> None:
    #     e.set_footer(text=f"{self.__class__.__name__} version: {self.__version__}")
    #     e.timestamp = datetime.now()

    # def get_embed(self, **kwargs) -> discord.Embed:
    #     e = discord.Embed(**kwargs)
    #     e.set_author(name=self.bot.user.name, icon_url=self.bot.user.display_avatar.url)
    #     e.set_footer(text=f"{self.__class__.__name__} version: {self.__version__}")
    #     e.timestamp = datetime.now()
    #     return e

    # async def character_view(self, interaction: discord.Interaction) -> None:
    #     """Display character sheet."""
    #     base: discord.ui.View = info_view(interaction.user)
    #     user_sheet = await self.user_sheet(interaction.user)
    #     try:
    #         await interaction.response.send_message(embed=user_sheet, view=base)
    #     except discord.errors.InteractionResponded:
    #         await interaction.edit_original_response(embed=user_sheet, view=base)
    #     except Exception as e:
    #         log.error(e)

    #     result = await base.wait()

    #     if base.value == "statsrecord":
    #         await self.statsrec_view(
    #             interaction, await self.user_statsrecord(interaction.user)
    #         )
    #     elif base.value == "equipments":
    #         await self.equipment_view(
    #             interaction, await self.user_equipments(interaction.user)
    #         )
    #     elif isinstance(result, bool):
    #         await interaction.edit_original_response(embed=user_sheet, view=None)

    async def statsrec_view(
        self, interaction: discord.Interaction, embed: discord.Embed
    ) -> None:
        """Send stat view."""
        player = await self.get_user(interaction.user)
        sub_view = stats_view(interaction.user, player.remain_stats)

        await interaction.edit_original_response(embed=embed, view=sub_view)
        result = await sub_view.wait()
        if sub_view.value == "ret":
            return await self.send_base_view(interaction)
        elif sub_view.value == "str":
            player.stats.str += 1
            player.remain_stats -= 1
        elif sub_view.value == "dex":
            player.stats.dex += 1
            player.remain_stats -= 1
        elif sub_view.value == "con":
            player.stats.con += 1
            player.remain_stats -= 1
        elif sub_view.value == "wis":
            player.stats.wis += 1
            player.remain_stats -= 1
        elif isinstance(result, bool):
            return await interaction.edit_original_response(embed=embed, view=None)

        await self.set_user(interaction.user, player)
        await self.statsrec_view(
            interaction, await self.user_statsrecord(interaction.user)
        )

    async def equipment_view(
        self, interaction: discord.Interaction, embed: discord.Embed
    ) -> None:
        """Send equip view."""
        sub_view = equip_view(interaction.user)
        await interaction.edit_original_response(embed=embed, view=sub_view)
        result = await sub_view.wait()
        if sub_view.value == "ret":
            await self.send_base_view(interaction)
        elif isinstance(result, bool):
            await interaction.edit_original_response(embed=embed, view=None)

    def int2Roman(self, num: int):
        values = [1000, 900, 500, 400, 100, 90, 50, 40, 10, 9, 5, 4, 1]
        numerals = [
            "M",
            "CM",
            "D",
            "CD",
            "C",
            "XC",
            "L",
            "XL",
            "X",
            "IX",
            "V",
            "IV",
            "I",
        ]
        result, i = "", 0
        while num:
            result += (num // values[i]) * numerals[i]
            num %= values[i]
            i += 1
        return result

    async def build_inventory_embeds(
        self, interaction: discord.Interaction
    ) -> Dict[str, discord.Embed]:
        player = await self.get_user(interaction.user)
        player_inventory: List = player.inventory
        inventory_embed = {}
        missing_items = []
        for it, item_id in enumerate(player_inventory, start=1):
            item: Item = self.get_user_item(interaction.user, item_id)
            if item is None:
                missing_items.append(item_id)
                continue
            t = item.name
            if item.reinforced:
                t += f" {self.int2Roman(item.reinforced)}"

            if item_id in [
                player.head,
                player.necklace,
                player.body,
                player.pants,
                player.gloves,
                player.boots,
                player.weapon,
                player.ring,
            ]:
                t += " (已裝備)"

            e = discord.Embed(
                title=t, description=item.description, colour=player.colour
            )
            e.set_author(name=f"物品欄 ({it}/{len(player_inventory)})")
            category_text = ""
            if item.category == "head":
                category_text = "頭部"
            elif item.category == "necklace":
                category_text = "項鍊"
            elif item.category == "body":
                category_text = "上衣"
            elif item.category == "pants":
                category_text = "褲子"
            elif item.category == "gloves":
                category_text = "手套"
            elif item.category == "boots":
                category_text = "靴子"
            elif item.category == "weapon":
                category_text = "武器"
            elif item.category == "ring":
                category_text = "戒指"
            e.add_field(
                name="裝備類別",
                value=category_text,
                inline=True,
            )
            if item.reinforced:
                stars = ""
                rein = item.reinforced
                stars += ":sparkles:" * int(rein / 10)
                rein = rein % 10
                stars += ":star2:" * int(rein / 5)
                rein = rein % 5
                stars += ":star:" * rein
                e.add_field(
                    name="強化等級",
                    value=stars,
                    inline=True,
                )
            itemstats = [
                (
                    (
                        f"蠻力 {item.vit:+}"
                        + (
                            f"({item.reinforced_stats.vit:+})\n"
                            if item.reinforced
                            else "\n"
                        )
                    )
                    if item.vit
                    else ""
                ),
                (
                    (
                        f"技巧 {item.dex:+}"
                        + (
                            f"({item.reinforced_stats.dex:+})\n"
                            if item.reinforced
                            else "\n"
                        )
                    )
                    if item.dex
                    else ""
                ),
                (
                    (
                        f"體質 {item.sta:+}"
                        + (
                            f"({item.reinforced_stats.sta:+})\n"
                            if item.reinforced
                            else "\n"
                        )
                    )
                    if item.sta
                    else ""
                ),
                (
                    (
                        f"神秘 {item.mys:+}"
                        + (
                            f"({item.reinforced_stats.mys:+})\n"
                            if item.reinforced
                            else "\n"
                        )
                    )
                    if item.mys
                    else ""
                ),
                f"幸運 {item.luk:+}\n" if item.luk else "",
            ]
            itemstats = "".join(itemstats)
            e.add_field(
                name="屬性加成",
                value="無" if len(itemstats) == 0 else itemstats,
                inline=False,
            )
            e.set_footer(
                text=(
                    "物品代碼:"
                    f" {item_id}{(f'{chr(10)}包含碎片: {item.reinforce_attempts}') if item.reinforced else ''}"
                )
            )
            inventory_embed[item_id] = e
        # fuck this shit
        if len(missing_items) > 0:
            for item_id in missing_items:
                player_inventory.remove(item_id)
            await self.set_user(interaction.user, player)
        return inventory_embed

    async def inven_view(
        self,
        interaction: discord.Interaction,
        embeds: Dict[str, discord.Embed],
    ):
        """Send inventory view."""
        if len(embeds) == 0:
            await interaction.edit_original_response(
                embed=discord.Embed(
                    description="你的物品欄是空的", color=discord.Color.red()
                ),
                view=None,
            )
            return
        view = inventory_view(interaction.user, embeds)
        await interaction.edit_original_response(
            embed=embeds[list(embeds.keys())[0]], view=view
        )
        result = await view.wait()
        if view.value == "equip":
            player = await self.get_user(interaction.user)
            if self.in_player_equips(player, view.selection):
                await self.unequip_item(interaction.user, view.selection)
            else:
                await self.equip_item(interaction.user, view.selection)

        elif view.value == "drop":
            result = await self.remove_item(interaction.user, view.selection)
            if not result:
                await interaction.followup.send(
                    embed=discord.Embed(
                        description="裝備中的物品無法丟棄", color=discord.Color.red()
                    ),
                    ephemeral=True,
                )

        elif isinstance(result, bool):
            return await interaction.edit_original_response(
                embed=embeds[view.selection], view=None
            )
        inventory_embeds = await self.build_inventory_embeds(interaction)
        await self.inven_view(interaction, inventory_embeds)

    def create_item(self, item_ptr: Item, item_level: int = 1) -> Item:
        """Create item."""
        item = item_ptr.__copy__()
        item.level = item_level
        item.name = f"Lv. {item.level} {item.name}"
        item.stats_adjustment()
        return item

    # player related functions
    def get_user_item(self, user_id: int, item_id: str) -> Optional[Item]:
        """Get specific user item."""
        inventory = self.user_inventory.get(user_id, None)
        if not inventory:
            log.info(f"Inventory missing. user_id: {user_id} | item: {item_id}")
            return None
        item = inventory.get(item_id, None)
        if not item:
            log.info(f"Item missing, user_id: {user_id} | item: {item_id}")
            return None
        return Item(data=item)

    async def reinforce_item(
        self, user: discord.User, item_id: str, rigged=False
    ) -> bool:
        """Reinforce item."""
        item = self.get_user_item(user, item_id)
        user_inventory: dict = self.user_inventory.get(user.id, None)

        player: Player = await self.get_user(user)
        player.soulshard -= 1
        result = item._reinforce()
        if result is None and not rigged:
            for parts in [
                player.head,
                player.necklace,
                player.body,
                player.pants,
                player.gloves,
                player.boots,
                player.weapon,
                player.ring,
            ]:
                if parts == item_id:
                    parts = ""
                    break
            player.inventory.remove(item_id)
            user_inventory.pop(item_id, None)
            if item.set in LEGENDARY_SETS:
                player.soulshard += item.reinforce_attempts
                player.soulshard += 210
            else:
                player.soulshard += item.reinforce_attempts
        else:
            item._reinforce_adjustment()
            user_inventory.update({item_id: item.__dict__()})

        await self.user_inventory.put(user.id, user_inventory)
        await self.set_user(user, player)
        await self.reload_equip_stats(user)
        return result

    async def give_item(self, user_id: int, item: Item) -> Union[bool, str]:
        """Give an item to a player."""
        item_id = str(uuid.uuid4())

        user_inventory: dict = self.user_inventory.get(user_id, {})
        user_data: dict = self.user_data.get(user_id, None)

        if len(user_inventory) >= user_data["allowed_inventory"]:
            return False

        user_inventory[item_id] = copy.copy(item.__dict__())
        await self.user_inventory.put(user_id, user_inventory)

        user_data["inventory"].append(item_id)
        await self.user_data.put(user_id, user_data)

        return item_id

    async def give_legendary_item(
        self, user: discord.User, item_name: str, reinforce: int = 0
    ) -> Union[bool, str]:
        """Give a legendary item to a player."""
        item_id = str(uuid.uuid4())

        user_inventory = self.user_inventory.get(user.id, {})
        user_data: dict = self.user_data.get(user.id, None)

        if len(user_inventory) >= user_data["allowed_inventory"]:
            return False

        item: Item = self.legendary[item_name].__copy__()
        item.name = f"Lv. {item.level} {item.name}"
        item.reinforced = reinforce
        item._reinforce_adjustment()
        user_inventory[item_id] = copy.copy(item.__dict__())
        await self.user_inventory.put(user.id, user_inventory)

        user_data["inventory"].append(item_id)
        await self.user_data.put(user.id, user_data)

        return item_id

    async def set_job(self, user: discord.User, job_name: str) -> Union[bool, str]:
        """Set a player's job."""
        player: Player = await self.get_user(user)
        job: Job = self.job[job_name]
        if not job:
            return False
        player.job = job_name
        player.str_mod = job.str_mod
        player.dex_mod = job.dex_mod
        player.con_mod = job.con_mod
        player.wis_mod = job.wis_mod
        player.luk_mod = job.luk_mod
        await self.set_user(user, player)
        return job.name

    async def base_player(self) -> Player:
        data: Player = Player()
        data.seen = int(datetime.timestamp(datetime.now()))
        return data

    async def get_user(self, user_id: int, create: bool = True) -> Player:
        """Retrieve a user's data.

        Attributes
        ----------
        - user_id: :class:`int`
            The user id to retrieve the player data for.

        - create: :class:`bool`
            Whether to create a new player if one doesn't exist.`(Default: True)`

        Returns
        -------
        :class:`Player`
            The player object.
        """
        data: dict = self.user_data.get(user_id, None)
        if data is not None:
            return Player(data=data)

        if not create:
            return Player()

        # Create a new player in the database.
        player: Player = Player()
        await self.p_set(user_id, player)
        item = self.create_item(self.item["wood_stick"], 1)
        item_id = await self.give_item(user_id, item)
        await self.equip_item(user_id, item_id)
        data: dict = self.user_data.get(user_id, None)
        return Player(data=data)

    async def set_user(self, user_id: int, player: Player) -> None:
        """Save a user's data.

        Attributes
        ----------
        - user_id: :class:`int`
            The user id to save the player data for.
        - player: :class:`Player`
            The player object to save.
        """
        await self.user_data.put(user_id, player.__dict__())

    async def user_sheet(self, user: discord.User) -> discord.Embed:
        """Get player infosheet in embed."""
        player = await self.get_user(user, False)
        exp = player.exp
        required = player.exp_required(player.level)
        # job = self.job[player.job]
        e = discord.Embed(
            title=f"{user.display_name}",
            description=player.status,
            colour=player.colour,
        )
        e.set_author(name="角色資訊")
        e.add_field(
            name="\a",
            value=(
                f"物品欄空間: {len(player.inventory)}/{player.allowed_inventory}\n"
                f"```fix\n生命數值: {player.health:>20,}\n"
                f"物理傷害:{f'{player._physical_base_damage:,}~{player._physical_max_damage:,}':>20}\n"
                f"魔法傷害:{f'{player._magical_base_damage:,}~{player._magical_max_damage:,}':>20}\n```"
            ),
            inline=False,
        )
        e.add_field(
            name="• 屬性 " + "-" * 40,
            value=(
                "```fix\n"
                f"蠻力: {player.vitality:>20,}\n"
                f"技巧: {player.dexerity:>20,}\n"
                f"體質: {player.stamina:>20,}\n"
                f"神秘: {player.mystic:>20,}\n"
                "------------------------\n"
                f"命中: {player.accuracy:>20,}\n"
                f"速度: {player.speed:>20,}\n"
                f"回復: {player.regen:>20,}\n"
                "```"
            ),
            inline=False,
        )
        # e.add_field(
        #     name="• 職業 " + "-" * 12,
        #     value=f"```fix\n{job.name}```",
        #     inline=True,
        # )
        e.add_field(
            name="• 等級 " + "-" * 12,
            value=f"```st\nLv. {player.level}\n```",
            inline=True,
        )

        prc_str = f"{(exp/required*100):,.2f}%"
        exp_str = f"{intword(exp)} / {intword(required)}"
        e.add_field(
            name="• 經驗 " + "-" * 40,
            value=f"```fix\n百分比: {prc_str:>20}\n經驗值: {exp_str:>20}\n```",
            inline=False,
        )
        if player.blessing:
            blessings = "\n".join(player.blessing)
            e.add_field(
                name="• 祝福 " + "-" * 40,
                value=f"```fix\n{blessings}\n```",
                inline=False,
            )
        if (
            player.remain_stats
            or int(player.chest / 20) > 0
            or len(player.legendary_chest) > 0
            or player.soulshard > 0
        ):
            content_str = ""
            if player.remain_stats:
                content_str += f"剩餘點數: {intword(player.remain_stats):>20,}\n"
            if int(player.chest / 20) > 0:
                content_str += f"補給木箱: {intword(int(player.chest/20)):>20,}\n"
            if player.soulshard > 0:
                content_str += f"靈魂碎片: {intword(player.soulshard):>20,}\n"
            e.add_field(
                name="• 提醒 " + "-" * 40,
                value=f"```fix\n{content_str}\n```",
                inline=False,
            )
        stamp_footer(e)
        return e

    async def user_statsrecord(self, user: discord.User) -> discord.Embed:
        """Get player stats and raid record"""
        player: Player = await self.get_user(user)
        e = discord.Embed(
            title=f"{user.name}#{user.discriminator}",
            description=f"**剩餘點數: {player.remain_stats:,}**",
            colour=player.colour,
        )
        e.set_author(name="角色屬性&討伐紀錄")
        e.add_field(
            name="• 角色屬性",
            value=(
                "```st\n蠻力:"
                f" {player._vitality:>5,}{'' if not any([player.equip_stats.vit]) else f'({player.vit:,}{player.equip_stats.str:+,})'}\n技巧:"
                f" {player._dexterity:>5,}{'' if not any([player.equip_stats.dex]) else f'({player.dex:,}{player.equip_stats.dex:+,})'}\n體質:"
                f" {player._stamina:>5,}{'' if not any([player.equip_stats.sta]) else f'({player.sta:,}{player.equip_stats.con:+,})'}\n神秘:"
                f" {player._mystic:>5,}{'' if not any([player.equip_stats.mys]) else f'({player.mys:,}{player.equip_stats.wis:+,})'}\n------------------------\n物理傷害:{f'{player._physical_base_damage:,}~{player._physical_max_damage:,}':>20}\n魔法傷害:{f'{player._magical_base_damage:,}~{player._magical_max_damage:,}':>20}\n```命中:"
                f" {player.accuracy:>20,}\n回復: {player.regen:>20,}\n速度:"
                f" {player.speed:>20,}\n```"
            ),
            inline=False,
        )
        e.add_field(
            name="• 討伐紀錄",
            value=(
                "```st\n"
                f"討伐怪物: {player.monster_cnt:,}\n"
                f"最高輸出: {player.max_dmg:,}\n"
                f"總輸出: {player.cum_dmg:,}\n"
                "```"
            ),
            inline=False,
        )
        stamp_footer(e)
        return e

    async def user_equipments(self, user: discord.User) -> discord.Embed:
        """Get player raid record."""
        player: Player = await self.get_user(user)
        e = discord.Embed(
            title=f"{user.name}#{user.discriminator}",
            description=player.status,
            colour=player.colour,
        )
        e.set_author(name="角色配戴裝備欄位")
        if player.head:
            item = self.get_user_item(user, player.head)
            item_name = f"{item.name} {self.int2Roman(item.reinforced)}"
            e.add_field(
                name="▹ 頭部",
                value="\n".join(["```st", item_name, "```"]),
                inline=False,
            )
        if player.necklace:
            item = self.get_user_item(user, player.necklace)
            item_name = f"{item.name} {self.int2Roman(item.reinforced)}"
            e.add_field(
                name="▹ 項鍊",
                value="\n".join(["```st", item_name, "```"]),
                inline=False,
            )
        if player.body:
            item = self.get_user_item(user, player.body)
            item_name = f"{item.name} {self.int2Roman(item.reinforced)}"
            e.add_field(
                name="▹ 上衣",
                value="\n".join(["```st", item_name, "```"]),
                inline=False,
            )
        if player.pants:
            item = self.get_user_item(user, player.pants)
            item_name = f"{item.name} {self.int2Roman(item.reinforced)}"
            e.add_field(
                name="▹ 褲子",
                value="\n".join(["```st", item_name, "```"]),
                inline=False,
            )
        if player.gloves:
            item = self.get_user_item(user, player.gloves)
            item_name = f"{item.name} {self.int2Roman(item.reinforced)}"
            e.add_field(
                name="▹ 手套",
                value="\n".join(["```st", item_name, "```"]),
                inline=False,
            )
        if player.boots:
            item = self.get_user_item(user, player.boots)
            item_name = f"{item.name} {self.int2Roman(item.reinforced)}"
            e.add_field(
                name="▹ 靴子",
                value="\n".join(["```st", item_name, "```"]),
                inline=False,
            )
        if player.weapon:
            item = self.get_user_item(user, player.weapon)
            item_name = f"{item.name} {self.int2Roman(item.reinforced)}"
            e.add_field(
                name="▹ 武器",
                value="\n".join(["```st", item_name, "```"]),
                inline=False,
            )
        if player.ring:
            item = self.get_user_item(user, player.ring)
            item_name = f"{item.name} {self.int2Roman(item.reinforced)}"
            e.add_field(
                name="▹ 戒指",
                value="\n".join(["```st", item_name, "```"]),
                inline=False,
            )

        stamp_footer(e)
        return e

    async def reload_equip_stats(self, user_id: int):
        """Reload player equipment stats"""
        player: dict = self.user_data.get(user_id, None)
        if not player:
            raise ValueError("Player not found")
        equipped = [
            player["head"],
            player["necklace"],
            player["body"],
            player["pants"],
            player["gloves"],
            player["boots"],
            player["weapon"],
            player["ring"],
        ]
        player["equip_stats"]["str"] = 0
        player["equip_stats"]["dex"] = 0
        player["equip_stats"]["con"] = 0
        player["equip_stats"]["wis"] = 0
        player["equip_stats"]["luk"] = 0
        player["range_adjustment"] = 0

        Behemoth = 0
        Leviathan = 0
        Tiamat = 0

        for item_id in equipped:
            if not item_id:
                continue
            item = self.get_user_item(user_id, item_id)
            if item is None:
                continue
            player["equip_stats"]["str"] += item.str
            player["equip_stats"]["str"] += item.reinforced_stats.str
            player["equip_stats"]["dex"] += item.dex
            player["equip_stats"]["dex"] += item.reinforced_stats.dex
            player["equip_stats"]["con"] += item.con
            player["equip_stats"]["con"] += item.reinforced_stats.con
            player["equip_stats"]["wis"] += item.wis
            player["equip_stats"]["wis"] += item.reinforced_stats.wis
            player["equip_stats"]["luk"] += item.luk
            player["range_adjustment"] += item.range_adjustment

            if item.set == "Behemoth":
                Behemoth += 1
            if item.set == "Leviathan":
                Leviathan += 1
            if item.set == "Tiamat":
                Tiamat += 1

        blessing = []
        if Behemoth >= 3:
            player["equip_stats"]["str"] += 200
            player["equip_stats"]["str"] = int(player["equip_stats"]["str"] * 1.6)
            bless = "I"
            if Behemoth >= 6:
                player["equip_stats"]["dex"] += 300
                bless = "II"
                if Behemoth >= 8:
                    player["equip_stats"]["dex"] = int(
                        player["equip_stats"]["dex"] * 2.5
                    )
                    bless = "III"
            blessing.append("貝西摩斯的猖狂 " + bless)
        if Leviathan >= 3:
            player["equip_stats"]["con"] += 200
            player["equip_stats"]["con"] = int(player["equip_stats"]["con"] * 1.1)
            bless = "I"
            if Leviathan >= 6:
                player["equip_stats"]["wis"] += 300
                bless = "II"
                if Leviathan >= 8:
                    player["equip_stats"]["wis"] = int(
                        player["equip_stats"]["wis"] * 2.1
                    )
                    bless = "III"
            blessing.append("利維坦的傲慢 " + bless)
        if Tiamat >= 3:
            player["equip_stats"]["str"] += 200
            player["equip_stats"]["str"] = int(player["equip_stats"]["str"] * 1.9)
            bless = "I"
            if Tiamat >= 6:
                player["equip_stats"]["con"] += 300
                bless = "II"
                if Tiamat >= 8:
                    player["equip_stats"]["con"] = int(
                        player["equip_stats"]["con"] * 1.9
                    )
                    bless = "III"
            blessing.append("提亞馬特的狂妄 " + bless)

        player["blessing"] = blessing

        return await self.user_data.put(user_id, player)

    async def equip_item(self, user_id: int, item_id: str):
        player: dict = self.user_data.get(user_id, None)
        if not player:
            raise ValueError("Player not found")
        if item_id in [
            player["head"],
            player["necklace"],
            player["body"],
            player["pants"],
            player["gloves"],
            player["boots"],
            player["weapon"],
            player["ring"],
        ]:
            return
        item = self.get_user_item(user_id, item_id)
        if item.level > player["level"] + max(player["rebirth"], 10):
            return
        if not item:
            raise ValueError("Item not found")
        if item.category == "head":
            slot = "head"
        elif item.category == "necklace":
            slot = "necklace"
        elif item.category == "body":
            slot = "body"
        elif item.category == "pants":
            slot = "pants"
        elif item.category == "gloves":
            slot = "gloves"
        elif item.category == "boots":
            slot = "boots"
        elif item.category == "weapon":
            slot = "weapon"
        elif item.category == "ring":
            slot = "ring"
        else:
            raise ValueError("Invalid item category")
        player[slot] = item_id
        await self.user_data.put(user_id, player)
        await self.reload_equip_stats(user_id)

    async def unequip_item(self, user: discord.User, item_id: str):
        player: dict = self.user_data.get(user.id, None)
        if not player:
            raise ValueError("Player not found")
        for part in [
            "head",
            "necklace",
            "body",
            "pants",
            "gloves",
            "boots",
            "weapon",
            "ring",
        ]:
            if item_id == player[part]:
                player[part] = ""
                break

        await self.user_data.put(user.id, player)
        await self.reload_equip_stats(user)

    def in_player_equips(self, player: Player, item_id: str):
        return item_id in [
            player.head,
            player.necklace,
            player.body,
            player.pants,
            player.gloves,
            player.boots,
            player.weapon,
            player.ring,
        ]

    async def remove_item(self, user: discord.User, item_id: str) -> bool:
        player: Player = await self.get_user(user)
        if self.in_player_equips(player, item_id):
            return False
        if not player:
            raise ValueError("Player not found")
        item = self.get_user_item(user, item_id)
        if not item:
            raise ValueError("Item not found")
        player.inventory.remove(item_id)
        await self.set_user(user, player)

        user_inventory = self.user_inventory.get(user.id, None)
        user_inventory.pop(item_id, None)
        await self.user_inventory.put(user.id, user_inventory)
        return True

    # world related functions
    async def get_world(self, guild: discord.Guild) -> Guild:
        """Get world from guild."""
        data = self.world_data.get(guild.id, None)
        if data is None:
            data = Guild()
            data.name = guild.name
            await self.set_world(guild, data)
        else:
            data = Guild(data=data)
        return data

    async def set_world(self, guild: discord.Guild, world: Guild) -> None:
        """Set world for guild."""
        await self.world_data.put(guild.id, world.__dict__())

    async def world_info(self, guild: discord.Guild) -> discord.Embed:
        """Get world info."""
        world = await self.get_world(guild)
        e = discord.Embed(
            title=f"{guild.name}",
            description=world.status,
            colour=world.colour,
        )
        e.set_author(name="世界資訊")
        if guild.icon:
            e.set_thumbnail(url=guild.icon.url)
        if guild.premium_subscription_count > 1:
            e.add_field(
                name="• 世界增幅",
                value=(
                    f"```fix\n加成等級: {guild.premium_tier}\n經驗加成:"
                    f" {guild.premium_tier*5}%\n```"
                ),
                inline=False,
            )
        e.add_field(
            name="• 世界等級",
            value=f"```st\nLv. {world.level}```",
            inline=True,
        )
        e.add_field(
            name="• 世界主人",
            value=f"```fix\n{guild.owner.name}#{guild.owner.discriminator}```",
            inline=True,
        )
        e.add_field(
            name="• 世界數據",
            value=(
                "```asciidoc\n"
                f"- 擊殺首領: {world.killed_bosses:>40,}\n"
                f"- 擊殺怪物: {world.killed_mobs:>40,}\n"
                "```"
            ),
            inline=False,
        )
        required = world.exp_required(world.level)
        prc_str = f"{(world.exp/required*100):,.2f}%"
        exp_str = f"{world.exp:,} / {required:,}"
        nxt_str = f"{required - world.exp:,}"
        e.add_field(
            name="• 世界經驗值",
            value=(
                "```asciidoc\n"
                f"- 百分比: {prc_str:>40}\n"
                f"- 經驗值: {exp_str:>40}\n"
                f"- 離升等: {nxt_str:>40}\n"
                "```"
            ),
            inline=False,
        )
        stamp_footer(e)
        return e
