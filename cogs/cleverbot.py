from discord.ext import commands
import discord.utils
from cogs.utils import checks
from .utils.dataIO import dataIO
import discord.utils
import os
import aiohttp
import json

API_URL = "https://www.cleverbot.com/getreply"


class CleverbotError(Exception):
    pass

class NoCredentials(CleverbotError):
    pass

class InvalidCredentials(CleverbotError):
    pass

class APIError(CleverbotError):
    pass

class OutOfRequests(CleverbotError):
    pass

class OutdatedCredentials(CleverbotError):
    pass


class Cleverbot():
    """Cleverbot"""

    def __init__(self, bot):
        self.bot = bot
        self.settings = dataIO.load_json("data/cleverbot/settings.json")
        self.instances = dataIO.load_json("data/cleverbot/instances.json")

    @commands.group(no_pm=True, invoke_without_command=True, pass_context=True)
    async def cleverbot(self, ctx, *, message):
        """Talk with cleverbot"""
        author = ctx.message.author
        channel = ctx.message.channel
        try:
            result = await self.get_response(author, message)
        except NoCredentials:
            await self.bot.send_message(channel, "The owner needs to set the credentials first.\n"
                                                 "See: `[p]cleverbot apikey`")
        except APIError:
            await self.bot.send_message(channel, "Error contacting the API.")
        except InvalidCredentials:
            await self.bot.send_message(channel, "The token that has been set is not valid.\n"
                                                 "See: `[p]cleverbot apikey`")
        except OutOfRequests:
            await self.bot.send_message(channel, "You have ran out of requests for this month. "
                                                 "The free tier has a 5000 requests a month limit.")
        except OutdatedCredentials:
            await self.bot.send_message(channel, "You need a valid cleverbot.com api key for this to "
                                                 "work. The old cleverbot.io service will soon be no "
                                                 "longer active. See `[p]help cleverbot apikey`")
        else:
            await self.bot.say(result)

    @cleverbot.command(pass_context=True)
    async def conversations(self, ctx):
        """See who the bot is talking to"""
        server = ctx.message.server
        author = ctx.message.author
        message = "No one is talking to me right now."
        if len(self.instances):
            message = "I am having a conversation with the following users:\n```"
            for c in self.instances:
                if discord.utils.get(server.members, id=c) is not None:
                    message += "\n{}".format(discord.utils.get(server.members, id=c).display_name)
            message += "\n```"
        await self.bot.say(message)
        
    @cleverbot.command(pass_context=True)
    async def goodbye(self, ctx):
        """End your conversation with the bot"""
        await self.end_conversation(ctx.message.author, ctx.message.channel)
        
    @cleverbot.command()
    @checks.is_owner()
    async def toggle(self):
        """Toggles reply on mention"""
        self.settings["TOGGLE"] = not self.settings["TOGGLE"]
        if self.settings["TOGGLE"]:
            await self.bot.say("I will reply on mention.")
        else:
            await self.bot.say("I won't reply on mention anymore.")
        dataIO.save_json("data/cleverbot/settings.json", self.settings)
        
    @cleverbot.command()
    @checks.is_owner()
    async def apikey(self, key: str):
        """Sets token to be used with cleverbot.com

        You can get it from https://www.cleverbot.com/api/
        Use this command in direct message to keep your
        token secret"""
        self.settings["cleverbot_key"] = key
        self.settings.pop("key", None)
        self.settings.pop("user", None)
        dataIO.save_json("data/cleverbot/settings.json", self.settings)
        await self.bot.say("Credentials set.")

    async def get_response(self, author, text):
        payload = {}
        payload["key"] = self.get_credentials()
        payload["cs"] = self.instances.get(author.id, "")
        payload["input"] = text
        session = aiohttp.ClientSession()

        async with session.get(API_URL, params=payload) as r:
            if r.status == 200:
                data = await r.text()
                data = json.loads(data, strict=False)
                self.instances[author.id] = data["cs"] # Preserves conversation status
            elif r.status == 401:
                raise InvalidCredentials()
            elif r.status == 503:
                raise OutOfRequests()
            else:
                raise APIError()
        await session.close()
        dataIO.save_json("data/cleverbot/instances.json", self.instances)
        return data["output"]

    def get_credentials(self):
        if "cleverbot_key" not in self.settings:
            if "key" in self.settings:
                raise OutdatedCredentials() # old cleverbot.io credentials
        try:
            return self.settings["cleverbot_key"]
        except KeyError:
            raise NoCredentials()

    async def on_message(self, message):
        if not self.settings["TOGGLE"] or message.server is None:
            return

        if not self.bot.user_allowed(message):
            return

        author = message.author
        channel = message.channel

        if message.author.id != self.bot.user.id:
            to_strip = "@" + author.server.me.display_name + " "
            text = message.clean_content
            if not text.startswith(to_strip):
                return
            text = text.replace(to_strip, "", 1)
            await self.bot.send_typing(channel)
            if "goodbye" in text.lower():
                await self.end_conversation(author, channel)
            else:
                try:
                    response = await self.get_response(author, text)
                except NoCredentials:
                    await self.bot.send_message(channel, "The owner needs to set the credentials first.\n"
                                                            "See: `[p]cleverbot apikey`")
                except APIError:
                    await self.bot.send_message(channel, "Error contacting the API.")
                except InvalidCredentials:
                    await self.bot.send_message(channel, "The token that has been set is not valid.\n"
                                                            "See: `[p]cleverbot apikey`")
                except OutOfRequests:
                    await self.bot.send_message(channel, "You have ran out of requests for this month. "
                                                            "The free tier has a 5000 requests a month limit.")
                except OutdatedCredentials:
                    await self.bot.send_message(channel, "You need a valid cleverbot.com api key for this to "
                                                            "work. The old cleverbot.io service will soon be no "
                                                            "longer active. See `[p]help cleverbot apikey`")
                else:
                    await self.bot.send_message(channel, response)
                
    async def end_conversation(self, author, channel):
        if author.id in self.instances:
            try:
                goodbye = await self.get_response(author, "Goodbye Cleverbot.")
            except:
                goodbye = "Goodbye {}.".format(author.display_name)
            del self.instances[author.id]
            dataIO.save_json("data/cleverbot/instances.json", self.instances)
            await self.bot.send_message(channel, goodbye)
        else:
            await self.bot.send_message(channel, "I was never talking to you in the first place.")


def check_folders():
    if not os.path.exists("data/cleverbot"):
        print("Creating data/cleverbot folder...")
        os.makedirs("data/cleverbot")


def check_files():
    f = "data/cleverbot/settings.json"
    data = {"TOGGLE" : True}
    if not dataIO.is_valid_json(f):
        dataIO.save_json(f, data)
    f = "data/cleverbot/instances.json"
    data = {}
    if not dataIO.is_valid_json(f):
        dataIO.save_json(f, data)


def setup(bot):
    check_folders()
    check_files()
    bot.add_cog(Cleverbot(bot))
