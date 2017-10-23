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
UNIT_SUF_TABLE = {'sec': (1, ''),
                  'min': (60, ''),
                  'hr': (60 * 60, 's'),
                  'day': (60 * 60 * 24, 's')
                  }
                  
def _generate_timespec(sec):
    timespec = []

    def sort_key(kt):
        k, t = kt
        return t[0]
    for unit, kt in sorted(UNIT_SUF_TABLE.items(), key=sort_key, reverse=True):
        secs, suf = kt
        q = sec // secs
        if q:
            if q <= 1:
                suf = ''
            timespec.append('%02.d%s%s' % (q, unit, suf))
        sec = sec % secs
    return ', '.join(timespec)
    
    
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
    async def strike(self, ctx, user: discord.Member, reason: str, strikes = 1):
        """Strikes a misbehaving user.
        
        Remember to use quotation marks around the reason."""
        server = ctx.message.server
        moderator = ctx.message.author
        self.json_server_check(server)
        strike_level = 0
        serverSettings = self.settings[server.id]
        nStrikes = serverSettings["nStrikes"]
        
        # --- GET DATA FROM JSON ---
        if user.id == moderator.id:
            await self.bot.say('Please don\'t strike yourself :(')
        elif user.id not in serverSettings:
            # USER HAS NO STRIKES
            if strikes > nStrikes:
                strikes = nStrikes
            strike_level = strikes
            forgiveAfter = serverSettings["forgive"][strike_level-1]
            until = forgiveAfter + int(time.time())
            serverSettings[user.id] = { "strike" : strike_level, "until" : until, "givenBy" : [moderator.id], "reason" : [reason]}
            
            #Keep continuity with forgive function
            for i in range(strikes-1):
                serverSettings[user.id]["givenBy"].append(moderator.id)
                serverSettings[user.id]["reason"].append(reason)
                
            dataIO.save_json(self.location, self.settings)
            await self.bot.say("{} has been given {} strike(s) by {}".format(user.name, strikes, moderator.name))
        elif user.id in self.settings[server.id]:
            # --- GIVE USER ANOTHER STRIKE ---
            strike_level = serverSettings[user.id]["strike"]
            if strike_level != nStrikes:
                if strike_level + strikes > nStrikes:
                    serverSettings[user.id]["strike"] = nStrikes
                else:
                    serverSettings[user.id]["strike"] += strikes
                strike_level = serverSettings[user.id]["strike"]
                forgiveAfter = serverSettings["forgive"][strike_level-1]
                until = forgiveAfter + int(time.time())
                serverSettings[user.id]["until"] = until
                serverSettings[user.id]["givenBy"].append(moderator.id)
                serverSettings[user.id]["reason"].append(reason)
                dataIO.save_json(self.location, self.settings)
                await self.bot.say("{} has been given {} strike(s) by {}".format(user.name, strikes, moderator.name))
            else:
                await self.bot.say("Max number of strikes already reached, is this user not perma banned yet?")
        # TODO : Respond to command
        # TODO : Send user a DM
        # TODO : Give user penalty
        # TODO : Check if moderator has permission to ban if applicable
    
    # TODO : !amend (change a reason for a strike)
    
    async def amend(self, ctx, user: discord.Member, strikeNum, reason:str):
        """Amend a strike's reason"""
        
        
    # TODO : !forgive (manually remove a strike)
    @commands.command(pass_context=True, no_pm=True)
	@checks.mod_or_permissions(kick_members=True)
    async def forgive(self, ctx, user: discord.Member, count=1):
        """Manually removes strikes, most recent by default.
        Can specify how many strikes to remove."""
        server = ctx.message.server
        moderator = ctx.message.author
        serverSettings = self.settings[server.id]
        nStrikes = serverSettings["nStrikes"]
        if user.id not in serverSettings:
            await self.bot.say("User has no strikes on this server")
            
        elif user.id == moderator.id:
            await self.bot.say("You can't remove your own strikes!")
            
        elif serverSettings[user.id]["strike"] == 0:
            await self.bot.say("User does not have a strike on this sever")
            
        else:
            if count > nStrikes:
                count = nStrikes
            serverSettings[user.id]["strike"] -= count
            if serverSettings[user.id]["strike"] <= 0:
                del(serverSettings[user.id])
                dataIO.save_json(self.location, self.settings)
                await self.bot.say("{} has been completely forgiven".format(user.name))
                return
                
            strike_level = serverSettings[user.id]["strike"]
            forgiveAfter = serverSettings["forgive"][strike_level-1]
            del(serverSettings[user.id]["givenBy"][-1])
            del(serverSettings[user.id]["reason"][-1])
            until = forgiveAfter + int(time.time())
            serverSettings[user.id]["until"] = until
            dataIO.save_json(self.location,self.settings)
            await self.bot.say("I guess we can forgive {} for what they've done".format(user.name))
       
        
    # TODO : !strikes (a list of striked users)
    @commands.command(pass_context=True, no_pm=True)
	@checks.mod_or_permissions(kick_members=True)
    async def strikes(self,ctx):
        """List of all users currently striked"""
        server = ctx.message.server
        userCheck = False
        if server.id not in self.settings:
            await self.bot.say("No users are currently striked")
            return
        nStrikes = self.settings[server.id]["nStrikes"]
        #Check for users
        for i in self.settings[server.id]:
            if i not in ["duration", "forgive", "nStrikes", "penalty"]:
                userCheck = True
        if userCheck == False:
            await self.bot.say("No users are currently striked")
            return
            
        def getmname(mid):
            member = discord.utils.get(server.members, id=mid)
            if member:
                if member.nick:
                    return '%s (%s)' % (member.nick, member)
                else:
                    return str(member)
            else:
                return '(member not present, id #%d)'

        headers = ['Member', 'Strike', 'Remaining', 'Striked by', 'Reason']
        table = []
        disp_table = []
        now = time.time()
        for member_id in self.settings[server.id]:
            if member_id in ["duration", "forgive", "nStrikes", "penalty"]:
                continue
            data = self.settings[server.id][member_id]
            member_name = getmname(member_id)
            punisher_name = data["givenBy"][-1]
            punisher_name = getmname(punisher_name.translate({ord(i): None for i in "'[]"}))
            
            reason = data["reason"][-1]
            t = data["until"]
            strike = data["strike"]
            sort = t if t else float("inf")
            table.append((sort, member_name, strike, t, punisher_name, reason))
            
        for _, name, strike, rem, mod, reason in sorted(table, key=lambda x: x[0]):
            remaining = _generate_timespec(rem - now) if rem else 'Forever'
            if strike == nStrikes:
                remaining = 'Forever'
            if not reason:
                reason = 'n/a'
            disp_table.append((name, strike, remaining, mod, reason))
            
        msg = '```\n%s\n```' % tabulate(disp_table, headers)
        await self.bot.say(msg)
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