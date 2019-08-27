import asyncio

from tqdm import tqdm

__all__ = ["async_tqdm"]


def async_tqdm(*args, interval: float = 0.5, **kwargs) -> tqdm:
    """Same as `tqdm() <https://tqdm.github.io>`_, except a background task is spawned to
    asynchronously refresh the progress bar every ``interval`` seconds.

    This should only be used in slow loops which ``await`` something
    between iterations.

    Parameters
    ----------
    *args
        Positional arguments to ``tqdm()``.
    interval : float
        The sleep interval between the progress bar being refreshed, in
        seconds. Defaults to 0.5.
    **kwargs
        Keyword arguments to ``tqdm()``.

    """
    progress_bar = tqdm(*args, **kwargs)

    async def _progress_bar_refresher() -> None:
        while not progress_bar.disable:
            await asyncio.sleep(interval)
            progress_bar.refresh()

    asyncio.create_task(_progress_bar_refresher())
    return progress_bar
