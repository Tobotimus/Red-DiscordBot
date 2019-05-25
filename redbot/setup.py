#!/usr/bin/env python3
import asyncio
import os
import sys
from copy import deepcopy
from datetime import datetime as dt
from pathlib import Path
import logging
from typing import Dict, Any, Optional

import appdirs
import click

import redbot.logging
from redbot.core.cli import confirm
from redbot.core.json_io import JsonIO
from redbot.core.utils import safe_delete, create_backup as _create_backup
from redbot.core import config, data_manager, drivers
from redbot.core.drivers import BackendType, IdentifierData

conversion_log = logging.getLogger("red.converter")

config_dir = None
appdir = appdirs.AppDirs("Red-DiscordBot")
if sys.platform == "linux":
    if 0 < os.getuid() < 1000:
        config_dir = Path(appdir.site_data_dir)
if not config_dir:
    config_dir = Path(appdir.user_config_dir)
try:
    config_dir.mkdir(parents=True, exist_ok=True)
except PermissionError:
    print("You don't have permission to write to '{}'\nExiting...".format(config_dir))
    sys.exit(1)
config_file = config_dir / "config.json"


def load_existing_config():
    if not config_file.exists():
        return {}

    return JsonIO(config_file)._load_json()


instance_data = load_existing_config()
if instance_data is None:
    instance_list = []
else:
    instance_list = list(instance_data.keys())


def save_config(name, data, remove=False):
    _config = load_existing_config()
    if remove and name in _config:
        _config.pop(name)
    else:
        if name in _config:
            print(
                "WARNING: An instance already exists with this name. "
                "Continuing will overwrite the existing instance config."
            )
            if not confirm("Are you absolutely certain you want to continue (y/n)? "):
                print("Not continuing")
                sys.exit(0)
        _config[name] = data
    JsonIO(config_file)._save_json(_config)


def get_data_dir():
    default_data_dir = Path(appdir.user_data_dir)

    print(
        "Hello! Before we begin the full configuration process we need to"
        " gather some initial information about where you'd like us"
        " to store your bot's data. We've attempted to figure out a"
        " sane default data location which is printed below. If you don't"
        " want to change this default please press [ENTER], otherwise"
        " input your desired data location."
    )
    print()
    print("Default: {}".format(default_data_dir))

    new_path = input("> ")

    if new_path != "":
        new_path = Path(new_path)
        default_data_dir = new_path

    if not default_data_dir.exists():
        try:
            default_data_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            print(
                "We were unable to create your chosen directory."
                " You may need to restart this process with admin"
                " privileges."
            )
            sys.exit(1)

    print("You have chosen {} to be your data directory.".format(default_data_dir))
    if not confirm("Please confirm (y/n):"):
        print("Please start the process over.")
        sys.exit(0)
    return default_data_dir


def get_storage_type():
    storage_dict = {1: "JSON", 2: "MongoDB", 3: "PostgreSQL"}
    storage = None
    while storage is None:
        print()
        print("Please choose your storage backend (if you're unsure, choose 1).")
        print("1. JSON (file storage, requires no database).")
        print("2. MongoDB")
        print("3. PostgreSQL")
        storage = input("> ")
        try:
            storage = int(storage)
        except ValueError:
            storage = None
        else:
            if storage not in storage_dict:
                storage = None
    return storage


def get_name():
    name = ""
    while len(name) == 0:
        print()
        print(
            "Please enter a name for your instance, this name cannot include spaces"
            " and it will be used to run your bot from here on out."
        )
        name = input("> ")
        if " " in name:
            name = ""
    return name


def basic_setup():
    """
    Creates the data storage folder.
    :return:
    """

    default_data_dir = get_data_dir()

    default_dirs = deepcopy(data_manager.basic_config_default)
    default_dirs["DATA_PATH"] = str(default_data_dir.resolve())

    storage = get_storage_type()

    storage_dict = {1: BackendType.JSON, 2: BackendType.MONGO, 3: BackendType.POSTGRES}
    storage_type: BackendType = storage_dict.get(storage, BackendType.JSON)
    default_dirs["STORAGE_TYPE"] = storage_type.value
    driver_cls = drivers.get_driver_class(storage_type)
    default_dirs["STORAGE_DETAILS"] = driver_cls.get_config_details()

    name = get_name()
    save_config(name, default_dirs)

    print()
    print(
        "Your basic configuration has been saved. Please run `redbot <name>` to"
        " continue your setup process and to run the bot."
    )


def get_current_backend(instance) -> BackendType:
    return BackendType(instance_data[instance]["STORAGE_TYPE"])


def get_target_backend(backend) -> BackendType:
    if backend == "json":
        return BackendType.JSON
    elif backend == "mongo":
        return BackendType.MONGO
    elif backend == "postgres":
        return BackendType.POSTGRES


async def do_migration(
    current_backend: BackendType, target_backend: BackendType
) -> Dict[str, Any]:
    cur_driver_cls = drivers.get_driver_class(current_backend)
    new_driver_cls = drivers.get_driver_class(target_backend)
    cur_storage_details = data_manager.storage_details()
    new_storage_details = new_driver_cls.get_config_details()

    await cur_driver_cls.initialize(**cur_storage_details)
    await new_driver_cls.initialize(**new_storage_details)

    await config.migrate(cur_driver_cls, new_driver_cls)

    await cur_driver_cls.teardown()
    await new_driver_cls.teardown()

    return new_storage_details


async def mongov1_to_json() -> Dict[str, Any]:
    await drivers.MongoDriver.initialize(**data_manager.storage_details())
    m = drivers.MongoDriver("Core", "0")
    db = m.db
    collection_names = await db.list_collection_names()
    for collection_name in collection_names:
        if "." in collection_name:
            # Fix for one of Zeph's problems
            continue
        # Every cog name has its own collection
        collection = db[collection_name]
        async for document in collection.find():
            # Every cog has its own document.
            # This means if two cogs have the same name but different identifiers, they will
            # be two separate documents in the same collection
            cog_id = document.pop("_id")
            if not isinstance(cog_id, str):
                # Another garbage data check
                continue
            elif not str(cog_id).isdigit():
                continue
            driver = drivers.JsonDriver(collection_name, cog_id)
            for category, value in document.items():
                ident_data = IdentifierData(str(cog_id), category, tuple(), tuple(), 0)
                await driver.set(ident_data, value=value)

    conversion_log.info("Cog conversion complete.")
    await drivers.MongoDriver.teardown()

    return {}


async def edit_instance():
    _instance_list = load_existing_config()
    if not _instance_list:
        print("No instances have been set up!")
        return

    print(
        "You have chosen to edit an instance. The following "
        "is a list of instances that currently exist:\n"
    )
    for instance in _instance_list.keys():
        print("{}\n".format(instance))
    print("Please select one of the above by entering its name")
    selected = input("> ")

    if selected not in _instance_list.keys():
        print("That isn't a valid instance!")
        return
    _instance_data = _instance_list[selected]
    default_dirs = deepcopy(data_manager.basic_config_default)

    current_data_dir = Path(_instance_data["DATA_PATH"])
    print("You have selected '{}' as the instance to modify.".format(selected))
    if not confirm("Please confirm (y/n):"):
        print("Ok, we will not continue then.")
        return

    print("Ok, we will continue on.")
    print()
    if confirm("Would you like to change the instance name? (y/n)"):
        name = get_name()
    else:
        name = selected

    if confirm("Would you like to change the data location? (y/n)"):
        default_data_dir = get_data_dir()
        default_dirs["DATA_PATH"] = str(default_data_dir.resolve())
    else:
        default_dirs["DATA_PATH"] = str(current_data_dir.resolve())

    if name != selected:
        save_config(selected, {}, remove=True)
    save_config(name, default_dirs)

    print("Your basic configuration has been edited")


async def create_backup(instance: str) -> None:
    data_manager.load_basic_configuration(instance)
    backend_type = get_current_backend(instance)
    if backend_type == BackendType.MONGOV1:
        await mongov1_to_json()
    elif backend_type != BackendType.JSON:
        await do_migration(backend_type, BackendType.JSON)
    print("Backing up the instance's data...")
    success = await _create_backup()
    if success is not None:
        print(f"A backup of {instance} has been made. It is at {backup_fpath}")
    else:
        print("Creating the backup failed.")


async def remove_instance(
    instance,
    interactive: bool = False,
    drop_db: Optional[bool] = None,
    remove_datapath: Optional[bool] = None,
):
    data_manager.load_basic_configuration(instance)

    if confirm("Would you like to make a backup of the data for this instance? (y/n)"):
        await create_backup(instance)

    backend = get_current_backend(instance)
    if backend == BackendType.MONGOV1:
        driver_cls = drivers.MongoDriver
    else:
        driver_cls = drivers.get_driver_class(backend)

    await driver_cls.delete_all_data(interactive=interactive, drop_db=drop_db)

    if interactive is True and remove_datapath is None:
        remove_datapath = confirm("Would you like to delete the instance's entire datapath? (y/n)")

    if remove_datapath is True:
        data_path = data_manager.core_data_path().parent
        safe_delete(data_path)

    save_config(instance, {}, remove=True)
    print("The instance {} has been removed\n".format(instance))


async def remove_instance_interaction():
    if not instance_list:
        print("No instances have been set up!")
        return

    print(
        "You have chosen to remove an instance. The following "
        "is a list of instances that currently exist:\n"
    )
    for instance in instance_data.keys():
        print("{}\n".format(instance))
    print("Please select one of the above by entering its name")
    selected = input("> ")

    if selected not in instance_data.keys():
        print("That isn't a valid instance!")
        return

    await remove_instance(selected, interactive=True)


@click.group(invoke_without_command=True)
@click.option("--debug", type=bool)
@click.pass_context
def cli(ctx, debug):
    level = logging.DEBUG if debug else logging.INFO
    redbot.logging.init_logging(level=level, location=Path.cwd() / "red_setup_logs")
    if ctx.invoked_subcommand is None:
        basic_setup()


@cli.command()
@click.argument("instance", type=click.Choice(instance_list))
@click.option("--no-prompt", default=False, help="Don't ask for user input during the process.")
@click.option(
    "--drop-db",
    type=bool,
    default=None,
    help=(
        "Drop the entire database constaining this instance's data. Has no effect on JSON "
        "instances. If this option and --no-prompt are omitted, you will be asked about this."
    ),
)
@click.option(
    "--remove-datapath",
    type=bool,
    default=None,
    help=(
        "Remove this entire instance's datapath. If this option and --no-prompt are omitted, you "
        "will be asked about this."
    ),
)
def delete(instance: str, no_prompt: Optional[bool], drop_db: Optional[bool]):
    loop = asyncio.get_event_loop()
    if no_prompt is None:
        interactive = None
    else:
        interactive = not no_prompt
    loop.run_until_complete(remove_instance(instance, interactive, drop_db))


@cli.command()
@click.argument("instance", type=click.Choice(instance_list))
@click.argument("backend", type=click.Choice(["json", "mongo", "postgres"]))
def convert(instance, backend):
    current_backend = get_current_backend(instance)
    target = get_target_backend(backend)
    data_manager.load_basic_configuration(instance)

    default_dirs = deepcopy(data_manager.basic_config_default)
    default_dirs["DATA_PATH"] = str(Path(instance_data[instance]["DATA_PATH"]))

    loop = asyncio.get_event_loop()

    if current_backend == BackendType.MONGOV1:
        if target == BackendType.JSON:
            new_storage_details = loop.run_until_complete(mongov1_to_json())
        else:
            raise RuntimeError(
                "Please see conversion docs for updating to the latest mongo version."
            )
    else:
        new_storage_details = loop.run_until_complete(do_migration(current_backend, target))

    if new_storage_details is not None:
        default_dirs["STORAGE_TYPE"] = target.value
        default_dirs["STORAGE_DETAILS"] = new_storage_details
        save_config(instance, default_dirs)
        conversion_log.info(f"Conversion to {target} complete.")
    else:
        conversion_log.info(
            f"Cannot convert {current_backend.value} to {target.value} at this time."
        )


if __name__ == "__main__":
    try:
        cli()
    except KeyboardInterrupt:
        print("Exiting...")
    else:
        print("Exiting...")
