import os
import discord
from discord.ext import commands
from discord.ext.commands.bot import Bot
from cogs.utils import checks
from cogs.utils.dataIO import dataIO
from cogs.utils.chat_formatting import inline
from unicodedata import name

DIR_PATH = "data/reactkarma"
KARMA_PATH = "{}/karma.json".format(DIR_PATH)
SETTINGS_PATH = "{}/settings.json".format(DIR_PATH)
DOWNVOTE = "downvotes"
UPVOTE = "upvotes"
DEFAULT = {
    "upvotes"  : {},
    "downvotes": {}
}

class ReactKarma():
    """Keep track of karma for all users in the bot's scope. 
    
    Emojis which affect karma are customised by the owner.
    Upvotes add 1 karma. Downvotes subtract 1 karma."""

    def __init__(self, bot):
        self.bot = bot
        self.karma = dataIO.load_json(KARMA_PATH)
        self.settings = dataIO.load_json(SETTINGS_PATH)
        self.setting_emojis = False # For knowing when emojis are being added/removed

    @commands.command(pass_context=True)
    async def upvotes(self, ctx):
        """List the upvote emojis."""
        await self.bot.say("The upvote emojis are:\n{}".format(self._get_emojis(UPVOTE)))

    @commands.command(pass_context=True)
    async def downvotes(self, ctx):
        """List the downvote emojis."""
        await self.bot.say("The downvote emojis are:\n{}".format(self._get_emojis(DOWNVOTE)))

    @commands.command(name="karma", pass_context=True)
    async def get_karma(self, ctx, user: discord.Member=None):
        """Check a user's karma. 

        Leave [user] blank to see your own karma."""
        if user is None: 
            user = ctx.message.author
        self.karma = dataIO.load_json(KARMA_PATH)
        if user.id in self.karma:
            _karma = self.karma[user.id]
            await self.bot.say("{} has {} karma.".format(user.display_name, _karma))
        else:
            await self.bot.say("{} has never received any karma!".format(user.display_name))
            return

    @commands.command(name="addupvote", aliases=["addupvotes"], pass_context=True)
    @checks.is_owner()
    async def add_upvote(self, ctx):
        """Add an upvote emoji by reacting to the bot's response.
        
        Only reactions from the command author will be added."""
        msg = await self.bot.say("React to my message with the new upvote emoji(s)! (I will respond once done)")
        self.setting_emojis = True
        response = await self.bot.wait_for_reaction(user=ctx.message.author, message=msg, timeout=10.0)
        while response is not None:
            if response.user == ctx.message.author:
                self._add_reaction(response.reaction, UPVOTE)
            response = await self.bot.wait_for_reaction(user=ctx.message.author, message=msg, timeout=8.0)
        self.setting_emojis = False
        await self.bot.say("Done! The upvote emojis are now:\n {}".format(self._get_emojis(UPVOTE)))
        
    @commands.command(name="adddownvote", aliases=["adddownvotes"], pass_context=True)
    @checks.is_owner()
    async def add_downvote(self, ctx):
        """Add a downvote emoji by reacting to the bot's response.
        
        Only reactions from the command author will be added."""
        msg = await self.bot.say("React to my message with the new downvote emoji(s)! (I will respond once done)")
        self.setting_emojis = True
        response = await self.bot.wait_for_reaction(user=ctx.message.author, message=msg, timeout=10.0)
        while response is not None:
            if response.user == ctx.message.author:
                self._add_reaction(response.reaction, DOWNVOTE)
            response = await self.bot.wait_for_reaction(user=ctx.message.author, message=msg, timeout=8.0)
        self.setting_emojis = False
        await self.bot.say("Done! The downvote emojis are now:\n{}".format(self._get_emojis(DOWNVOTE)))

    @commands.command(name="removeupvote", aliases=["removeupvotes"], pass_context=True)
    @checks.is_owner()
    async def remove_upvote(self, ctx):
        """Remove an upvote emoji by reacting to the bot's response.
        
        Only reactions from the command author will be removed."""
        msg = await self.bot.say("React to my message with the upvote emoji(s)! (I will respond once done)")
        self.setting_emojis = True
        response = await self.bot.wait_for_reaction(user=ctx.message.author, message=msg, timeout=10.0)
        while response is not None:
            if response.user == ctx.message.author:
                self._remove_reaction(response.reaction, UPVOTE)
            response = await self.bot.wait_for_reaction(user=ctx.message.author, message=msg, timeout=8.0)
        self.setting_emojis = False
        await self.bot.say("Done! The upvote emojis are now:\n {}".format(self._get_emojis(UPVOTE)))

    @commands.command(name="removedownvote", aliases=["removedownvotes"], pass_context=True)
    @checks.is_owner()
    async def remove_downvote(self, ctx):
        """Remove a downvote emoji by reacting to the bot's response.
        
        Only reactions from the command author will be removed."""
        msg = await self.bot.say("React to my message with the downvote emoji(s)! (I will respond once done)")
        self.setting_emojis = True
        response = await self.bot.wait_for_reaction(user=ctx.message.author, message=msg, timeout=10.0)
        while response is not None:
            if response.user == ctx.message.author:
                self._remove_reaction(response.reaction, DOWNVOTE)
            response = await self.bot.wait_for_reaction(user=ctx.message.author, message=msg, timeout=8.0)
        self.setting_emojis = False
        await self.bot.say("Done! The downvote emojis are now:\n {}".format(self._get_emojis(DOWNVOTE)))

    @commands.command(name="resetkarma", pass_context=True)
    @checks.is_owner()
    async def reset_karma(self, ctx):
        await self.bot.say("This will remove all karma from all members across all servers. "
                           "Are you sure you want to do this? Type `yes` to continue.")
        accepted = await self.bot.wait_for_message(author=ctx.message.author, content="yes", timeout=15.0)
        if accepted is not None:
            self.karma = {}
            dataIO.save_json(KARMA_PATH, self.karma)
            await self.bot.say("Karma reset.")
        else:
            await self.bot.say("Reset cancelled.")

    async def reaction_added(self, reaction: discord.Reaction, user: discord.User):
        if self.setting_emojis: return # Don't change karma whilst adding/removing emojis
        author = reaction.message.author
        if author == user: return # Users can't change their own karma
        emoji = reaction.emoji
        if isinstance(emoji, discord.Emoji):
            emoji = emoji.name.upper()
        else:
            emoji = name(emoji).upper()
        if emoji in self.settings[UPVOTE]:
            self._add_karma(author.id, 1)
        elif emoji in self.settings[DOWNVOTE]:
            self._add_karma(author.id, -1)

    async def reaction_removed(self, reaction: discord.Reaction, user: discord.User):
        if self.setting_emojis: return # Don't change karma whilst adding/removing emojis
        author = reaction.message.author
        if author == user: return # Users can't change their own karma
        emoji = reaction.emoji
        if isinstance(emoji, discord.Emoji):
            emoji = emoji.name.upper()
        else:
            emoji = name(emoji).upper()
        if emoji in self.settings[UPVOTE]:
            self._add_karma(author.id, -1)
        elif emoji in self.settings[DOWNVOTE]:
            self._add_karma(author.id, 1)

    def _add_reaction(self, reaction: discord.Reaction, type):
        emoji = reaction.emoji
        if isinstance(emoji, discord.Emoji):
            emoji_name = emoji.name.upper()
            emoji = str(emoji)
        else:
            emoji_name = name(emoji).upper()
        if type in self.settings:
            self.settings[type][emoji_name] = emoji
            dataIO.save_json(SETTINGS_PATH, self.settings)

    def _remove_reaction(self, reaction: discord.Reaction, type):
        emoji = reaction.emoji
        if isinstance(emoji, discord.Emoji):
            emoji_name = emoji.name.upper()
            emoji = str(emoji)
        else:
            emoji_name = name(emoji).upper()
        if type in self.settings and emoji_name in self.settings[type]:
            del self.settings[type][emoji_name]
            dataIO.save_json(SETTINGS_PATH, self.settings)

    def _get_emojis(self, type):
        if type in self.settings and self.settings[type]:
            ret = []
            for emoji_name, emoji in self.settings[type].items():
                ret.append(str(emoji))
            return " ".join(ret)

    def _add_karma(self, user_id, amount: int):
        self.karma = dataIO.load_json(KARMA_PATH)
        if user_id not in self.karma:
            self.karma[user_id] = 0
        self.karma[user_id] += amount
        dataIO.save_json(KARMA_PATH, self.karma)


def check_folders():
    if not os.path.exists(DIR_PATH):
        print("Creating {} folder...".format(DIR_PATH))
        os.makedirs(DIR_PATH)

def check_files():
    if not dataIO.is_valid_json(KARMA_PATH):
        dataIO.save_json(KARMA_PATH, {})
    if not dataIO.is_valid_json(SETTINGS_PATH):
        dataIO.save_json(SETTINGS_PATH, DEFAULT)

def setup(bot):
    check_folders()
    check_files()
    n = ReactKarma(bot)
    bot.add_listener(n.reaction_added, "on_reaction_add")
    bot.add_listener(n.reaction_removed, "on_reaction_remove")
    bot.add_cog(ReactKarma(bot))