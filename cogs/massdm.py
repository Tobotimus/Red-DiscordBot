from typing import List

import discord
from discord.ext import commands

from .utils import checks
CHECKER = None

class MassDM:

    """Send a direct message to all members of the specified Role."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _member_has_role(self, member: discord.Member, role: discord.Role):
        return role in member.roles

    def _get_users_with_role(self, server: discord.Server,
                             role: discord.Role) -> List[discord.User]:
        roled = []
        for member in server.members:
            if self._member_has_role(member, role):
                roled.append(member)
        return roled

    @commands.command(no_pm=True, pass_context=True, name="massdm",
                      aliases=["mdm"])
    @checks.admin_or_permissions(ban_members=True)
    async def _mdm(self, ctx: commands.Context,
                   role: discord.Role, *, message: str):
        """Sends a DM to all Members with the given Role.
        Allows for the following customizations:
        {0} is the member being messaged.
        {1} is the role they are being message through.
        {2} is the person sending the message.
        """
        global CHECKER
        server = ctx.message.server
        sender = ctx.message.author

        try:
            await self.bot.delete_message(ctx.message)
        except:
            pass

        dm_these = self._get_users_with_role(server, role)
        if CHECKER != None:
            await self.bot.send_message(CHECKER, "{1} is trying to mass dm {0} this message, type 'I agree' if you're ok with this."
                                        .format(role,sender))
            await self.bot.send_message(CHECKER, message.format(CHECKER, role, sender))
            answer = await self.bot.wait_for_message(timeout = 3000, author = CHECKER)
            if "i agree" not in answer.content.lower():
                await self.bot.send_message(sender, "You weren't given permission to send this message by {}".format(CHECKER))
                return
        for user in dm_these:
            try:
                await self.bot.send_message(user,
                                                message.format(user, role, sender))
            except (discord.Forbidden, discord.HTTPException):
                continue
        
    @commands.command(no_pm=True, pass_context=True, name="setchecker",
                      aliases=["sc"])
    @checks.admin_or_permissions(administrator=True)
    async def set_checker(self, ctx, Checker: discord.Member = None):
        """Sets a person to validate Mass DM's
        leaving blank <Checker> blank will disable this feature"""
        global CHECKER
        CHECKER = Checker
        if CHECKER != None:
            await self.bot.send_message(CHECKER,"You are the filter for mass DM's, use your power wisely")
        else:
            await self.bot.say("No mass DM checker set, try not to abuse the command")
        try:
            await self.bot.delete_message(ctx.message)
        except:
            pass
        
def setup(bot: commands.Bot):
    bot.add_cog(MassDM(bot))
