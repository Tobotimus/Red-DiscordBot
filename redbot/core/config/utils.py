import enum
from typing import Any, Dict, TYPE_CHECKING, Tuple, Type, TypeVar, Union

if TYPE_CHECKING:
    from .drivers import BaseDriver

_T = TypeVar("_T")

__all__ = ["ConfigCategory", "migrate", "str_key_dict"]


class ConfigCategory(enum.Enum):
    GLOBAL = "GLOBAL"
    GUILD = "GUILD"
    CHANNEL = "TEXTCHANNEL"
    ROLE = "ROLE"
    USER = "USER"
    MEMBER = "MEMBER"

    def __str__(self) -> str:
        return self.value

    @classmethod
    def get_pkey_info(
        cls, category: Union[str, "ConfigCategory"], custom_group_data: Dict[str, int]
    ) -> Tuple[int, bool]:
        """Get the full primary key length for the given category,
        and whether or not the category is a custom category.
        """
        try:
            # noinspection PyArgumentList
            category_obj = cls(category)
        except ValueError:
            return custom_group_data[category], True
        else:
            return _CATEGORY_PKEY_COUNTS[category_obj], False


_CATEGORY_PKEY_COUNTS = {
    ConfigCategory.GLOBAL: 0,
    ConfigCategory.GUILD: 1,
    ConfigCategory.CHANNEL: 1,
    ConfigCategory.ROLE: 1,
    ConfigCategory.USER: 1,
    ConfigCategory.MEMBER: 2,
}


async def migrate(cur_driver_cls: Type["BaseDriver"], new_driver_cls: Type["BaseDriver"]) -> None:
    """Migrate from one driver type to another."""
    # Get custom group data
    from .config import Config

    core_conf = Config.get_core_conf()
    core_conf.init_custom("CUSTOM_GROUPS", 2)
    all_custom_group_data = await core_conf.custom("CUSTOM_GROUPS").all()

    await cur_driver_cls.migrate_to(new_driver_cls, all_custom_group_data)


def str_key_dict(value: Dict[Any, _T]) -> Dict[str, _T]:
    """
    Recursively casts all keys in the given `dict` to `str`.

    Parameters
    ----------
    value : Dict[Any, Any]
        The `dict` to cast keys to `str`.

    Returns
    -------
    Dict[str, Any]
        The `dict` with keys (and nested keys) casted to `str`.

    """
    ret = {}
    for k, v in value.items():
        if isinstance(v, dict):
            v = str_key_dict(v)
        ret[str(k)] = v
    return ret
