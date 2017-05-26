import discord
from discord.ext import commands
from .utils import checks
import asyncio
import logging
from __main__ import send_cmd_help
from cogs.utils.dataIO import dataIO
import os
import time
import copy
# Tabulate, for displaying strikes
try:
    from tabulate import tabulate
except:
    raise Exception('Run "pip install tabulate" in your CMD/Linux Terminal')
log = logging.getLogger('red.strike')

PERMENENT = -1
NONE = 0
WARNING = 1
TIMEOUT = 2
BAN = 3
HOUR = 3600
DAY = 86400
default_settings = {
    "nStrikes"  : 4, 
    "penalty"   : [WARNING, TIMEOUT, BAN, BAN], 
    "duration"  : [NONE, 1 * DAY, 14 * DAY, PERMENENT], 
    "forgive"   : [30 * DAY, 30 * DAY, 90 * DAY, PERMENENT] 
}

# Perhaps we should merge this cog with punish? 
# Or just add !timeout here to replace punish?
# Also need to be able to ban users for a period of time
# Should we add that in here or in mod.py?
    
class Strike:
    """Keeps track of strikes and takes action on misbehaving users."""
    
    # --- Format
    # {
    # Server : {
    #   UserIDs : {
    #     Strike :
    #     Until :
    #     GivenBy : []
    #     Reason(s): []
    #     }
    #   }
    #   NumOfStrikes: 
    #   Pentalties: []
    #   PenaltyDurations: []
    #   ForgiveAfter: []
    # }
    # ---
    
    def __init__(self, bot):
        self.bot = bot
        self.location = 'data/strike/settings.json'
        self.settings = dataIO.load_json(self.location)
        
    def json_server_check(self, server):
        if server.id not in self.settings:
                log.debug('Adding server({}) in Json'.format(server.id))
                self.settings[server.id] = default_settings
                dataIO.save_json(self.location, self.settings)
                
    @commands.command(pass_context=True, no_pm=True)
    @checks.mod_or_permissions(kick_members=True)
    async def strike(self, ctx, user: discord.Member, reason: str):
        """Strikes a misbehaving user.
        
        Remember to use quotation marks around the reason."""
        server = ctx.message.server
        moderator = ctx.message.author
        self.json_server_check(server)
        strike_level = 0
        # --- GET DATA FROM JSON ---
        if user.id == moderator.id:
            await self.bot.say('Please don\'t strike yourself :(')
        elif user.id not in self.settings[server.id]:
            # USER HAS NO STRIKES
            forgiveAfter = self.settings[server.id]["forgive"][strike_level]
            strike_level = 1
            until = forgiveAfter + int(time.time())
            self.settings[server.id][user.id] = { "strike" : strike_level, "until" : until, "givenBy" : [moderator.id], "reason" : [reason] }
            dataIO.save_json(self.location, self.settings)
            # TODO : Respond to command
            # TODO : Send user a DM
            # TODO : Give user penalty
            # TODO : Check if moderator has permission to ban if applicable
        elif user.id in self.settings[server.id]:
            # --- GIVE USER ANOTHER STRIKE ---
            strike_level = self.settings[server.id][user.id]["strike"]
            forgiveAfter = self.settings[server.id]["forgive"][strike_level]
            until = forgiveAfter + int(time.time())
            self.settings[server.id][user.id]["strike"] += 1
            self.settings[server.id][user.id]["until"] = until
            self.settings[server.id][user.id]["givenBy"].append(moderator.id)
            self.settings[server.id][user.id]["reason"].append(reason)
            dataIO.save_json(self.location, self.settings)
            # TODO : Respond to command
            # TODO : Send user a DM
            # TODO : Give user penalty
            # TODO : Check if moderator has permission to ban if applicable
    
    # TODO : !amend (change a reason for a strike)
    
    # TODO : !forgive (manually remove a strike)
    
    # TODO : !strikes (a list of striked users)
    
    # TODO : !strikeset (group of commands for changing settings)
    
    # TODO : !strikes ()
    
    # TODO : listener for when the penalty / strike expires
    
def check_folder():
    if not os.path.exists('data/strike'):
        log.debug('Creating folder: data/strike')
        os.makedirs('data/strike')


def check_file():
    f = 'data/strike/settings.json'
    if dataIO.is_valid_json(f) is False:
        log.debug('Creating json: settings.json')
        dataIO.save_json(f, {})


def setup(bot):
    check_folder()
    check_file()
    n = Strike(bot)
    bot.add_cog(n)