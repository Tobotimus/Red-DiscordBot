import discord
from discord.ext import commands
from .utils.dataIO import dataIO
from .utils import checks
import os
import datetime
import requests
import json
import r6sapi as api

platforms = {
    "xb1":          api.Platforms.XBOX,
    "xone":         api.Platforms.XBOX,
    "xbone":        api.Platforms.XBOX,
    "xbox":         api.Platforms.XBOX,
    "xboxone":      api.Platforms.XBOX,
    "ps":           api.Platforms.PLAYSTATION,
    "ps4":          api.Platforms.PLAYSTATION,
    "playstation":  api.Platforms.PLAYSTATION,
    "uplay":        api.Platforms.UPLAY,
    "pc":           api.Platforms.UPLAY
}

r6db_platforms = {
    api.Platforms.XBOX:         "xbox.",
    api.Platforms.PLAYSTATION:  "ps4.",
    api.Platforms.UPLAY:        ""
}

colours = {
    api.Platforms.XBOX:         discord.colour.Colour.green(),
    api.Platforms.PLAYSTATION:  discord.colour.Colour.magenta(),
    api.Platforms.UPLAY:        discord.colour.Colour.blue()
}

regions = {
    "na":       api.RankedRegions.NA,
    "us":       api.RankedRegions.NA,
    "america":  api.RankedRegions.NA,
    "eu":       api.RankedRegions.EU,
    "europe":   api.RankedRegions.EU,
    "asia":     api.RankedRegions.ASIA,
    "au":       api.RankedRegions.ASIA,
    "anz":      api.RankedRegions.ASIA,
    "oceania":  api.RankedRegions.ASIA
}

region_names = {
    api.RankedRegions.ASIA: "Asia",
    api.RankedRegions.EU:   "EU",
    api.RankedRegions.NA:   "NA"
}

class R6StatsError(Exception):
    pass

class NoCredentials(R6StatsError):
    pass

class InvalidCredentials(R6StatsError):
    pass

class APIError(R6StatsError):
    pass

class R6Stats:
    """Get info on Rainbow Six players from http://r6stats.com"""

    def __init__(self, bot):
        self.bot = bot
        self.path = "data/r6stats/settings.json"
        self.settings = dataIO.load_json(self.path)
        if "email" not in self.settings or "password" not in self.settings:
            self.auth = None
        else:
            self.auth = api.Auth(self.settings["email"], self.settings["password"])
        

    @checks.is_owner()
    @commands.command()
    async def r6auth(self, email, password):
        """Give the bot an Ubisoft account login to request stats."""
        self.settings["email"] = email
        self.settings["password"] = password
        self.auth = api.Auth(email=email, password=password)
        dataIO.save_json(self.path, self.settings)
        await self.bot.say("Settings saved.")

    @commands.group(aliases=["r6s", "stats"], invoke_without_command=True, pass_context=True)
    async def r6stats(self, ctx, username, platform="Uplay"):
        """Overall stats for a particular player.
        
        Example: !r6s Tobotimus xbox"""
        await self.bot.send_typing(ctx.message.channel)
        player = await self.request_player(username, platform)
        if player is not None:
            try:
                await player.check_general()
                await player.check_level()
            except api.InvalidRequest:
                await self.bot.say("There are no stats available for that player.")
                return
            if player.xp is None or player.xp == 0:
                await self.bot.say("There are no stats available for that player.")
                return
            platform = player.platform
            username = player.name
            data = discord.Embed(title=username, description="General stats. Use subcommands for more specific stats.")
            data.timestamp = datetime.datetime.now()
            data.colour = colours.get(platform)
            data.set_thumbnail(url=player.icon_url)
            k_d = "{} - {}\n".format(player.kills, player.deaths) +\
                  "(Ratio: {})".format("{0:.2f}".format(player.kills / player.deaths) if (player.deaths != 0) else "-.--")
            data.add_field(name="Kills - Deaths", value=k_d)
            data.add_field(name="Headshot %", value="{}%".format("{0:.1f}".format(player.headshots/player.kills*100) if (player.kills != 0) else "--.-"))
            data.add_field(name="Wins - Losses", value="{} - {}".format(player.matches_won, player.matches_lost))
            data.add_field(name="Win %", value="{}%".format("{0:.1f}".format(player.matches_won/player.matches_played*100) if (player.matches_played != 0) else "--.-"))
            data.add_field(name="Playtime", value="{0:.1f}H".format(player.time_played / 3600))
            data.add_field(name="Level", value=player.level)
            await self.bot.say(embed=data)

    @r6stats.command(aliases=["rank"], pass_context=True)
    async def ranked(self, ctx, username, platform="Uplay", region="ANZ"):
        """Ranked stats for a particular player.
        
        Example: !r6s rank Tobotimus uplay NA"""
        await self.bot.send_typing(ctx.message.channel)
        region = regions.get(region.lower())
        if region is None: 
            await self.bot.say("Invalid region, please use `eu`, `na`, `asia`.")
            return
        player = await self.request_player(username, platform)
        if player is not None:
            try:
                await player.check_queues()
                await player.check_level()
            except api.InvalidRequest:
                await self.bot.say("There are no stats available for that player.")
                return
            if player.xp is None or player.xp == 0:
                await self.bot.say("There are no stats available for that player.")
                return
            platform = player.platform
            username = player.name
            rank = await player.get_rank(region)
            data = discord.Embed(title=username, description="Ranked stats for {} region".format(region_names.get(region)))
            data.timestamp = datetime.datetime.now()
            data.colour = colours.get(platform)
            if rank.get_bracket() != api.Rank.UNRANKED:
                data.set_thumbnail(url=rank.get_icon_url())
            rank_s = "{}\n".format(rank.rank) +\
                     "(Max: {})".format(api.Rank.RANKS[rank.max_rank])
            data.add_field(name="Rank", value=rank_s)
            mmr = "{}\n".format(int(rank.mmr)) +\
                  "(Max: {})\n".format(int(rank.max_mmr)) +\
                  "(Next Rank: {})\n".format(int(rank.next_rank_mmr)) +\
                  "(Uncertainty: {})".format(int(rank.skill_stdev * 100))
            data.add_field(name="MMR", value=mmr)
            record = "{} - {}\n".format(rank.wins, rank.losses) +\
                     "(Abandons: {})\n".format(rank.abandons) +\
                     "(Win %: {}%)".format("{0:.1f}".format(rank.wins/(rank.losses+rank.wins)*100) if (rank.losses+rank.wins != 0) else "--.-")
            data.add_field(name="Wins - Losses", value=record)
            await self.bot.say(embed=data)

    @r6stats.command(aliases=["other"], pass_context=True)
    async def misc(self, ctx, username, platform="Uplay"):
        """Get Miscellaneous stats, including a hacker rating!
        
        Example: !r6s misc Tobotimus"""
        await self.bot.send_typing(ctx.message.channel)
        player = await self.request_player(username, platform)
        if player is not None:
            try:
                await player.check_general()
                await player.check_level()
            except api.InvalidRequest:
                await self.bot.say("There are no stats available for that player.")
                return
            if player.xp is None or player.xp == 0:
                await self.bot.say("There are no stats available for that player.")
                return
            platform = player.platform
            username = player.name
            data = discord.Embed(title=username, description="Miscellaneous stats.")
            data.timestamp = datetime.datetime.now()
            data.colour = colours.get(platform)
            data.set_thumbnail(url=player.icon_url)
            useful =  "**Assists:** {}\n".format(player.kill_assists) +\
                      "**Revives:** {}\n".format(player.revives) +\
                      "**Reinforcements:** {}".format(player.reinforcements_deployed)
            data.add_field(name="Usefulness", value=useful)
            useless = "**Suicides:** {}\n".format(player.suicides) +\
                      "**Barricades:** {}".format(player.barricades_deployed)
            data.add_field(name="Uselessness", value=useless)
            extras =  "**Gadgets Destroyed:** {}\n".format(player.gadgets_destroyed) +\
                      "**Blind Kills:** {}\n".format(player.blind_kills) +\
                      "**Melee Kills:** {}\n".format(player.melee_kills) +\
                      "**Hotbreaches:** {}".format(player.rappel_breaches)
            data.add_field(name="Extras", value=extras)
            hacker =  "**{}%**\n".format("{0:.1f}".format(player.penetration_kills/player.kills*200) if player.kills != 0 else "--.-") +\
                      "**Penetration Kills:** {}".format(player.penetration_kills)
            data.add_field(name="Hacker Rating", value=hacker)
            await self.bot.say(embed=data)

    @commands.command(pass_context=True, aliases=["r6n", "r6name", "r6aliases"])
    async def r6names(self, ctx, username, platform="Uplay"):
        """Look up a player's aliases on R6DB.
        
        Example: !r6names Tobotimus"""
        await self.bot.send_typing(ctx.message.channel)
        platform = r6db_platforms.get(platforms.get(platform))
        r = requests.Request(url= "https://{}r6db.com/api/v2/players/?name={}&exact=0".format(platform, username))
        

    async def request_player(self, username, platform):
        if self.auth is None:
            await self.bot.say("The owner needs to set the credentials first.\n"
                                "See: `[p]r6auth`")
            return
        platform = platforms.get(platform.lower())
        if platform is None:
            await self.bot.say("Invalid platform specified.")
            return
        player = None
        try:
            player = await self.auth.get_player(username, platform)
        except:
            await self.bot.say("Player not found!")
            return
        if player is None:
            await self.bot.say("Player not found!")
            return
        return player

def check_folders():
    if not os.path.exists("data/r6stats"):
        print("Creating data/r6stats folder...")
        os.makedirs("data/r6stats")


def check_files():
    f = "data/r6stats/settings.json"
    data = {}
    if not dataIO.is_valid_json(f):
        dataIO.save_json(f, data)

def setup(bot):
    check_folders()
    check_files()
    bot.add_cog(R6Stats(bot))