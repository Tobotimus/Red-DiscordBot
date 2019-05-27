import collections
from copy import deepcopy
from typing import Any, Dict, TYPE_CHECKING, Union

from .identifier_data import IdentifierData
from .utils import str_key_dict
from .value import Value, ValueContextManager

if TYPE_CHECKING:
    from .config import Config

__all__ = ["Group"]


class Group(Value):
    """
    Represents a group of data, composed of more `Group` or `Value` objects.

    Inherits from `Value` which means that all of the attributes and methods
    available in `Value` are also available when working with a `Group` object.

    Attributes
    ----------
    defaults : `dict`
        All registered default values for this Group.
    force_registration : `bool`
        Same as `Config.force_registration`.
    driver : `BaseDriver`
        A reference to `Config.driver`.

    """

    def __init__(
        self,
        identifier_data: IdentifierData,
        defaults: dict,
        driver,
        config: "Config",
        force_registration: bool = False,
    ):
        self._defaults = defaults
        self.force_registration = force_registration
        self.driver = driver

        super().__init__(identifier_data, {}, self.driver, config)

    @property
    def defaults(self):
        return deepcopy(self._defaults)

    async def _get(self, default: Dict[str, Any] = ...) -> Dict[str, Any]:
        default = default if default is not ... else self.defaults
        raw = await super()._get(default)
        if isinstance(raw, dict):
            return self.nested_update(raw, default)
        else:
            return raw

    # noinspection PyTypeChecker
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
        is_group = self.is_group(item)
        is_value = not is_group and self.is_value(item)
        new_identifiers = self.identifier_data.add_identifier(item)
        if is_group:
            return Group(
                identifier_data=new_identifiers,
                defaults=self._defaults[item],
                driver=self.driver,
                force_registration=self.force_registration,
                config=self._config,
            )
        elif is_value:
            return Value(
                identifier_data=new_identifiers,
                default_value=self._defaults[item],
                driver=self.driver,
                config=self._config,
            )
        elif self.force_registration:
            raise AttributeError("'{}' is not a valid registered Group or value.".format(item))
        else:
            return Value(
                identifier_data=new_identifiers,
                default_value=None,
                driver=self.driver,
                config=self._config,
            )

    async def clear_raw(self, *nested_path: Any):
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
        nested_path : Any
            Multiple arguments that mirror the arguments passed in for nested
            dict access. These are casted to `str` for you.
        """
        path = tuple(str(p) for p in nested_path)
        identifier_data = self.identifier_data.add_identifier(*path)
        await self.driver.clear(identifier_data)

    def is_group(self, item: Any) -> bool:
        """A helper method for `__getattr__`. Most developers will have no need
        to use this.

        Parameters
        ----------
        item : Any
            See `__getattr__`.

        """
        default = self._defaults.get(str(item))
        return isinstance(default, dict)

    def is_value(self, item: Any) -> bool:
        """A helper method for `__getattr__`. Most developers will have no need
        to use this.

        Parameters
        ----------
        item : Any
            See `__getattr__`.

        """
        try:
            default = self._defaults[str(item)]
        except KeyError:
            return False

        return not isinstance(default, dict)

    def get_attr(self, item: Union[int, str]):
        """Manually get an attribute of this Group.

        This is available to use as an alternative to using normal Python
        attribute access. It may be required if you find a need for dynamic
        attribute access.

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
        if isinstance(item, int):
            item = str(item)
        return self.__getattr__(item)

    async def get_raw(self, *nested_path: Any, default=...):
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
        Any
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
            raw = await self.driver.get(identifier_data)
        except KeyError:
            if default is not ...:
                return default
            raise
        else:
            if isinstance(default, dict):
                return self.nested_update(raw, default)
            return raw

    def all(self, *, acquire_lock: bool = True) -> ValueContextManager[Dict[str, Any]]:
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
        dict
            All of this Group's attributes, resolved as raw data values.

        """
        return self(acquire_lock=acquire_lock)

    def nested_update(
        self, current: collections.Mapping, defaults: Dict[str, Any] = ...
    ) -> Dict[str, Any]:
        """Robust updater for nested dictionaries

        If no defaults are passed, then the instance attribute 'defaults'
        will be used.
        """
        if defaults is ...:
            defaults = self.defaults

        for key, value in current.items():
            if isinstance(value, collections.Mapping):
                result = self.nested_update(value, defaults.get(key, {}))
                defaults[key] = result
            else:
                defaults[key] = deepcopy(current[key])
        return defaults

    async def set(self, value):
        if not isinstance(value, dict):
            raise ValueError("You may only set the value of a group to be a dict.")
        await super().set(value)

    async def set_raw(self, *nested_path: Any, value):
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
        nested_path : Any
            Multiple arguments that mirror the arguments passed in for nested
            `dict` access. These are casted to `str` for you.
        value
            The value to store.
        """
        path = tuple(str(p) for p in nested_path)
        identifier_data = self.identifier_data.add_identifier(*path)
        if isinstance(value, dict):
            value = str_key_dict(value)
        await self.driver.set(identifier_data, value=value)
