import json
from typing import Optional, Dict, Any, Set

import asyncpg

from .red_base import BaseDriver, IdentifierData, ConfigCategory

__all__ = ["PostgresDriver"]


class PostgresDriver(BaseDriver):

    _pool: Optional[asyncpg.pool.Pool] = None

    def __init__(self, cog_name, identifier):
        self._schema_name: str = "__".join((self.cog_name, identifier))
        self._schema_created = False
        self._created_tables = Set[str]()

        super().__init__(cog_name, identifier)

    @classmethod
    async def intitialize(cls, storage_details: Dict[str, Any]) -> None:
        cls._pool = asyncpg.create_pool(**storage_details)

    async def has_valid_connection(self) -> bool:
        raise NotImplementedError

    async def get(self, identifier_data: IdentifierData):
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
        if identifier_data.category not in self._created_tables:
            await self._create_table(identifier_data)

        table = ".".join((self._schema_name, identifier_data.category))

        pk_len = self._get_pk_len(identifier_data)
        if len(identifier_data.primary_key) < pk_len:
            selection = [
                f"primary_key_{i}"
                for i
                in range(
                    identifier_data.custom_group_data[
                        identifier_data.category
                    ],
                    len(identifier_data.identifiers),
                    -1
                )
            ] + ["json_data"]
            fetch = self._pool.fetch
        else:
            selection = " -> ".join(
                ["json_data"] + ["'?'" for _ in range(len(identifier_data.identifiers))]
            )
            fetch = self._pool.fetchrow

        query = f"SELECT {selection} FROM {table}"
        if identifier_data.primary_key:
            primary_key_comparison = " AND ".join(
                (f"primary_key_{i} == ?" for i in range(len(identifier_data.primary_key)))
            )
            query += f" WHERE {primary_key_comparison}"

        result = await fetch(
            query,
            *identifier_data.identifiers,
            *identifier_data.primary_key,
        )

        if multi:
            ret = {}
            for row in result:
                inner = ret
                for primary_key in row[:-2]:
                    inner = inner.setdefault(primary_key, {})
                data = row[-1]
                inner[row[-2]] = json.loads(data)
            return ret
        else:
            if not result:
                raise KeyError()
            return json.loads(result[0])

    def get_config_details(self):
        """
        Asks users for additional configuration information necessary
        to use this config driver.

        Returns
        -------
            Dict of configuration details.
        """
        raise NotImplementedError

    async def set(self, identifier_data: IdentifierData, value=None):
        """
        Sets the value of the key indicated by the given identifiers.

        Parameters
        ----------
        identifier_data
        value
            Any JSON serializable python object.
        """
        if identifier_data.category not in self._created_tables:
            await self._create_table(identifier_data)

        table = ".".join((self._schema_name, identifier_data.category))

        pk_len = self._get_pk_len(identifier_data)
        if len(identifier_data.primary_key) < pk_len:

        else:
            values = ", ".join(["?"] * (pk_len + 1))
            await self._pool.execute(
                f"""
                INSERT INTO {table} AS t VALUES({values})
                ON CONFLICT({primary_key_names}) DO UPDATE SET 
                    json_data = (
                        SELECT jsonb_set_deep(t.json_data, ?, ?)
                    )
                """,
                *identifier_data.primary_key,

            )
        raise NotImplementedError

    async def clear(self, identifier_data: IdentifierData):
        """
        Clears out the value specified by the given identifiers.

        Equivalent to using ``del`` on a dict.

        Parameters
        ----------
        identifier_data
        """
        raise NotImplementedError

    async def _create_table(self, identifier_data: IdentifierData) -> None:
        if identifier_data.category == ConfigCategory.MEMBER:
            pk_len = 2
            pk_typ = "BIGINT"
        elif identifier_data.is_custom:
            pk_len = identifier_data.custom_group_data[identifier_data.category]
            pk_typ = "TEXT"
        else:
            pk_len = 1
            pk_typ = "BIGINT"
        pk_def = ", ".join((f"primary_key_{i} {pk_typ}" for i in range(pk_len)))

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                if not self._schema_created:
                    await conn.execute(
                        f"CREATE SCHEMA IF NOT EXISTS {self._schema_name}"
                    )
                table_name = ".".join((self._schema_name, identifier_data.category))
                await conn.execute(
                    f"CREATE TABLE IF NOT EXISTS {table_name}"
                    f"({pk_def}, json_data jsonb)",
                )
                self._created_tables.add(identifier_data.category)

    @staticmethod
    def _get_pk_len(identifier_data: IdentifierData) -> bool:
        if identifier_data.category == ConfigCategory.MEMBER:
            pk_len = 2
        elif identifier_data.is_custom:
            pk_len = identifier_data.custom_group_data[identifier_data.category]
        else:
            pk_len = 1
        return pk_len
