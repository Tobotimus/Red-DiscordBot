import functools
import pickle
from collections import defaultdict
from typing import (
    Dict,
    TYPE_CHECKING,
    Union,
    Type,
    Optional,
    Callable,
    Sequence,
    TypeVar,
    Iterable,
)

import discord

from .array import Array
from .identifier_data import IdentifierData
from .utils import str_key_dict, ConfigCategory, JsonSerializable
from .value import Value, ValueContextManager, MutableValue

if TYPE_CHECKING:
    from .config import Config

__all__ = ["Group", "ModelGroup", "model_group"]

_T = TypeVar("_T")


class Group(MutableValue):
    """
    Represents a group of data, composed of more `Group` or `Value` objects.

    Inherits from `Value` which means that all of the attributes and methods
    available in `Value` are also available when working with a `Group` object.
    """

    @property
    def defaults(self):
        default = self.default
        if default is None:
            return {}
        else:
            return default

    async def _get(
        self, default: Dict[str, JsonSerializable] = ..., **kwargs
    ) -> Dict[str, JsonSerializable]:
        default = default if default is not ... else self.defaults
        num_pkeys = len(self.identifier_data.primary_key)
        if num_pkeys < self.identifier_data.primary_key_len:
            passed_default = {}
        else:
            passed_default = default
        raw = await super()._get(passed_default)
        if isinstance(raw, dict):
            return self.__nested_update(
                raw, default, num_pkeys, kwargs.get("int_primary_keys", False)
            )
        else:
            return raw

    def __getitem__(
        self, item: Union[str, int, Iterable[Union[str, int]]]
    ) -> Union["Group", Value]:
        if len(self.identifier_data.primary_key) < self.identifier_data.primary_key_len:
            item_adder = self.identifier_data.add_primary_key
        else:
            item_adder = self.identifier_data.add_identifier
        if isinstance(item, (str, int)):
            new_identifier_data = item_adder(str(item))
        else:
            new_identifier_data = item_adder(*map(str, item))

        default_type = self.__get_default_type(new_identifier_data)
        if default_type is None and self._config.force_registration:
            raise AttributeError("'{}' is not a valid registered Group or value.".format(item))
        else:
            value_cls = _VALUE_CLASS_MAPPING[default_type]
            return value_cls(new_identifier_data, self._config)

    def __getattr__(self, item: str) -> Union["Group", Value]:
        """Get an attribute of this group.

        This special method is called whenever dot notation is used on this
        object.

        Parameters
        ----------
        item : str
            The name of the attribute being accessed.

        Returns
        -------
        `Group` or `Value`
            A child value of this Group. This, of course, can be another
            `Group`, due to Config's composite pattern.

        Raises
        ------
        AttributeError
            If the attribute has not been registered and `force_registration`
            is set to :code:`True`.

        """
        return self[item]

    async def clear_raw(self, *nested_path: JsonSerializable):
        """
        Allows a developer to clear data as if it was stored in a standard
        Python dictionary.

        For example::

            await conf.clear_raw("foo", "bar")

            # is equivalent to

            data = {"foo": {"bar": None}}
            del data["foo"]["bar"]

        Parameters
        ----------
        nested_path : JsonSerializable
            Multiple arguments that mirror the arguments passed in for nested
            dict access. These are casted to `str` for you.
        """
        path = tuple(str(p) for p in nested_path)
        identifier_data = self.identifier_data.add_identifier(*path)
        await self._config.driver.clear(identifier_data)

    def __get_default_type(self, id_data: IdentifierData) -> Optional[Type[JsonSerializable]]:
        if len(id_data.primary_key) < id_data.primary_key_len:
            return dict

        try:
            inner = self._config.defaults[id_data.category]
            for key in id_data.identifiers:
                inner = inner[key]
        except KeyError:
            return
        else:
            return type(inner)

    @discord.utils.deprecated("square-bracket syntax")
    def get_attr(self, item: Union[int, str]):
        """Manually get an attribute of this Group.

        This is available to use as an alternative to using normal Python
        attribute access. It may be required if you find a need for dynamic
        attribute access.

        .. deprecated:: 3.2
            Use square-bracket syntax (`Group.__getitem__`) instead.

        Example
        -------
        A possible use case::

            @commands.command()
            async def some_command(self, ctx, item: str):
                user = ctx.author

                # Where the value of item is the name of the data field in Config
                await ctx.send(await self.conf.user(user).get_attr(item).foo())

        Parameters
        ----------
        item : str
            The name of the data field in `Config`. This is casted to
            `str` for you.

        Returns
        -------
        `Value` or `Group`
            The attribute which was requested.

        """
        return self[item]

    async def get_raw(self, *nested_path: JsonSerializable, default=...):
        """
        Allows a developer to access data as if it was stored in a standard
        Python dictionary.

        For example::

            d = await conf.get_raw("foo", "bar")

            # is equivalent to

            data = {"foo": {"bar": "baz"}}
            d = data["foo"]["bar"]

        Note
        ----
        If retreiving a sub-group, the return value of this method will
        include registered defaults for values which have not yet been set.

        Parameters
        ----------
        nested_path : str
            Multiple arguments that mirror the arguments passed in for nested
            dict access. These are casted to `str` for you.
        default
            Default argument for the value attempting to be accessed. If the
            value does not exist the default will be returned.

        Returns
        -------
        JsonSerializable
            The value of the path requested.

        Raises
        ------
        KeyError
            If the value does not exist yet in Config's internal storage.

        """
        path = tuple(str(p) for p in nested_path)

        if default is ...:
            poss_default = self.defaults
            for ident in path:
                try:
                    poss_default = poss_default[ident]
                except KeyError:
                    break
            else:
                default = poss_default

        identifier_data = self.identifier_data.add_identifier(*path)
        try:
            raw = await self._config.driver.get(identifier_data)
        except KeyError:
            if default is not ...:
                return default
            raise
        else:
            if isinstance(default, dict):
                return self.__nested_update(
                    raw,
                    default,
                    len(identifier_data.primary_key) + len(identifier_data.identifiers),
                )
            return raw

    def all(
        self,
        *,
        acquire_lock: bool = True,
        with_defaults: bool = True,
        int_primary_keys: bool = False,
    ) -> ValueContextManager[Dict[Union[str, int], JsonSerializable]]:
        """Get a dictionary representation of this group's data.

        The return value of this method can also be used as an asynchronous
        context manager, i.e. with :code:`async with` syntax.

        Note
        ----
        The return value of this method will include registered defaults for
        values which have not yet been set.

        Other Parameters
        ----------------
        acquire_lock : bool
            Same as the ``acquire_lock`` keyword parameter in
            `Value.__call__`.

        Returns
        -------
        Dict[str, JsonSerializable]
            All of this Group's attributes, resolved as raw data values.

        """
        if with_defaults is False:
            default = {}
        else:
            default = ...
        return ValueContextManager(
            self,
            functools.partial(self._get, default, int_primary_keys=int_primary_keys),
            acquire_lock=acquire_lock,
        )

    def __nested_update(
        self,
        cur_data: Dict[str, JsonSerializable],
        defaults: Dict[str, JsonSerializable],
        cur_level: int,
        int_primary_keys: bool = False,
    ) -> Dict[str, JsonSerializable]:
        data_contains_pkeys = cur_level < self.identifier_data.primary_key_len
        if data_contains_pkeys is True:
            ret = {}
        else:
            ret = pickle.loads(pickle.dumps(defaults, -1))

        for key, value in cur_data.items():
            if data_contains_pkeys is True:
                if int_primary_keys is True:
                    key = int(key)
                ret[key] = self.__nested_update(value, defaults, cur_level + 1, int_primary_keys)
            elif isinstance(value, dict):
                ret[key] = self.__nested_update(value, defaults.get(key, {}), cur_level)
            else:
                ret[key] = value
        return ret

    async def set(self, value):
        if not isinstance(value, dict):
            raise TypeError("You may only set the value of a Group to be a dict.")
        await super().set(value)

    async def set_raw(self, *nested_path: JsonSerializable, value):
        """
        Allows a developer to set data as if it was stored in a standard
        Python dictionary.

        For example::

            await conf.set_raw("foo", "bar", value="baz")

            # is equivalent to

            data = {"foo": {"bar": None}}
            data["foo"]["bar"] = "baz"

        Parameters
        ----------
        nested_path : JsonSerializable
            Multiple arguments that mirror the arguments passed in for nested
            `dict` access. These are casted to `str` for you.
        value
            The value to store.
        """
        path = tuple(str(p) for p in nested_path)
        identifier_data = self.identifier_data.add_identifier(*path)
        if isinstance(value, dict):
            value = str_key_dict(value)
        await self._config.driver.set(identifier_data, value=value)

    async def contains(self, item: Union[str, int]) -> bool:
        return await self._config.driver.object_contains(self.identifier_data, str(item))


_VALUE_CLASS_MAPPING = defaultdict(lambda: Value, {dict: Group, list: Array})


class ModelGroup(Callable[[Union[_T, str, int, Sequence[Union[str, int]]]], Group], Group):
    def __init__(
        self,
        primary_key_getter: Callable[..., Sequence[str]],
        identifier_data: IdentifierData,
        config: "Config",
    ) -> None:
        super().__init__(identifier_data, config)
        self.__primary_key_getter = primary_key_getter

    def __call__(
        self, model: Union[_T, str, int, Sequence[Union[str, int]]] = ..., **kwargs
    ) -> Group:
        if model is ...:
            raise TypeError("__call__() missing 1 required positional argument: 'model'")

        primary_key = self.__primary_key_getter(self._config, model, **kwargs)
        new_identifier_data = self.identifier_data.add_primary_key(*primary_key)
        new_identifier_data = self.identifier_data.add_primary_key(*primary_key)

        return Group(identifier_data=new_identifier_data, config=self._config)


class _ModelGroupDescriptor:
    def __init__(
        self,
        primary_key_getter: Callable[..., Sequence[str]],
        category: Union[str, ConfigCategory],
    ) -> None:
        self._primary_key_getter = primary_key_getter
        self._category = str(category)

    def __get__(
        self, instance: Optional["Config"], owner: Type["Config"]
    ) -> Union[ModelGroup, "_ModelGroupDescriptor"]:
        if instance is None:
            return self

        return ModelGroup(
            self._primary_key_getter,
            identifier_data=IdentifierData(
                instance.cog_name,
                instance.unique_identifier,
                self._category,
                (),
                (),
                *ConfigCategory.get_pkey_info(self._category, instance.custom_groups),
            ),
            config=instance,
        )


def model_group(
    category: Union[str, ConfigCategory]
) -> Callable[[staticmethod], _ModelGroupDescriptor]:
    def decorator(method: Callable[..., Sequence[str]]) -> _ModelGroupDescriptor:
        return _ModelGroupDescriptor(method, category)

    return decorator
