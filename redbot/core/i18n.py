import gettext
import weakref
from contextvars import ContextVar
from pathlib import Path
from typing import Callable, Dict, ClassVar, List

import polib
from discord.utils import deprecated

import redbot.core
from redbot.core import data_manager

__all__ = ["Translator", "cog_i18n"]


class Translator(Callable[[str], str]):
    """Function to get translated strings at runtime."""

    locale_var: ClassVar[ContextVar[str]] = ContextVar("cur_locale", default="en-US")

    def __init__(self, package: str):
        """
        Initializes an internationalization object.

        Parameters
        ----------
        package : str
            The package containing the `locales` directory.

        """
        self.domain = package
        self._translations: Dict[str, gettext.NullTranslations] = {}

    @property
    def translations(self) -> gettext.NullTranslations:
        locale = self.locale_var.get()
        try:
            return self._translations[locale]
        except KeyError:
            self._translations[locale] = translations = gettext.translation(
                self.domain,
                localedir=data_manager.core_data_path() / "localedir",
                languages=[locale],
                fallback=True,
            )
            return translations

    def __call__(self, message: str) -> str:
        """Translate the given string."""
        return self.translations.gettext(message)

    @classmethod
    def list_available_locales(cls) -> List[str]:
        ret = [
            p.name
            for p in cls._get_localedir().iterdir()
            if next(p.joinpath("LC_MESSAGES").iterdir(), None)  # if not empty
        ]
        if "en-US" not in ret:
            ret.append("en-US")
        ret.sort()
        return ret

    @staticmethod
    def _get_localedir() -> Path:
        return data_manager.core_data_path() / "localedir"

    @classmethod
    def _load_core_locales(cls) -> None:
        core_pkg_pth = Path(redbot.core.__file__).parent
        for locales_path in core_pkg_pth.glob("**/locales"):
            package_path = locales_path.parent
            package_name = ".".join(
                map(str, package_path.relative_to(core_pkg_pth.parents[1]).parts)
            )
            cls._load_locales(package_name, package_path)

    @classmethod
    def _load_locales(cls, package_name: str, locales_path: Path) -> None:
        localedir = cls._get_localedir()
        for pofile_path in locales_path.glob("*.po"):
            language = pofile_path.stem
            mofile_path = localedir / language / "LC_MESSAGES" / f"{package_name}.mo"
            mofile_path.parent.mkdir(parents=True, exist_ok=True)
            polib.pofile(str(pofile_path)).save_as_mofile(str(mofile_path))


@deprecated("the `translator` argument to Cog.__init_subclass__")
def cog_i18n(translator: Translator):
    """Class decorator to link a translator to a cog.

    .. deprecated:: 3.2

        Use the `translator` argument to ``Cog.__init_subclass__``, like
        so::

            from redbot.core import commands

            class MyCog(commands.Cog, translator=_):
                ...

    """

    def decorator(cog_class: type):
        cog_class.__translator__ = translator

    return decorator
