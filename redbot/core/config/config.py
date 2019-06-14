import asyncio
import pickle
from typing import Any, Dict, MutableMapping, Optional, Tuple, TypeVar, Union, Sequence, cast
import weakref

import discord

from .drivers import BaseDriver, get_driver
from .group import Group, model_group, ModelGroup, CustomGroup, _UnregisteredCustomGroup
from .identifier_data import IdentifierData
from .utils import ConfigCategory, JsonSerializable
from .value import ValueContextManager

__all__ = ["Config", "get_latest_confs"]

_T = TypeVar("_T")

_config_cache = weakref.WeakValueDictionary()
_retrieved = weakref.WeakSet()


class Config(Group):
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

    guild: ModelGroup[discord.Guild]
    channel: ModelGroup[discord.abc.GuildChannel]
    role: ModelGroup[discord.Role]
    user: ModelGroup[discord.abc.User]
    member: ModelGroup[discord.Member]

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
        defaults: Optional[dict] = None,
    ):
        self.cog_name = cog_name
        self.unique_identifier = unique_identifier

        self.driver: BaseDriver = driver
        self.force_registration = force_registration
        self._defaults: Dict[str, Dict[str, JsonSerializable]] = defaults or {}

        self.custom_groups: Dict[str, int] = {}
        self._lock_cache: MutableMapping[
            IdentifierData, asyncio.Lock
        ] = weakref.WeakValueDictionary()

        super().__init__(
            IdentifierData(
                cog_name=self.cog_name,
                uuid=self.unique_identifier,
                category=str(ConfigCategory.GLOBAL),
                primary_key=(),
                identifiers=(),
                primary_key_len=0,
                is_custom=False,
            ),
            config=self,
        )

    @property
    def all_defaults(self) -> Dict[str, Dict[str, JsonSerializable]]:
        return pickle.loads(pickle.dumps(self._defaults, -1))

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

    @model_group(ConfigCategory.GUILD)
    def guild(self, guild: Union[discord.Guild, int, str]) -> Sequence[str]:
        """Returns a `Group` for the given guild.

        Parameters
        ----------
        guild : discord.Guild
            A guild object.

        Returns
        -------
        Group
            The guild's Group object.

        """
        return self.__default_primary_key_getter(guild)

    @model_group(ConfigCategory.CHANNEL)
    def channel(self, channel: Union[discord.abc.GuildChannel, int, str]) -> Sequence[str]:
        """Returns a `Group` for the given channel.

        Parameters
        ----------
        channel : Union[discord.abc.GuildChannel, int, str]
            A channel object or ID.

        Returns
        -------
        Group
            The channel's Group object.

        """
        return self.__default_primary_key_getter(channel)

    @model_group(ConfigCategory.ROLE)
    def role(self, role: Union[discord.Role, int, str]) -> Sequence[str]:
        """Returns a `Group` for the given role.

        Parameters
        ----------
        role : Union[discord.Role, int, str]
            A role object or ID.

        Returns
        -------
        Group
            The role's Group object.

        """
        return self.__default_primary_key_getter(role)

    @model_group(ConfigCategory.USER)
    def user(self, user: Union[discord.abc.User, int, str]) -> Sequence[str]:
        """Returns a `Group` for the given user.

        Parameters
        ----------
        user : Union[discord.abc.User, int, str]
            A user object or ID.

        Returns
        -------
        Group
            The user's Group object.

        """
        return self.__default_primary_key_getter(user)

    @model_group(ConfigCategory.MEMBER)
    def member(
        self, member: Union[discord.Member, Tuple[Union[int, str], Union[int, str]]]
    ) -> Sequence[str]:
        """Returns a `Group` for the given member.

        Parameters
        ----------
        member : Union[discord.Member, Sequence[Union[int, str]]]
            A member object or sequence (guild_id, user_id).

        Returns
        -------
        Group
            The member's Group object.

        """
        try:
            guild_id = member.guild.id
            user_id = member.id
        except AttributeError:
            guild_id, user_id = member

        return str(guild_id), str(user_id)

    def custom(self, group_identifier: str, *identifiers: Any) -> Group:
        """Returns a `Group` for the given custom group.

        Parameters
        ----------
        group_identifier : str
            Used to identify the custom group.
        identifiers : str
            The attributes necessary to uniquely identify an entry in
            the custom group. These are casted to `str` for you.

        Returns
        -------
        Group
            The custom group's Group object.

        """
        if identifiers:
            if group_identifier not in self.custom_groups:
                raise ValueError(f"Group identifier not registered: {group_identifier}")
            return Group(
                IdentifierData(
                    cog_name=self.cog_name,
                    uuid=self.unique_identifier,
                    category=str(group_identifier),
                    primary_key=tuple(map(str, identifiers)),
                    identifiers=(),
                    primary_key_len=self.custom_groups[group_identifier],
                    is_custom=True,
                ),
                config=self,
            )
        else:
            # CustomGroup supports `register(N, **defaults)`
            if group_identifier not in self.custom_groups:
                return cast(CustomGroup, _UnregisteredCustomGroup(
                    IdentifierData(
                        cog_name=self.cog_name,
                        uuid=self.unique_identifier,
                        category=str(group_identifier),
                        primary_key=(),
                        identifiers=(),
                        primary_key_len=0,
                        is_custom=True,
                    ),
                    config=self,
                ))
            return CustomGroup(
                IdentifierData(
                    cog_name=self.cog_name,
                    uuid=self.unique_identifier,
                    category=str(group_identifier),
                    primary_key=(),
                    identifiers=(),
                    primary_key_len=self.custom_groups.get(group_identifier),
                    is_custom=True,
                ),
                config=self,
            )

    def register_global(self, **defaults: JsonSerializable) -> None:
        """Register default values for the global scope.

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
        self._register_default(ConfigCategory.GLOBAL, **defaults)

    @discord.utils.deprecated("Config.guild.register()")
    def register_guild(self, **kwargs):
        """Register default values on a per-guild level.

        See `register_global` for more details.
        """
        self.guild.register(**kwargs)

    @discord.utils.deprecated("Config.channel.register()")
    def register_channel(self, **kwargs):
        """Register default values on a per-channel level.

        See `register_global` for more details.
        """
        # We may need to add a voice channel category later
        self.channel.register(**kwargs)

    @discord.utils.deprecated("Config.role.register()")
    def register_role(self, **kwargs):
        """Registers default values on a per-role level.

        See `register_global` for more details.
        """
        self.role.register(**kwargs)

    @discord.utils.deprecated("Config.user.register()")
    def register_user(self, **kwargs):
        """Registers default values on a per-user level.

        This means that each user's data is guild-independent.

        See `register_global` for more details.
        """
        self.user.register(**kwargs)

    @discord.utils.deprecated("Config.member.register()")
    def register_member(self, **kwargs):
        """Registers default values on a per-member level.

        This means that each user's data is guild-dependent.

        See `register_global` for more details.
        """
        self.member.register(**kwargs)

    @discord.utils.deprecated("Config.custom(category).register()")
    def register_custom(self, group_identifier: str, **kwargs):
        """Registers default values for a custom group.

        See `register_global` for more details.
        """
        self._register_default(group_identifier, **kwargs)

    @discord.utils.deprecated("Config.custom(category).register()")
    def init_custom(self, group_identifier: str, identifier_count: int):
        """Initializes a custom group for usage.

        This method must be called first!
        """
        if group_identifier in self.custom_groups:
            raise ValueError(f"Group identifier already registered: {group_identifier}")

        self.custom_groups[group_identifier] = identifier_count

    @discord.utils.deprecated("Config.guild.all()")
    def all_guilds(self) -> ValueContextManager[Dict[str, JsonSerializable]]:
        """Get all guild data as a dict.

        .. deprecated:: 3.2
            Use ``Config.guild.all()`` instead.

        Note
        ----
        The return value of this method will include registered defaults
        for values which have not yet been set.

        Returns
        -------
        ValueContextManager[Dict[str, JsonSerializable]]
            A dictionary in the form {`int`: `dict`} mapping
            :code:`GUILD_ID -> data`.

        """
        return self.guild.all(acquire_lock=True, int_primary_keys=True)

    @discord.utils.deprecated("Config.channel.all()")
    def all_channels(self) -> ValueContextManager[Dict[str, JsonSerializable]]:
        """Get all channel data as a dict.

        .. deprecated:: 3.2
            Use ``Config.channel.all()`` instead.

        Note
        ----
        The return value of this method will include registered defaults
        for values which have not yet been set.

        Returns
        -------
        ValueContextManager[Dict[str, JsonSerializable]]
            A dictionary in the form {`int`: `dict`} mapping
            :code:`CHANNEL_ID -> data`.

        """
        return self.channel.all(acquire_lock=True, int_primary_keys=True)

    @discord.utils.deprecated("Config.role.all()")
    def all_roles(self) -> ValueContextManager[Dict[str, JsonSerializable]]:
        """Get all role data as a dict.

        .. deprecated:: 3.2
            Use ``Config.role.all()`` instead.

        Note
        ----
        The return value of this method will include registered defaults
        for values which have not yet been set.

        Returns
        -------
        ValueContextManager[Dict[str, JsonSerializable]]
            A dictionary in the form {`int`: `dict`} mapping
            :code:`ROLE_ID -> data`.

        """
        return self.role.all(acquire_lock=True, int_primary_keys=True)

    @discord.utils.deprecated("Config.user.all()")
    def all_users(self) -> ValueContextManager[Dict[str, JsonSerializable]]:
        """Get all user data as a dict.

        .. deprecated:: 3.2
            Use ``Config.user.all()`` instead.

        Note
        ----
        The return value of this method will include registered defaults
        for values which have not yet been set.

        Returns
        -------
        ValueContextManager[Dict[str, JsonSerializable]]
            A dictionary in the form {`int`: `dict`} mapping
            :code:`USER_ID -> data`.

        """
        return self.user.all(acquire_lock=True, int_primary_keys=True)

    @discord.utils.deprecated("Config.member.all() or Config.member[guild.id].all()")
    def all_members(
        self, guild: discord.Guild = None
    ) -> ValueContextManager[Dict[str, JsonSerializable]]:
        """Get data for all members.

        If :code:`guild` is specified, only the data for the members of that
        guild will be returned. As such, the dict will map
        :code:`MEMBER_ID -> data`. Otherwise, the dict maps
        :code:`GUILD_ID -> MEMBER_ID -> data`.

        .. deprecated:: 3.2
            Use ``Config.member.all()`` or
            ``Config.member[guild.id].all()`` instead.

        Note
        ----
        The return value of this method will include registered defaults
        for values which have not yet been set.

        Parameters
        ----------
        guild : `discord.Guild`, optional
            The guild to get the member data from. Can be omitted if
            data from every member of all guilds is desired.

        Returns
        -------
        ValueContextManager[Dict[str, JsonSerializable]]
            A dictionary of all specified member data.

        """
        if guild is not None:
            group = self.member[guild.id]
        else:
            group = self.member
        return group.all(acquire_lock=True, int_primary_keys=True)

    async def clear_all(self):
        """Clear all data from this Config instance.

        This resets all data to its registered defaults.

        .. important::

            This cannot be undone.

        """
        identifier_data = IdentifierData(self.cog_name, self.unique_identifier, "", (), (), 0)
        await Group(identifier_data, config=self).clear()

    @discord.utils.deprecated("Config.clear()")
    async def clear_all_globals(self):
        """Clear all global data.

        This resets all global data to its registered defaults.

        .. deprecated:: 3.2
            Use ``Config.clear()`` instead.

        """
        await self.clear()

    @discord.utils.deprecated("Config.guild.clear()")
    async def clear_all_guilds(self):
        """Clear all guild data.

        This resets all guild data to its registered defaults.

        .. deprecated:: 3.2
            Use ``Config.guild.clear()`` instead.

        """
        await self.guild.clear()

    @discord.utils.deprecated("Config.channel.clear()")
    async def clear_all_channels(self):
        """Clear all channel data.

        This resets all channel data to its registered defaults.

        .. deprecated:: 3.2
            Use ``Config.channel.clear()`` instead.

        """
        await self.channel.clear()

    @discord.utils.deprecated("Config.role.clear()")
    async def clear_all_roles(self):
        """Clear all role data.

        This resets all role data to its registered defaults.

        .. deprecated:: 3.2
            Use ``Config.role.clear()`` instead.

        """
        await self.role.clear()

    @discord.utils.deprecated("Config.user.clear()")
    async def clear_all_users(self):
        """Clear all user data.

        This resets all user data to its registered defaults.

        .. deprecated:: 3.2
            Use ``Config.user.clear()`` instead.

        """
        await self.user.clear()

    @discord.utils.deprecated("Config.member.clear() or Config.member[guild.id].clear()")
    async def clear_all_members(self, guild: discord.Guild = None):
        """Clear all member data.

        This resets all specified member data to its registered
        defaults.

        .. deprecated:: 3.2
            Use ``Config.member.clear()`` or
            ``Config.member[guild.id].clear()`` instead.

        Parameters
        ----------
        guild : Optional[discord.Guild]
            The guild to clear member data from. Omit to clear member
            data from all guilds.

        """
        if guild is not None:
            group = self.member[guild.id]
        else:
            group = self.member
        await group.clear()

    @discord.utils.deprecated("Config.custom(category).clear()")
    async def clear_all_custom(self, category: str):
        """Clear all custom group data.

        This resets all custom group data to its registered defaults.

        .. deprecated:: 3.2
            Use ``Config.custom(category).clear()`` instead.

        Parameters
        ----------
        category : str
            The identifier for the custom group. This is casted to
            `str` for you.

        """
        await self.custom(category).clear()

    def _register_default(
        self, category: Union[ConfigCategory, str], **kwargs: JsonSerializable
    ) -> None:
        category = str(category)
        defaults_dict = self._defaults.setdefault(category, {})

        data = pickle.loads(pickle.dumps(kwargs, -1))

        for k, v in data.items():
            to_add = self.__get_defaults_dict(k, v)
            self.__update_defaults(to_add, defaults_dict)

    @staticmethod
    def __default_primary_key_getter(
        model: Union[discord.abc.Snowflake, str, int]
    ) -> Sequence[str]:
        try:
            # noinspection PyUnresolvedReferences
            _id = model.id
        except AttributeError:
            _id = model

        return (str(_id),)

    @staticmethod
    def __get_defaults_dict(key: str, value) -> dict:
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
    def __update_defaults(
        to_add: Dict[str, JsonSerializable], _partial: Dict[str, JsonSerializable]
    ) -> None:
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
                    Config.__update_defaults(v, _partial=_partial[k])
                else:
                    _partial[k] = v
            else:
                _partial[k] = v


def get_latest_confs() -> Tuple["Config"]:
    global _retrieved
    ret = set(_config_cache.values()) - set(_retrieved)
    _retrieved |= ret
    # noinspection PyTypeChecker
    return tuple(ret)
