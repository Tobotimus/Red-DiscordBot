from typing import Tuple, Union

from .utils import ConfigCategory

__all__ = ["IdentifierData"]


class IdentifierData:
    def __init__(
        self,
        cog_name: str,
        uuid: str,
        category: Union[str, ConfigCategory],
        primary_key: Tuple[str, ...],
        identifiers: Tuple[str, ...],
        primary_key_len: int,
        is_custom: bool = False,
    ):
        self._cog_name = cog_name
        self._uuid = uuid
        self._category = str(category)
        self._primary_key = primary_key
        self._identifiers = identifiers
        self.primary_key_len = primary_key_len
        self._is_custom = is_custom

    @property
    def cog_name(self) -> str:
        return self._cog_name

    @property
    def uuid(self) -> str:
        return self._uuid

    @property
    def category(self) -> str:
        return self._category

    @property
    def primary_key(self) -> Tuple[str, ...]:
        return self._primary_key

    @property
    def identifiers(self) -> Tuple[str, ...]:
        return self._identifiers

    @property
    def is_custom(self) -> bool:
        return self._is_custom

    def __repr__(self) -> str:
        return (
            f"<IdentifierData cog_name={self.cog_name} uuid={self.uuid} category={self.category} "
            f"primary_key={self.primary_key} identifiers={self.identifiers}>"
        )

    def __eq__(self, other) -> bool:
        if not isinstance(other, IdentifierData):
            return False
        return (
            self.cog_name == other.cog_name
            and self.uuid == other.uuid
            and self.category == other.category
            and self.primary_key == other.primary_key
            and self.identifiers == other.identifiers
        )

    def __hash__(self) -> int:
        return hash((self.cog_name, self.uuid, self.category, self.primary_key, self.identifiers))

    def add_primary_key(self, *primary_key: str) -> "IdentifierData":
        if not all(isinstance(i, str) for i in primary_key):
            raise ValueError("Primary keys must be strings.")

        return IdentifierData(
            self.cog_name,
            self.uuid,
            self.category,
            self.primary_key + primary_key,
            self.identifiers,
            self.primary_key_len,
            is_custom=self.is_custom,
        )

    def add_identifier(self, *identifier: str) -> "IdentifierData":
        if not all(isinstance(i, str) for i in identifier):
            raise ValueError("Identifiers must be strings.")

        return IdentifierData(
            self.cog_name,
            self.uuid,
            self.category,
            self.primary_key,
            self.identifiers + identifier,
            self.primary_key_len,
            is_custom=self.is_custom,
        )

    def to_tuple(self) -> Tuple[str, ...]:
        return tuple(
            filter(
                None,
                (self.cog_name, self.uuid, self.category, *self.primary_key, *self.identifiers),
            )
        )
