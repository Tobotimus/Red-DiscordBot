import discord
from discord.ext import commands
from .utils.dataIO import dataIO
from .utils import checks
import os
import datetime
import requests
import json
import r6sapi as api

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
        self.platforms = {
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
        self.colours = {
            api.Platforms.XBOX:             discord.colour.Colour.green(),
            api.Platforms.PLAYSTATION:      discord.colour.Colour.magenta(),
            api.Platforms.UPLAY:            discord.colour.Colour.blue()
        }

    @checks.is_owner()
    @commands.command()
    async def r6auth(self, email, password):
        """Give the bot an Ubisoft account login to request stats."""
        self.settings["email"] = email
        self.settings["password"] = password
        self.auth = api.Auth(email=email, password=password)
        dataIO.save_json(self.path, self.settings)
        await self.bot.say("Settings saved.")

    @commands.group(invoke_without_command=True)
    async def r6stats(self, username, platform="Uplay"):
        if self.auth is None:
            await self.bot.say("The owner needs to set the credentials first.\n"
                                                 "See: `[p]r6auth`")
            return
        platform = self.platforms.get(platform.lower())
        if platform is None:
            await self.bot.say("Invalid platform specified.")
            return
        try:
            player = await self.auth.get_player(username, platform)
        except:
            await self.bot.say("Player not found!")
            return
        if player is None:
            await self.bot.say("Player not found!")
            return
        await player.check_general()
        await player.check_level()
        if player.xp is None or player.xp == 0:
            await self.bot.say("There are no stats available for that player.")
            return

        data = discord.Embed(title=username, description="General stats. Use subcommands for more specific stats.")
        data.timestamp = datetime.datetime.now()
        data.colour = self.colours.get(platform)
        data.add_field(name="Kills - Deaths", value="{} - {}".format(player.kills, player.deaths))
        data.add_field(name="K/D Ratio", value="{0:.2f}".format(player.kills / player.deaths))
        data.add_field(name="Playtime", value="{0:.1f}H".format(player.time_played / 3600))
        data.add_field(name="Wins - Losses", value="{} - {}".format(player.matches_won, player.matches_lost))
        data.add_field(name="Win %", value="{0:.1f}%".format(player.matches_won / player.matches_played * 100))
        data.add_field(name="Level", value=player.level)

        await self.bot.say(embed=data)
        
    def request_player(self, username, platform):
        player = self.auth.get_player(username, platform)
        if player is None:
            pass

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