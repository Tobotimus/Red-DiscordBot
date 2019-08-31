import asyncio
import contextlib
from typing import (
    Union,
    Iterable,
    AsyncIterable,
    Optional,
    Generator,
    AsyncIterator,
    TypeVar,
    cast,
)

from tqdm import tqdm

__all__ = ["async_tqdm"]

_T = TypeVar("_T")


class _AsyncTqdm(AsyncIterator[_T], tqdm):
    def __init__(self, iterable: AsyncIterable[_T], *args, **kwargs) -> None:
        self.async_iterator = iterable.__aiter__()
        super().__init__(self.infinite_generator(), *args, **kwargs)
        self.iterator = cast(Generator[None, bool, None], iter(self))

    @staticmethod
    def infinite_generator() -> Generator[None, bool, None]:
        while True:
            # Generator can be forced to raise StopIteration by calling `g.send(True)`
            current = yield
            if current:
                break

    async def __anext__(self) -> _T:
        try:
            result = await self.async_iterator.__anext__()
        except StopAsyncIteration:
            # If the async iterator is exhausted, force-stop the tqdm iterator
            with contextlib.suppress(StopIteration):
                self.iterator.send(True)
            raise
        else:
            next(self.iterator)
            return result

    def __aiter__(self) -> "_AsyncTqdm[_T]":
        return self


def async_tqdm(
    iterable: Optional[Union[Iterable, AsyncIterable]] = None,
    *args,
    refresh_interval: float = 0.5,
    **kwargs,
) -> Union[tqdm, _AsyncTqdm]:
    """Same as `tqdm() <https://tqdm.github.io>`_, except it can be used
    in ``async for`` loops, and a task can be spawned to asynchronously
    refresh the progress bar every ``refresh_interval`` seconds.

    This should only be used for ``async for`` loops, or ``for`` loops
    which ``await`` something slow between iterations.

    Parameters
    ----------
    iterable: Optional[Union[Iterable, AsyncIterable]]
        The iterable to pass to ``tqdm()``. If this is an async
        iterable, this function will return a wrapper
    *args
        Other positional arguments to ``tqdm()``.
    refresh_interval : float
        The sleep interval between the progress bar being refreshed, in
        seconds. Defaults to 0.5. Set to 0 to disable the auto-
        refresher.
    **kwargs
        Keyword arguments to ``tqdm()``.

    """
    if isinstance(iterable, AsyncIterable):
        progress_bar = _AsyncTqdm(iterable, *args, **kwargs)
    else:
        progress_bar = tqdm(iterable, *args, **kwargs)

    if refresh_interval:
        # The background task that refreshes the progress bar
        async def _progress_bar_refresher() -> None:
            while not progress_bar.disable:
                await asyncio.sleep(refresh_interval)
                progress_bar.refresh()

        asyncio.create_task(_progress_bar_refresher())

    return progress_bar
