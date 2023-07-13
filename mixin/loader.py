import pathlib

import orjson
from loguru import logger as log

from ..lib import Item, Job, MonsterInfo

datapath = pathlib.Path(__file__).parent.parent.resolve() / "data"


class DungeonLoaderMixin:
    def load_dungeon(self) -> None:
        """Load dungeon."""
        # self.load_job()
        self.load_item()
        self.load_monsterinfo()
        # self.load_legend()
        # self.load_legendary()
        log.info("Finished loading dungeon data.")

    # system functions
    # def load_job(self) -> None:
    #     """Load jobs."""
    #     self.job = {}
    #     with open(rf"{datapath}/job.json", "r", encoding="utf-8") as f:
    #         jobs_data: dict = orjson.loads(f.read())
    #     for name in jobs_data.keys():
    #         self.job[name] = Job(data=jobs_data[name])
    #     log.info("Loaded {} jobs.", len(self.job))

    def load_item(self) -> None:
        """Load items."""
        self.item = {}
        with open(rf"{datapath}/item.json", "r", encoding="utf-8") as f:
            items_data: dict = orjson.loads(f.read())
        for name in items_data.keys():
            self.item[name] = Item(data=items_data[name])
        log.info("Loaded {} items.", len(self.item))

    def load_monsterinfo(self) -> None:
        """Load monsterinfo."""
        self.mob = {}
        with open(rf"{datapath}/monster.json", "r", encoding="utf-8") as f:
            mobs_data: dict = orjson.loads(f.read())
        for name in mobs_data.keys():
            self.mob[name] = MonsterInfo(data=mobs_data[name])
        log.info("Loaded {} monsters.", len(self.mob))

    # def load_legend(self) -> None:
    #     """Load legend."""
    #     self.legend = {}
    #     with open(rf"{datapath}/legend.json", "r", encoding="utf-8") as f:
    #         legend_data: dict = orjson.loads(f.read())
    #     for name in legend_data.keys():
    #         self.legend[name] = MonsterInfo(data=legend_data[name])
    #     log.info("Loaded {} legends.", len(self.legend))

    # def load_legendary(self) -> None:
    #     """Load legendary."""
    #     self.legendary = {}
    #     with open(rf"{datapath}/legendary.json", "r", encoding="utf-8") as f:
    #         legendary_data: dict = orjson.loads(f.read())
    #     for name in legendary_data.keys():
    #         self.legendary[name] = Item(data=legendary_data[name])
    #     log.info("Loaded {} legendaries.", len(self.legendary))
