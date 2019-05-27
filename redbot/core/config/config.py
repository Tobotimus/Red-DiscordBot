import asyncio
from copy import deepcopy
from typing import Any, Dict, MutableMapping, Optional, Tuple, TypeVar, Union
import weakref

import discord

from .drivers import BaseDriver, get_driver
from .group import Group
from .identifier_data import IdentifierData
from .utils import ConfigCategory
from .value import Value

__all__ = ["Config", "get_latest_confs"]

_T = TypeVar("_T")

_config_cache = weakref.WeakValueDictionary()
_retrieved = weakref.WeakSet()


class Config:
    """Configuration manager for cogs and Red.

    You should always use `get_conf` to instantiate a Config object. Use
    `get_core_conf` for Config used in the core package.

    .. important::
        Most config data should be accessed through its respective
        group method (e.g. :py:meth:`guild`) however the process for
        accessing global data is a bit different. There is no
        :python:`global` method because global data is accessed by
        normal attribute access::

            await conf.foo()

    Attributes
    ----------
    cog_name : `str`
        The name of the cog that has requested a `Config` object.
    unique_identifier : `int`
        Unique identifier provided to differentiate cog data when name
        conflicts occur.
    driver
        An instance of a driver that implements `BaseDriver`.
    force_registration : `bool`
        Determines if Config should throw an error if a cog attempts to access
        an attribute which has not been previously registered.

        Note
        ----
        **You should use this.** By enabling force registration you give Config
        the ability to alert you instantly if you've made a typo when
        attempting to access data.

    """

    def __new__(cls, cog_name, unique_identifier, *args, **kwargs):
        key = (cog_name, unique_identifier)

        if key[0] is None:
            raise ValueError("You must provide either the cog instance or a cog name.")

        if key in _config_cache:
            conf = _config_cache[key]
        else:
            conf = object.__new__(cls)
            _config_cache[key] = conf
        return conf

    def __init__(
        self,
        cog_name: str,
        unique_identifier: str,
        driver: BaseDriver,
        force_registration: bool = False,
        defaults: dict = None,
    ):
        self.cog_name = cog_name
        self.unique_identifier = unique_identifier

        self.driver = driver
        self.force_registration = force_registration
        self._defaults = defaults or {}

        self.custom_groups: Dict[str, int] = {}
        self._lock_cache: MutableMapping[
            IdentifierData, asyncio.Lock
        ] = weakref.WeakValueDictionary()

    @property
    def defaults(self):
        return deepcopy(self._defaults)

    @classmethod
    def get_conf(cls, cog_instance, identifier: int, force_registration=False, cog_name=None):
        """Get a Config instance for your cog.

        .. warning::

            If you are using this classmethod to get a second instance of an
            existing Config object for a particular cog, you MUST provide the
            correct identifier. If you do not, you *will* screw up all other
            Config instances for that cog.

        Parameters
        ----------
        cog_instance
            This is an instance of your cog after it has been instantiated. If
            you're calling this method from within your cog's :code:`__init__`,
            this is just :code:`self`.
        identifier : int
            A (hard-coded) random integer, used to keep your data distinct from
            any other cog with the same name.
        force_registration : `bool`, optional
            Should config require registration of data keys before allowing you
            to get/set values? See `force_registration`.
        cog_name : str, optional
            Config normally uses ``cog_instance`` to determine tha name of your cog.
            If you wish you may pass ``None`` to ``cog_instance`` and directly specify
            the name of your cog here.

        Returns
        -------
        Config
            A new Config object.

        """
        uuid = str(identifier)
        if cog_name is None:
            cog_name = type(cog_instance).__name__

        driver = get_driver(cog_name, uuid)
        if hasattr(driver, "migrate_identifier"):
            driver.migrate_identifier(identifier)

        conf = cls(
            cog_name=cog_name,
            unique_identifier=uuid,
            force_registration=force_registration,
            driver=driver,
        )
        return conf

    @classmethod
    def get_core_conf(cls, force_registration: bool = False):
        """Get a Config instance for the core bot.

        All core modules that require a config instance should use this
        classmethod instead of `get_conf`.

        Parameters
        ----------
        force_registration : `bool`, optional
            See `force_registration`.

        """
        return cls.get_conf(
            None, cog_name="Core", identifier=0, force_registration=force_registration
        )

    def __getattr__(self, item: str) -> Union[Group, Value]:
        """Same as `group.__getattr__` except for global data.

        Parameters
        ----------
        item : str
            The attribute you want to get.

        Returns
        -------
        `Group` or `Value`
            The value for the attribute you want to retrieve

        Raises
        ------
        AttributeError
            If there is no global attribute by the given name and
            `force_registration` is set to :code:`True`.
        """
        global_group = self._get_base_group(ConfigCategory.GLOBAL)
        return getattr(global_group, item)

    @staticmethod
    def _get_defaults_dict(key: str, value) -> dict:
        """
        Since we're allowing nested config stuff now, not storing the
        _defaults as a flat dict sounds like a good idea. May turn out
        to be an awful one but we'll see.
        """
        ret = {}
        partial = ret
        splitted = key.split("__")
        for i, k in enumerate(splitted, start=1):
            if not k.isidentifier():
                raise RuntimeError("'{}' is an invalid config key.".format(k))
            if i == len(splitted):
                partial[k] = value
            else:
                partial[k] = {}
                partial = partial[k]
        return ret

    @staticmethod
    def _update_defaults(to_add: Dict[str, Any], _partial: Dict[str, Any]):
        """
        This tries to update the _defaults dictionary with the nested
        partial dict generated by _get_defaults_dict. This WILL
        throw an error if you try to have both a value and a group
        registered under the same name.
        """
        for k, v in to_add.items():
            val_is_dict = isinstance(v, dict)
            if k in _partial:
                existing_is_dict = isinstance(_partial[k], dict)
                if val_is_dict != existing_is_dict:
                    # != is XOR
                    raise KeyError("You cannot register a Group and a Value under the same name.")
                if val_is_dict:
                    Config._update_defaults(v, _partial=_partial[k])
                else:
                    _partial[k] = v
            else:
                _partial[k] = v

    def _register_default(self, category: Union[ConfigCategory, str], **kwargs: Any):
        category = str(category)
        if category not in self._defaults:
            self._defaults[category] = {}

        data = deepcopy(kwargs)

        for k, v in data.items():
            to_add = self._get_defaults_dict(k, v)
            self._update_defaults(to_add, self._defaults[category])

    def register_global(self, **kwargs):
        """Register default values for attributes you wish to store in `Config`
        at a global level.

        Examples
        --------
        You can register a single value or multiple values::

            conf.register_global(
                foo=True
            )

            conf.register_global(
                bar=False,
                baz=None
            )

        You can also now register nested values::

            _defaults = {
                "foo": {
                    "bar": True,
                    "baz": False
                }
            }

            # Will register `foo.bar` == True and `foo.baz` == False
            conf.register_global(
                **_defaults
            )

        You can do the same thing without a :python:`_defaults` dict by
        using double underscore as a variable name separator::

            # This is equivalent to the previous example
            conf.register_global(
                foo__bar=True,
                foo__baz=False
            )

        """
        self._register_default(ConfigCategory.GLOBAL, **kwargs)

    def register_guild(self, **kwargs):
        """Register default values on a per-guild level.

        See `register_global` for more details.
        """
        self._register_default(ConfigCategory.GUILD, **kwargs)

    def register_channel(self, **kwargs):
        """Register default values on a per-channel level.

        See `register_global` for more details.
        """
        # We may need to add a voice channel category later
        self._register_default(ConfigCategory.CHANNEL, **kwargs)

    def register_role(self, **kwargs):
        """Registers default values on a per-role level.

        See `register_global` for more details.
        """
        self._register_default(ConfigCategory.ROLE, **kwargs)

    def register_user(self, **kwargs):
        """Registers default values on a per-user level.

        This means that each user's data is guild-independent.

        See `register_global` for more details.
        """
        self._register_default(ConfigCategory.USER, **kwargs)

    def register_member(self, **kwargs):
        """Registers default values on a per-member level.

        This means that each user's data is guild-dependent.

        See `register_global` for more details.
        """
        self._register_default(ConfigCategory.MEMBER, **kwargs)

    def register_custom(self, group_identifier: str, **kwargs):
        """Registers default values for a custom group.

        See `register_global` for more details.
        """
        self._register_default(group_identifier, **kwargs)

    def init_custom(self, group_identifier: str, identifier_count: int):
        """
        Initializes a custom group for usage. This method must be called first!
        """
        if group_identifier in self.custom_groups:
            raise ValueError(f"Group identifier already registered: {group_identifier}")

        self.custom_groups[group_identifier] = identifier_count

    def _get_base_group(self, category: Union[ConfigCategory, str], *primary_keys: str) -> Group:
        pkey_len, is_custom = ConfigCategory.get_pkey_info(category, self.custom_groups)
        category = str(category)
        identifier_data = IdentifierData(
            uuid=self.unique_identifier,
            category=category,
            primary_key=primary_keys,
            identifiers=(),
            primary_key_len=pkey_len,
            is_custom=is_custom,
        )
        return Group(
            identifier_data=identifier_data,
            defaults=self.defaults.get(category, {}),
            driver=self.driver,
            force_registration=self.force_registration,
            config=self,
        )

    def guild(self, guild: discord.Guild) -> Group:
        """Returns a `Group` for the given guild.

        Parameters
        ----------
        guild : discord.Guild
            A guild object.

        Returns
        -------
        `Group <redbot.core.config.Group>`
            The guild's Group object.

        """
        return self._get_base_group(ConfigCategory.GUILD, str(guild.id))

    def channel(self, channel: discord.TextChannel) -> Group:
        """Returns a `Group` for the given channel.

        This does not discriminate between text and voice channels.

        Parameters
        ----------
        channel : `discord.abc.GuildChannel`
            A channel object.

        Returns
        -------
        `Group <redbot.core.config.Group>`
            The channel's Group object.

        """
        return self._get_base_group(ConfigCategory.CHANNEL, str(channel.id))

    def role(self, role: discord.Role) -> Group:
        """Returns a `Group` for the given role.

        Parameters
        ----------
        role : discord.Role
            A role object.

        Returns
        -------
        `Group <redbot.core.config.Group>`
            The role's Group object.

        """
        return self._get_base_group(ConfigCategory.ROLE, str(role.id))

    def user(self, user: discord.abc.User) -> Group:
        """Returns a `Group` for the given user.

        Parameters
        ----------
        user : discord.User
            A user object.

        Returns
        -------
        `Group <redbot.core.config.Group>`
            The user's Group object.

        """
        return self._get_base_group(ConfigCategory.USER, str(user.id))

    def member(self, member: discord.Member) -> Group:
        """Returns a `Group` for the given member.

        Parameters
        ----------
        member : discord.Member
            A member object.

        Returns
        -------
        `Group <redbot.core.config.Group>`
            The member's Group object.

        """
        return self._get_base_group(ConfigCategory.MEMBER, str(member.guild.id), str(member.id))

    def custom(self, group_identifier: str, *identifiers: str):
        """Returns a `Group` for the given custom group.

        Parameters
        ----------
        group_identifier : str
            Used to identify the custom group.
        identifiers : str
            The attributes necessary to uniquely identify an entry in the
            custom group. These are casted to `str` for you.

        Returns
        -------
        `Group <redbot.core.config.Group>`
            The custom group's Group object.

        """
        if group_identifier not in self.custom_groups:
            raise ValueError(f"Group identifier not initialized: {group_identifier}")
        return self._get_base_group(str(group_identifier), *map(str, identifiers))

    async def _all_from_scope(
        self, scope: Union[str, ConfigCategory]
    ) -> Dict[int, Dict[Any, Any]]:
        """Get a dict of all values from a particular scope of data.

        :code:`scope` must be one of the constants attributed to
        this class, i.e. :code:`GUILD`, :code:`MEMBER` et cetera.

        IDs as keys in the returned dict are casted to `int` for convenience.

        Default values are also mixed into the data if they have not yet been
        overwritten.
        """
        scope = str(scope)
        group = self._get_base_group(scope)
        ret = {}

        try:
            dict_ = await self.driver.get(group.identifier_data)
        except KeyError:
            pass
        else:
            for k, v in dict_.items():
                data = group.defaults
                data.update(v)
                ret[int(k)] = data

        return ret

    async def all_guilds(self) -> dict:
        """Get all guild data as a dict.

        Note
        ----
        The return value of this method will include registered defaults for
        values which have not yet been set.

        Returns
        -------
        dict
            A dictionary in the form {`int`: `dict`} mapping
            :code:`GUILD_ID -> data`.

        """
        return await self._all_from_scope(ConfigCategory.GUILD)

    async def all_channels(self) -> dict:
        """Get all channel data as a dict.

        Note
        ----
        The return value of this method will include registered defaults for
        values which have not yet been set.

        Returns
        -------
        dict
            A dictionary in the form {`int`: `dict`} mapping
            :code:`CHANNEL_ID -> data`.

        """
        return await self._all_from_scope(ConfigCategory.CHANNEL)

    async def all_roles(self) -> dict:
        """Get all role data as a dict.

        Note
        ----
        The return value of this method will include registered defaults for
        values which have not yet been set.

        Returns
        -------
        dict
            A dictionary in the form {`int`: `dict`} mapping
            :code:`ROLE_ID -> data`.

        """
        return await self._all_from_scope(ConfigCategory.ROLE)

    async def all_users(self) -> dict:
        """Get all user data as a dict.

        Note
        ----
        The return value of this method will include registered defaults for
        values which have not yet been set.

        Returns
        -------
        dict
            A dictionary in the form {`int`: `dict`} mapping
            :code:`USER_ID -> data`.

        """
        return await self._all_from_scope(ConfigCategory.USER)

    @staticmethod
    def _all_members_from_guild(group: Group, guild_data: dict) -> dict:
        ret = {}
        for member_id, member_data in guild_data.items():
            new_member_data = group.defaults
            new_member_data.update(member_data)
            ret[int(member_id)] = new_member_data
        return ret

    async def all_members(self, guild: discord.Guild = None) -> dict:
        """Get data for all members.

        If :code:`guild` is specified, only the data for the members of that
        guild will be returned. As such, the dict will map
        :code:`MEMBER_ID -> data`. Otherwise, the dict maps
        :code:`GUILD_ID -> MEMBER_ID -> data`.

        Note
        ----
        The return value of this method will include registered defaults for
        values which have not yet been set.

        Parameters
        ----------
        guild : `discord.Guild`, optional
            The guild to get the member data from. Can be omitted if data
            from every member of all guilds is desired.

        Returns
        -------
        dict
            A dictionary of all specified member data.

        """
        ret = {}
        if guild is None:
            group = self._get_base_group(ConfigCategory.MEMBER)
            try:
                dict_ = await self.driver.get(group.identifier_data)
            except KeyError:
                pass
            else:
                for guild_id, guild_data in dict_.items():
                    ret[int(guild_id)] = self._all_members_from_guild(group, guild_data)
        else:
            group = self._get_base_group(ConfigCategory.MEMBER, str(guild.id))
            try:
                guild_data = await self.driver.get(group.identifier_data)
            except KeyError:
                pass
            else:
                ret = self._all_members_from_guild(group, guild_data)
        return ret

    async def _clear_scope(self, *scopes: Union[str, ConfigCategory]):
        """Clear all data in a particular scope.

        The only situation where a second scope should be passed in is if
        member data from a specific guild is being cleared.

        If no scopes are passed, then all data is cleared from every scope.

        Parameters
        ----------
        *scopes : str, optional
            The scope of the data. Generally only one scope needs to be
            provided, a second only necessary for clearing member data
            of a specific guild.

            **Leaving blank removes all data from this Config instance.**

        """
        if not scopes:
            # noinspection PyTypeChecker
            identifier_data = IdentifierData(self.unique_identifier, "", (), (), 0)
            group = Group(identifier_data, defaults={}, driver=self.driver, config=self)
        else:
            group = self._get_base_group(*scopes)
        await group.clear()

    async def clear_all(self):
        """Clear all data from this Config instance.

        This resets all data to its registered defaults.

        .. important::

            This cannot be undone.

        """
        await self._clear_scope()

    async def clear_all_globals(self):
        """Clear all global data.

        This resets all global data to its registered defaults.
        """
        await self._clear_scope(ConfigCategory.GLOBAL)

    async def clear_all_guilds(self):
        """Clear all guild data.

        This resets all guild data to its registered defaults.
        """
        await self._clear_scope(ConfigCategory.GUILD)

    async def clear_all_channels(self):
        """Clear all channel data.

        This resets all channel data to its registered defaults.
        """
        await self._clear_scope(ConfigCategory.CHANNEL)

    async def clear_all_roles(self):
        """Clear all role data.

        This resets all role data to its registered defaults.
        """
        await self._clear_scope(ConfigCategory.ROLE)

    async def clear_all_users(self):
        """Clear all user data.

        This resets all user data to its registered defaults.
        """
        await self._clear_scope(ConfigCategory.USER)

    async def clear_all_members(self, guild: discord.Guild = None):
        """Clear all member data.

        This resets all specified member data to its registered defaults.

        Parameters
        ----------
        guild : `discord.Guild`, optional
            The guild to clear member data from. Omit to clear member data from
            all guilds.

        """
        if guild is not None:
            await self._clear_scope(ConfigCategory.MEMBER, str(guild.id))
            return
        await self._clear_scope(ConfigCategory.MEMBER)

    async def clear_all_custom(self, category: str):
        """Clear all custom group data.

        This resets all custom group data to its registered defaults.

        Parameters
        ----------
        category : str
            The identifier for the custom group. This is casted to
            `str` for you.

        """
        await self._clear_scope(str(category))

    def get_guilds_lock(self) -> asyncio.Lock:
        """Get a lock for all guild data.

        Returns
        -------
        asyncio.Lock
        """
        return self.get_custom_lock(ConfigCategory.GUILD)

    def get_channels_lock(self) -> asyncio.Lock:
        """Get a lock for all channel data.

        Returns
        -------
        asyncio.Lock
        """
        return self.get_custom_lock(ConfigCategory.CHANNEL)

    def get_roles_lock(self) -> asyncio.Lock:
        """Get a lock for all role data.

        Returns
        -------
        asyncio.Lock
        """
        return self.get_custom_lock(ConfigCategory.ROLE)

    def get_users_lock(self) -> asyncio.Lock:
        """Get a lock for all user data.

        Returns
        -------
        asyncio.Lock
        """
        return self.get_custom_lock(ConfigCategory.USER)

    def get_members_lock(self, guild: Optional[discord.Guild] = None) -> asyncio.Lock:
        """Get a lock for all member data.

        Parameters
        ----------
        guild : Optional[discord.Guild]
            The guild containing the members whose data you want to
            lock. Omit to lock all data for all members in all guilds.

        Returns
        -------
        asyncio.Lock
        """
        if guild is None:
            return self.get_custom_lock(ConfigCategory.GUILD)
        else:
            id_data = IdentifierData(self.uuid, ConfigCategory.MEMBER, (str(guild.id),), (), 2)
            return self._lock_cache.setdefault(id_data, asyncio.Lock())

    def get_custom_lock(self, category: Union[str, ConfigCategory]) -> asyncio.Lock:
        """Get a lock for all data in a custom scope.

        Parameters
        ----------
        category : Union[str, ConfigCategory]
            The group identifier for the custom scope you want to lock.

        Returns
        -------
        asyncio.Lock
        """
        category = str(category)
        id_data = IdentifierData(
            self.uuid,
            category,
            (),
            (),
            *ConfigCategory.get_pkey_info(category, self.custom_groups),
        )
        return self._lock_cache.setdefault(id_data, asyncio.Lock())


def get_latest_confs() -> Tuple["Config"]:
    global _retrieved
    ret = set(_config_cache.values()) - set(_retrieved)
    _retrieved |= ret
    # noinspection PyTypeChecker
    return tuple(ret)
