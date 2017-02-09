import discord
from discord.ext import commands
from .utils import checks
import asyncio
import logging
# Data stuffies
from __main__ import send_cmd_help
from cogs.utils.dataIO import dataIO
from cogs.utils.chat_formatting import box
import os
import copy

log = logging.getLogger('red.register')

class Register:
    """Allows users to register for certain roles."""
    
    def __init__(self, bot):
        self.bot = bot
        self.location = 'data/register/settings.json'
        self.json = dataIO.load_json(self.location)

    @commands.command(pass_context=True, no_pm=True)
    async def register(self, ctx, role_name: str=''):
        """Gives the user a role

        Valid roles can be added using !regedit
        Example usage: !register PC"""
        server = ctx.message.server
        user = ctx.message.author
        if role_name:
            # --- CHECKING VALID ROLE ---
            try:
                role = discord.utils.get(server.roles, name=role_name)
                if role.id in self.json[server.id]:
                    # --- VALID ROLE! ---
                    # --- ADD TO USER ---
                    if role not in user.roles:
                        await self.bot.add_roles(user, role)
                        await self.bot.send_message(user, '{} role has been assigned to you in {}!'.format(role.name, server.name))
                    # --- REMOVE FROM USER ---
                    else:
                        await self.bot.remove_roles(user, role)
                        await self.bot.send_message(user, '{} role has been removed from you in {}!'.format(role.name, server.name))
            except:
                await self.bot.say('That role isn\'t in this server.')
        else:
            # NO ROLE GIVEN
            # PM USER HELP MESSAGE
            pages = self.bot.formatter.format_help_for(ctx, ctx.command)
            for page in pages:
                await self.bot.send_message(user, page)
            # PM USER VALID ROLES
            if server.id in self.json:
                valid_roles = []
                for r in self.json[server.id]:
                    role = discord.utils.get(server.roles, id=r)
                    log.debug(role.id)
                    if role is None:
                        temp.append('ID: {}'.format(role.id))
                    else:
                        valid_roles.append(role.name)
                msg = ("Valid register roles in {}:\n"
                        "{}"
                        "".format(server.name, ", ".join(sorted(valid_roles)))
                        )
                await self.bot.send_message(user, box(msg))
            else:
                msg = "There aren't any roles you can register for in {}".format(server.name)
                await self.bot.send_message(user, box(msg))
        await self.bot.delete_message(ctx.message)

    @commands.group(pass_context=True, no_pm=True)
    @checks.admin_or_permissions(administrator=True)
    async def regedit(self, ctx):
        """Manages valid register roles."""
        if ctx.invoked_subcommand is None:
            # Display valid register roles
            server = ctx.message.server
            await send_cmd_help(ctx)
            valid_roles = []
            if server.id in self.json:
                for r in self.json[server.id]:
                    # Get the role name
                    role = discord.utils.get(server.roles, id=r)
                    log.debug(role.id)
                    if role is None:
                        temp.append('ID: {}'.format(role.id))
                    else:
                        valid_roles.append(role.name)

            msg = ("Valid register roles:\n"
                   "{}"
                   "".format(", ".join(sorted(valid_roles)))
                   )
            await self.bot.say(box(msg))

    @regedit.command(name="addrole", pass_context=True, no_pm=True)
    async def _regedit_addrole(self, ctx, *, role_name: str):
        """Adds a register role."""
        server = ctx.message.server
        # --- CREATING ROLE ---
        if role_name not in [r.name for r in server.roles]:
            await self.bot.say('The {} role doesn\'t exist! Creating it now!'.format(role_name))
            log.debug('Creating {} role in {}'.format(role_name, server.id))
            try:
                perms = discord.Permissions.none()
                await self.bot.create_role(server, name=role_name, permissions=perms)
                await self.bot.say("Role created!")
            except discord.Forbidden:
                await self.bot.say("I cannot create a role. Please assign Manage Roles to me!")
        role = discord.utils.get(server.roles, name=role_name)
        # --- DONE CREATING ROLE! ---
        self.add_server_to_json(server)
        # --- ADDING ROLE TO JSON ---
        try:
            if role.id not in self.json[server.id]:
                # ROLE NOT IN REGISTER
                self.json[server.id][role.id] = {'role_name': role.name}
                dataIO.save_json(self.location, self.json)
                await self.bot.say('``{}`` is now in register.'.format(role.name))
            else:
                # ROLE ALREADY IN REGISTER
                await self.bot.say('``{}`` is already in register!'.format(role.name))
        except:
            await self.bot.say('Something went wrong.')

    @regedit.command(name="removerole", pass_context=True, no_pm=True)
    async def _regedit_removerole(self, ctx, *, role_name: str):
        """Removes a register role."""
        server = ctx.message.server
        if server.id in self.json:
            role = discord.utils.get(server.roles, name=role_name)
            if role:
                # ROLE IS IN SERVER
                if role.id in self.json[server.id]:
                    # REMOVE ROLE FROM JSON
                    del self.json[server.id][role.id]
                    dataIO.save_json(self.location, self.json)
                    await self.bot.say('``{}`` role has been removed from register.'.format(role.name))
                else:
                    # ROLE ISN'T IN JSON
                    await self.bot.say('``{}`` role isn\'t in register yet.'.format(role.name))
            else:
                # ROLE ISN'T IN SERVER
                await self.bot.say('That role isn\'t in this server.')
                if role_name in [r['role_name'] for r in self.json[server.id]]:
                    # TODO: REMOVE ROLE FROM JSON
                    del self.json[server.id][r]
                    dataIO.save_json(self.location, self.json)
                    await self.bot.say('Old role removed from register.')
                else:
                    await self.bot.say('That role isn\'t in this server.')
        else:
            msg = 'There aren\'t any roles you can register for in this server.'.format(server.name)
            await self.bot.say(box(msg))

    # TODO : FINISH DELCMDS
    '''@regedit.command(name="delcmds", pass_context=True, no_pm=True)
    async def _regedit_delcmds(self, ctx):
        """Toggles whether or not a the !register command is deleted after being sent."""
        self.add_server_to_json(server)'''
        
    def add_server_to_json(server):
        if server.id not in self.json:
                log.debug('Adding server({}) in Json'.format(server.id))
                self.json[server.id] = {}
                dataIO.save_json(self.location, self.json)

        
def check_folder():
    if not os.path.exists('data/register'):
        log.debug('Creating folder: data/register')
        os.makedirs('data/register')


def check_file():
    f = 'data/register/settings.json'
    if dataIO.is_valid_json(f) is False:
        log.debug('Creating json: settings.json')
        dataIO.save_json(f, {})


def setup(bot):
    check_folder()
    check_file()
    n = Register(bot)
    bot.add_cog(n)
