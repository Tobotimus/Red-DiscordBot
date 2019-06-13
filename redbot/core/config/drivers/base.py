import abc
import asyncio
from typing import Tuple, Dict, Any, Union, List, AsyncIterator, Type, Optional, Iterable

from ..identifier_data import IdentifierData
from ..utils import ConfigCategory, JsonSerializable
from ...errors import StoredTypeError

__all__ = ["BaseDriver"]


class BaseDriver(abc.ABC):
    def __init__(self, cog_name: str, identifier: str, **kwargs):
        self.cog_name = cog_name
        self.unique_cog_identifier = identifier

    @classmethod
    @abc.abstractmethod
    async def initialize(cls, **storage_details) -> None:
        """
        Initialize this driver.

        Parameters
        ----------
        **storage_details
            The storage details required to initialize this driver.
            Should be the same as :func:`data_manager.storage_details`

        Raises
        ------
        MissingExtraRequirements
            If initializing the driver requires an extra which isn't
            installed.

        """
        raise NotImplementedError

    @classmethod
    @abc.abstractmethod
    async def teardown(cls) -> None:
        """
        Tear down this driver.
        """
        raise NotImplementedError

    @staticmethod
    @abc.abstractmethod
    def get_config_details() -> Dict[str, Any]:
        """
        Asks users for additional configuration information necessary
        to use this config driver.

        Returns
        -------
        Dict[str, Any]
            Dictionary of configuration details.
        """
        raise NotImplementedError

    @abc.abstractmethod
    async def get(self, identifier_data: IdentifierData) -> JsonSerializable:
        """
        Finds the value indicate by the given identifiers.

        Parameters
        ----------
        identifier_data

        Returns
        -------
        Any
            Stored value.
        """
        raise NotImplementedError

    @abc.abstractmethod
    async def set(self, identifier_data: IdentifierData, value: JsonSerializable = None) -> None:
        """
        Sets the value of the key indicated by the given identifiers.

        Parameters
        ----------
        identifier_data
        value
            Any JSON serializable python object.
        """
        raise NotImplementedError

    @abc.abstractmethod
    async def clear(self, identifier_data: IdentifierData) -> None:
        """
        Clears out the value specified by the given identifiers.

        Equivalent to using ``del`` on a dict.

        Parameters
        ----------
        identifier_data
        """
        raise NotImplementedError

    async def inc(
        self,
        identifier_data: IdentifierData,
        value: Union[int, float],
        default: Union[int, float],
        *,
        lock: asyncio.Lock,
    ) -> Union[int, float]:
        """
        Increments the value specified by the given identifiers.

        Config should make the guarantee that the value to write to is a number, if it's not,
        this method should throw an error.

        Parameters
        ----------
        identifier_data
        value
        default
        lock
        """
        async with lock:
            try:
                existing_value = await self.get(identifier_data)
            except KeyError:
                existing_value = default
            else:
                if not isinstance(existing_value, (int, float)):
                    raise StoredTypeError(f"Cannot increment non-numeric value {existing_value}")

            new_value = existing_value + value
            await self.set(identifier_data, new_value)
        return new_value

    async def toggle(
        self, identifier_data: IdentifierData, default: bool, *, lock: asyncio.Lock
    ) -> bool:
        """
        Toggles the value specified by the given identifiers.

        Config should make the guarantee that the value to write to is a boolean, if it's not,
        this method should throw an error.

        Parameters
        ----------
        identifier_data
        default
        lock
        """
        async with lock:
            try:
                existing_value = await self.get(identifier_data)
            except KeyError:
                existing_value = default
            else:
                if not isinstance(existing_value, bool):
                    raise StoredTypeError(f"Cannot toggle non-boolean value {existing_value}")

            new_value = not existing_value
            await self.set(identifier_data, new_value)
        return new_value

    async def extend(
        self,
        identifier_data: IdentifierData,
        value: Iterable[JsonSerializable],
        default: List[JsonSerializable],
        *,
        lock: asyncio.Lock,
        max_length: Optional[int] = None,
        extend_left: bool = False,
    ) -> List[JsonSerializable]:
        async with lock:
            try:
                existing_value = await self.get(identifier_data)
            except KeyError:
                existing_value = default
            else:
                if not isinstance(existing_value, list):
                    raise StoredTypeError(f"Cannot extend non-array value {existing_value}")

            if extend_left is True:
                existing_value[:] = [*value, *existing_value]
            else:
                existing_value.extend(value)

            if max_length is not None:
                oversize_by = len(existing_value) - max_length
                if oversize_by > 0:
                    if extend_left is False:
                        existing_value[:] = existing_value[oversize_by:]
                    else:
                        existing_value[:] = existing_value[:max_length]

            await self.set(identifier_data, existing_value)
        return existing_value

    async def insert(
        self,
        identifier_data: IdentifierData,
        index: int,
        value: JsonSerializable,
        default: List[JsonSerializable],
        *,
        lock: asyncio.Lock,
        max_length: Optional[int] = None,
    ) -> List[JsonSerializable]:
        async with lock:
            try:
                existing_value = await self.get(identifier_data)
            except KeyError:
                existing_value = default

            try:
                existing_value.insert(index, value)
            except AttributeError:
                raise StoredTypeError(
                    f"Cannot insert into non-array value {existing_value}"
                ) from None

            if max_length is not None and len(existing_value) > max_length:
                del existing_value[-1]
            await self.set(identifier_data, existing_value)
        return existing_value

    async def index(self, identifier_data: IdentifierData, value: JsonSerializable) -> int:
        existing_value = await self.get(identifier_data)
        try:
            return existing_value.index(value)
        except AttributeError:
            raise StoredTypeError(
                f"Cannot call index() on non-array value {existing_value}"
            ) from None

    async def at(self, identifier_data: IdentifierData, index: int) -> JsonSerializable:
        value = await self.get(identifier_data)
        if not isinstance(value, list):
            raise StoredTypeError(f"Cannot do element-access on non-array value {value}")

        return value[index]

    async def set_at(
        self,
        identifier_data: IdentifierData,
        index: int,
        value: JsonSerializable,
        default: List[JsonSerializable],
        *,
        lock: asyncio.Lock,
    ) -> None:
        async with lock:
            try:
                existing_value = await self.get(identifier_data)
            except KeyError:
                existing_value = default
            if not isinstance(existing_value, list):
                raise StoredTypeError(f"Cannot do element-assignment on non-array value {value}")

            existing_value[index] = value
            await self.set(identifier_data, existing_value)

    async def object_contains(self, identifier_data: IdentifierData, item: str) -> bool:
        value = await self.get(identifier_data)
        if not isinstance(value, dict):
            raise StoredTypeError(f"Cannot call object_contains() on non-object value {value}")

        return item in value

    async def array_contains(
        self, identifier_data: IdentifierData, item: JsonSerializable
    ) -> bool:
        value = await self.get(identifier_data)
        if not isinstance(value, list):
            raise StoredTypeError(f"Cannot call array_contains() on non-array value {value}")

        return item in value

    @classmethod
    @abc.abstractmethod
    def aiter_cogs(cls) -> AsyncIterator[Tuple[str, str]]:
        """Get info for cogs which have data stored on this backend.

        Yields
        ------
        Tuple[str, str]
            Asynchronously yields (cog_name, cog_identifier) tuples.

        """
        raise NotImplementedError

    @classmethod
    async def migrate_to(
        cls,
        new_driver_cls: Type["BaseDriver"],
        all_custom_group_data: Dict[str, Dict[str, Dict[str, int]]],
    ) -> None:
        """Migrate data from this backend to another.

        Both drivers must be initialized beforehand.

        This will only move the data - no instance metadata is modified
        as a result of this operation.

        Parameters
        ----------
        new_driver_cls
            Subclass of `BaseDriver`.
        all_custom_group_data : Dict[str, Dict[str, Dict[str, int]]]
            Dict mapping cog names, to cog IDs, to custom groups, to
            primary key lengths.

        """
        # Backend-agnostic method of migrating from one driver to another.
        async for cog_name, cog_id in cls.aiter_cogs():
            this_driver = cls(cog_name, cog_id)
            other_driver = new_driver_cls(cog_name, cog_id)
            custom_group_data = all_custom_group_data.get(cog_name, {}).get(cog_id, {})
            exported_data = await this_driver.export_data(custom_group_data)
            await other_driver.import_data(exported_data, custom_group_data)

    @classmethod
    async def delete_all_data(cls, **kwargs) -> None:
        """Delete all data being stored by this driver.

        The driver must be initialized before this operation.

        The BaseDriver provides a generic method which may be overriden
        by subclasses.

        Parameters
        ----------
        **kwargs
            Driver-specific kwargs to change the way this method
            operates.

        """
        async for cog_name, cog_id in cls.aiter_cogs():
            driver = cls(cog_name, cog_id)
            await driver.clear(IdentifierData(cog_name, cog_id, "", (), (), 0))

    @staticmethod
    def _split_primary_key(
        category: Union[ConfigCategory, str],
        custom_group_data: Dict[str, int],
        data: Dict[str, Any],
    ) -> List[Tuple[Tuple[str, ...], Dict[str, Any]]]:
        pkey_len = ConfigCategory.get_pkey_info(category, custom_group_data)[0]
        if pkey_len == 0:
            return [((), data)]

        def flatten(levels_remaining, currdata, parent_key=()):
            items = []
            for _k, _v in currdata.items():
                new_key = parent_key + (_k,)
                if levels_remaining > 1:
                    items.extend(flatten(levels_remaining - 1, _v, new_key).items())
                else:
                    items.append((new_key, _v))
            return dict(items)

        ret = []
        for k, v in flatten(pkey_len, data).items():
            ret.append((k, v))
        return ret

    async def export_data(
        self, custom_group_data: Dict[str, int]
    ) -> List[Tuple[str, Dict[str, Any]]]:
        categories = [str(c) for c in ConfigCategory]
        categories.extend(custom_group_data.keys())

        ret = []
        for c in categories:
            ident_data = IdentifierData(
                self.cog_name,
                self.unique_cog_identifier,
                c,
                (),
                (),
                *ConfigCategory.get_pkey_info(c, custom_group_data),
            )
            try:
                data = await self.get(ident_data)
            except KeyError:
                continue
            ret.append((c, data))
        return ret

    async def import_data(
        self, cog_data: List[Tuple[str, Dict[str, Any]]], custom_group_data: Dict[str, int]
    ) -> None:
        for category, all_data in cog_data:
            splitted_pkey = self._split_primary_key(category, custom_group_data, all_data)
            for pkey, data in splitted_pkey:
                ident_data = IdentifierData(
                    self.cog_name,
                    self.unique_cog_identifier,
                    category,
                    pkey,
                    (),
                    *ConfigCategory.get_pkey_info(category, custom_group_data),
                )
                await self.set(ident_data, data)
