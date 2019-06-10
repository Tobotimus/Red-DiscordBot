import asyncio
import pickle
from typing import Any, Awaitable, AsyncContextManager, Optional, TYPE_CHECKING, TypeVar, Union

from .identifier_data import IdentifierData
from .utils import str_key_dict

if TYPE_CHECKING:
    from .config import Config

__all__ = ["ValueContextManager", "Value"]

_T = TypeVar("_T")


class ValueContextManager(Awaitable[_T], AsyncContextManager[_T]):
    """Context manager implementation of config values.

    This class allows mutable config values to be both "get" and "set" from
    within an async context manager.

    The context manager can only be used to get and set a mutable data type,
    i.e. `dict`s or `list`s. This is because this class's ``raw_value``
    attribute must contain a reference to the object being modified within the
    context manager.

    It should also be noted that the use of this context manager implies
    the acquisition of the value's lock when the ``acquire_lock`` kwarg
    to ``__init__`` is set to ``True``.
    """

    def __init__(self, value_obj: "Value", coro: Awaitable[Any], *, acquire_lock: bool):
        self.value_obj = value_obj
        self.coro = coro
        self.raw_value = None
        self.__original_value = None
        self.__acquire_lock = acquire_lock
        self.__lock = self.value_obj.get_lock()

    def __await__(self):
        return self.coro.__await__()

    async def __aenter__(self):
        if self.__acquire_lock is True:
            await self.__lock.acquire()
        self.raw_value = await self
        if not isinstance(self.raw_value, (list, dict)):
            raise TypeError(
                "Type of retrieved value must be mutable (i.e. "
                "list or dict) in order to use a config value as "
                "a context manager."
            )
        self.__original_value = pickle.loads(pickle.dumps(self.raw_value, -1))
        return self.raw_value

    async def __aexit__(self, exc_type, exc, tb):
        try:
            if isinstance(self.raw_value, dict):
                raw_value = str_key_dict(self.raw_value)
            else:
                raw_value = self.raw_value
            if raw_value != self.__original_value:
                await self.value_obj.set(self.raw_value)
        finally:
            if self.__acquire_lock is True:
                self.__lock.release()


class Value:
    """A singular "value" of data.

    Attributes
    ----------
    identifier_data : IdentifierData
        Information on identifiers for this value.

    """

    def __init__(self, identifier_data: IdentifierData, config: "Config"):
        self.identifier_data = identifier_data
        self._config = config

    @property
    def default(self):
        """The default value for the data element that `identifiers`
        points at.
        """
        inner = self._config.defaults
        try:
            inner = inner[self.identifier_data.category]
            for key in self.identifier_data.identifiers:
                inner = inner[key]
        except KeyError:
            return
        else:
            return inner

    def get_lock(self) -> asyncio.Lock:
        """Get a lock to create a critical region where this value is accessed.

        When using this lock, make sure you either use it with the
        ``async with`` syntax, or if that's not feasible, ensure you
        keep a reference to it from the acquisition to the release of
        the lock. That is, if you can't use ``async with`` syntax, use
        the lock like this::

            lock = config.foo.get_lock()
            await lock.acquire()
            # Do stuff...
            lock.release()

        Do not use it like this::

            await config.foo.get_lock().acquire()
            # Do stuff...
            config.foo.get_lock().release()

        Doing it the latter way will likely cause an error, as the
        acquired lock will be cleaned up by the garbage collector before
        it is released, meaning the second call to ``get_lock()`` will
        return a different lock to the first call.

        Returns
        -------
        asyncio.Lock
            A lock which is weakly cached for this value object.

        """
        # noinspection PyProtectedMember
        return self._config._lock_cache.setdefault(self.identifier_data, asyncio.Lock())

    async def _get(self, default: Any = ..., **kwargs):
        try:
            ret = await self._config.driver.get(self.identifier_data)
        except KeyError:
            return default if default is not ... else self.default
        return ret

    def __call__(self, default=..., *, acquire_lock: bool = True) -> ValueContextManager[Any]:
        """Get the literal value of this data element.

        Each `Value` object is created by the `Group.__getattr__` method. The
        "real" data of the `Value` object is accessed by this method. It is a
        replacement for a :code:`get()` method.

        The return value of this method can also be used as an asynchronous
        context manager, i.e. with :code:`async with` syntax. This can only be
        used on values which are mutable (namely lists and dicts), and will
        set the value with its changes on exit of the context manager. It will
        also acquire this value's lock to protect the critical region inside
        this context manager's body, unless the ``acquire_lock`` keyword
        argument is set to ``False``.

        Example
        -------
        ::

            foo = await conf.guild(some_guild).foo()

            # Is equivalent to this

            group_obj = conf.guild(some_guild)
            value_obj = conf.foo
            foo = await value_obj()

        .. important::

            This is now, for all intents and purposes, a coroutine.

        Parameters
        ----------
        default : `object`, optional
            This argument acts as an override for the registered default
            provided by `default`. This argument is ignored if its
            value is :code:`...`.

        Other Parameters
        ----------------
        acquire_lock : bool
            Set to ``False`` to disable the acquisition of the value's
            lock over the context manager body. Defaults to ``True``.
            Has no effect when not used as a context manager.

        Returns
        -------
        `awaitable` mixed with `asynchronous context manager`
            A coroutine object mixed in with an async context manager. When
            awaited, this returns the raw data value. When used in :code:`async
            with` syntax, on gets the value on entrance, and sets it on exit.

        """
        return ValueContextManager(self, self._get(default), acquire_lock=acquire_lock)

    async def set(self, value):
        """Set the value of the data elements pointed to by `identifiers`.

        Example
        -------
        ::

            # Sets global value "foo" to False
            await conf.foo.set(False)

            # Sets guild specific value of "bar" to True
            await conf.guild(some_guild).bar.set(True)

        Parameters
        ----------
        value
            The new literal value of this attribute.

        """
        if isinstance(value, dict):
            value = str_key_dict(value)
        await self._config.driver.set(self.identifier_data, value=value)

    async def inc(self, value, default: Optional[Union[int, float]] = None) -> Union[int, float]:
        """Increment and return the value of the data element pointed to by `identifiers`.

        Example
        -------
        ::
            # Increments and returns a global value "foo" by 3.
            new = await conf.foo.inc(3)
            # You can also decrement a value using by negative numbers
            new = await conf.foo.inc(-3)
            # Floats are also supported
            new = await conf.foo.inc(3.834)

        Parameters
        ----------
        value : Union[int, float]
            Number that will be used to increment a value.
        default : Optional[int, float]
            An override for the registered default.

        Returns
        -------
        Union[int, float]
            The stored value plus the value given as an integer or
            float.

        """
        if default is None:
            default = self.default

        if not isinstance(default, (int, float)):
            raise ValueError("You must register or provide a numeric default to use this method.")

        return await self._config.driver.inc(self.identifier_data, value, default=default)

    async def toggle(self, default: Optional[bool] = None) -> bool:
        """Toggles a Boolean value between True and False.

        Example
        -------
        ::
            # Assume the global value "foo" is currently True.
            # The following will change it to False, and return the result.
            new = await conf.foo.toggle()

        Parameters
        ----------
        default : Optional[bool]
            An override for the registered default.

        Returns
        -------
        bool
            The opposite of the originally stored value.
        """
        if default is None:
            default = self.default

        if not isinstance(default, bool):
            raise ValueError("You must register or provide a boolean default to use this method.")

        return await self._config.driver.toggle(self.identifier_data, default=default)

    async def clear(self):
        """
        Clears the value from record for the data element pointed to by `identifiers`.
        """
        await self._config.driver.clear(self.identifier_data)
