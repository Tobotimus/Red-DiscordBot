import os
import traceback
import datetime
import discord
from discord.ext import commands
from cogs.utils import checks
from cogs.utils.dataIO import dataIO
from cogs.utils.chat_formatting import pagify, box

FOLDER_PATH = "data/errorlogs"
SETTINGS_PATH = "{}/log_channels.json".format(FOLDER_PATH)
DEFAULT_SETTINGS = []
ENABLE = "enable"
DISABLE = "disable"
PRIVATE = "Private channel"

class ErrorLogs():
    """Logs traceback of command errors in specified channels."""

    def __init__(self, bot):
        self.bot = bot
        self.log_channels = dataIO.load_json(SETTINGS_PATH)

    @commands.command(pass_context=True)
    @checks.is_contributor()
    async def logerrors(self, ctx):
        """Toggle error logging in this channel."""
        channel = ctx.message.channel
        task = ENABLE
        if channel.id in self.log_channels:
            task = DISABLE
        await self.bot.say("This will {} command error logging in this channel. Are you sure about this? Type `yes` to agree".format(task))
        message = await self.bot.wait_for_message(author=ctx.message.author)
        if message is not None and message.content == 'yes':
            if task == ENABLE:
                self.log_channels.append(channel.id)
            elif task == DISABLE:
                self.log_channels.remove(channel.id)
            dataIO.save_json(SETTINGS_PATH, self.log_channels)
            await self.bot.say("Error logging {}d.".format(task))
        else:
            await self.bot.say("The operation was cancelled.")

    @commands.command(name="raise", pass_context=True)
    @checks.is_contributor()
    async def _raise(self, ctx):
        """Raise an exception."""
        await self.bot.say("I am raising an error right now.")
        raise Exception()

    async def _on_command_error(self, error, ctx):
        """Sends error info to log channels."""
        if not self.log_channels:
            return
        destinations = [c for c in self.bot.get_all_channels() if c.id in self.log_channels]
        destinations += [c for c in self.bot.private_channels if c.id in self.log_channels]
        error_title = "¯\_(ツ)_/¯ Exception in command '{}'".format(ctx.command.qualified_name)
        log = "".join(traceback.format_exception(type(error), error,
                                                    error.__traceback__))
        _channel_embed = ctx.message.channel
        if _channel_embed.is_private:
            _channel_embed = PRIVATE
        else:
            _channel_embed = _channel_embed.mention
        embed = discord.Embed(title=error_title, colour=discord.Colour.red(), timestamp=ctx.message.timestamp)
        embed.add_field(name="Invoker", value=ctx.message.author.mention)
        embed.add_field(name="Content", value=ctx.message.content)
        embed.add_field(name="Channel", value=_channel_embed)
        embed.set_footer(text="UTC")
        if _channel_embed != PRIVATE:
            embed.add_field(name="Server", value=ctx.message.server.name)
        for channel in destinations:
            try:
                await self.bot.send_message(channel, embed=embed)
            except:
                pass
            for page in pagify(log):
                await self.bot.send_message(channel, box(page, lang="py"))

def check_folders():
    if not os.path.exists(FOLDER_PATH):
            print("Creating " + FOLDER_PATH + " folder...")
            os.makedirs(FOLDER_PATH)

def check_files():
    if dataIO.is_valid_json(SETTINGS_PATH) is False:
        print('Creating json: log_channels.json')
        dataIO.save_json(SETTINGS_PATH, DEFAULT_SETTINGS)

def setup(bot):
    check_folders()
    check_files()
    n = ErrorLogs(bot)
    bot.add_listener(n._on_command_error, 'on_command_error')
    bot.add_cog(n)