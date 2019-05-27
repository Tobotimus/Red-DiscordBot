import asyncio
import os

import pytest

from redbot.core import config, data_manager


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for entire session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


def _get_backend_type():
    if os.getenv("RED_STORAGE_TYPE") == "postgres":
        return config.BackendType.POSTGRES
    elif os.getenv("RED_STORAGE_TYPE") == "mongo":
        return config.BackendType.MONGO
    else:
        return config.BackendType.JSON


@pytest.fixture(scope="session", autouse=True)
async def _setup_driver():
    backend_type = _get_backend_type()
    if backend_type == config.BackendType.POSTGRES:
        storage_details = {
            "host": os.getenv("RED_POSTGRES_HOST", "localhost"),
            "port": int(os.getenv("RED_POSTGRES_PORT", "5432")),
            "user": os.getenv("RED_POSTGRES_USER", "postgres"),
            "password": os.getenv("RED_POSTGRES_PASSWORD"),
            "database": os.getenv("RED_POSTGRES_DATABASE", "red_db"),
        }
    elif backend_type == config.BackendType.MONGO:
        storage_details = {
            "URI": os.getenv("RED_MONGO_URI", "mongodb"),
            "HOST": os.getenv("RED_MONGO_HOST", "localhost"),
            "PORT": int(os.getenv("RED_MONGO_PORT", "27017")),
            "USERNAME": os.getenv("RED_MONGO_USER", "red"),
            "PASSWORD": os.getenv("RED_MONGO_PASSWORD", "red"),
            "DB_NAME": os.getenv("RED_MONGO_DATABASE", "red_db"),
        }
    else:
        storage_details = {}
    data_manager.storage_type = lambda: backend_type.value
    data_manager.storage_details = lambda: storage_details
    driver_cls = config.get_driver_class(backend_type)
    await driver_cls.initialize(**storage_details)
    yield
    await driver_cls.teardown()
