import asyncio
from typing import List, Optional, Iterable

from .utils import JsonSerializable
from .value import MutableValue

__all__ = ["Array"]


class Array(MutableValue):
    async def set(self, value: JsonSerializable) -> None:
        if not isinstance(value, list):
            raise TypeError("You may only set the value of an Array to be a list.")
        await super().set(value)

    async def append(
        self, obj: JsonSerializable, *, max_length: Optional[int] = None, append_left: bool = False
    ) -> List[JsonSerializable]:
        return await self.extend((obj,), max_length=max_length, extend_left=append_left)

    async def extend(
        self,
        iterable: Iterable[JsonSerializable],
        *,
        max_length: Optional[int] = None,
        extend_left: bool = False,
    ) -> List[JsonSerializable]:
        return await self._config.driver.extend(
            self.identifier_data,
            iterable,
            default=self.default,
            max_length=max_length,
            extend_left=extend_left,
            lock=self.get_lock(),
        )

    async def insert(
        self, index: int, obj: JsonSerializable, *, max_length: Optional[int] = None
    ) -> List[JsonSerializable]:
        return await self._config.driver.insert(
            self.identifier_data,
            index,
            obj,
            default=self.default,
            max_length=max_length,
            lock=self.get_lock(),
        )

    async def index(self, obj: JsonSerializable, *, with_defaults: bool = True) -> int:
        try:
            return await self._config.driver.index(self.identifier_data, obj)
        except KeyError:
            return with_defaults is True and self.default.index(obj)

    async def at(self, index: int, *, with_defaults: bool = True) -> JsonSerializable:
        try:
            return await self._config.driver.at(self.identifier_data, index)
        except KeyError:
            return with_defaults is True and self.default[index]

    async def set_at(self, index: int, value: JsonSerializable) -> None:
        await self._config.driver.set_at(
            self.identifier_data, index, value, default=self.default, lock=self.get_lock()
        )

    async def contains(self, item: JsonSerializable) -> bool:
        return await self._config.driver.array_contains(self.identifier_data, item)
