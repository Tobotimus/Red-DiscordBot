import asyncio
from unittest.mock import patch, MagicMock
import pytest


# region Register Tests
from redbot.core.config import ConfigCategory
from redbot.core.errors import StoredTypeError


@pytest.mark.asyncio
async def test_config_register_global(config):
    config.register_global(enabled=False)
    assert config.all_defaults[ConfigCategory.GLOBAL.value]["enabled"] is False
    assert await config.enabled() is False


def test_config_register_global_badvalues(config):
    with pytest.raises(RuntimeError):
        config.register_global(**{"invalid var name": True})


@pytest.mark.asyncio
async def test_config_register_guild(config, empty_guild):
    config.guild.register(enabled=False, some_list=[], some_dict={})
    assert config.all_defaults[ConfigCategory.GUILD.value]["enabled"] is False
    assert config.all_defaults[ConfigCategory.GUILD.value]["some_list"] == []
    assert config.all_defaults[ConfigCategory.GUILD.value]["some_dict"] == {}

    assert await config.guild(empty_guild).enabled() is False
    assert await config.guild(empty_guild).some_list() == []
    assert await config.guild(empty_guild).some_dict() == {}


@pytest.mark.asyncio
async def test_config_register_channel(config, empty_channel):
    config.channel.register(enabled=False)
    assert config.all_defaults[ConfigCategory.CHANNEL.value]["enabled"] is False
    assert await config.channel(empty_channel).enabled() is False


@pytest.mark.asyncio
async def test_config_register_role(config, empty_role):
    config.role.register(enabled=False)
    assert config.all_defaults[ConfigCategory.ROLE.value]["enabled"] is False
    assert await config.role(empty_role).enabled() is False


@pytest.mark.asyncio
async def test_config_register_member(config, empty_member):
    config.member.register(some_number=-1)
    assert config.all_defaults[ConfigCategory.MEMBER.value]["some_number"] == -1
    assert await config.member(empty_member).some_number() == -1


@pytest.mark.asyncio
async def test_config_register_user(config, empty_user):
    config.user.register(some_value=None)
    assert config.all_defaults[ConfigCategory.USER.value]["some_value"] is None
    assert await config.user(empty_user).some_value() is None


@pytest.mark.asyncio
async def test_config_force_register_global(config_fr):
    with pytest.raises(AttributeError):
        await config_fr.enabled()

    config_fr.register_global(enabled=True)
    assert await config_fr.enabled() is True


# endregion


# Test nested registration
@pytest.mark.asyncio
async def test_nested_registration(config):
    config.register_global(foo__bar__baz=False)
    assert await config.foo.bar.baz() is False


@pytest.mark.asyncio
async def test_nested_registration_asdict(config):
    defaults = {"bar": {"baz": False}}
    config.register_global(foo=defaults)

    assert await config.foo.bar.baz() is False


@pytest.mark.asyncio
async def test_nested_registration_and_changing(config):
    defaults = {"bar": {"baz": False}}
    config.register_global(foo=defaults)

    assert await config.foo.bar.baz() is False

    with pytest.raises(TypeError):
        await config.foo.set(True)


@pytest.mark.asyncio
async def test_doubleset_default(config):
    config.register_global(foo=True)
    config.register_global(foo=False)

    assert await config.foo() is False


@pytest.mark.asyncio
async def test_nested_registration_multidict(config):
    defaults = {"foo": {"bar": {"baz": True}}, "blah": True}
    config.register_global(**defaults)

    assert await config.foo.bar.baz() is True
    assert await config.blah() is True


def test_nested_group_value_badreg(config):
    config.register_global(foo=True)
    with pytest.raises(KeyError):
        config.register_global(foo__bar=False)


@pytest.mark.asyncio
async def test_nested_toplevel_reg(config):
    defaults = {"bar": True, "baz": False}
    config.register_global(foo=defaults)

    assert await config.foo.bar() is True
    assert await config.foo.baz() is False


@pytest.mark.asyncio
async def test_nested_overlapping(config):
    config.register_global(foo__bar=True)
    config.register_global(foo__baz=False)

    assert await config.foo.bar() is True
    assert await config.foo.baz() is False


@pytest.mark.asyncio
async def test_nesting_nofr(config):
    config.register_global(foo={})
    assert await config.foo.bar() is None
    assert await config.foo() == {}


# region Default Value Overrides
@pytest.mark.asyncio
async def test_global_default_override(config):
    assert await config.enabled(True) is True


@pytest.mark.asyncio
async def test_global_default_nofr(config):
    assert await config.nofr() is None
    assert await config.nofr(True) is True


@pytest.mark.asyncio
async def test_guild_default_override(config, empty_guild):
    assert await config.guild(empty_guild).enabled(True) is True


@pytest.mark.asyncio
async def test_channel_default_override(config, empty_channel):
    assert await config.channel(empty_channel).enabled(True) is True


@pytest.mark.asyncio
async def test_role_default_override(config, empty_role):
    assert await config.role(empty_role).enabled(True) is True


@pytest.mark.asyncio
async def test_member_default_override(config, empty_member):
    assert await config.member(empty_member).enabled(True) is True


@pytest.mark.asyncio
async def test_user_default_override(config, empty_user):
    assert await config.user(empty_user).some_value(True) is True


# endregion


# region Setting Values
@pytest.mark.asyncio
async def test_set_global(config):
    await config.enabled.set(True)
    assert await config.enabled() is True


@pytest.mark.asyncio
async def test_set_guild(config, empty_guild):
    await config.guild(empty_guild).enabled.set(True)
    assert await config.guild(empty_guild).enabled() is True

    curr_list = await config.guild(empty_guild).some_list([1, 2, 3])
    assert curr_list == [1, 2, 3]
    curr_list.append(4)

    await config.guild(empty_guild).some_list.set(curr_list)
    assert await config.guild(empty_guild).some_list() == curr_list


@pytest.mark.asyncio
async def test_set_channel(config, empty_channel):
    await config.channel(empty_channel).enabled.set(True)
    assert await config.channel(empty_channel).enabled() is True


@pytest.mark.asyncio
async def test_set_channel_no_register(config, empty_channel):
    await config.channel(empty_channel).no_register.set(True)
    assert await config.channel(empty_channel).no_register() is True


# endregion


# Dynamic attribute testing
@pytest.mark.asyncio
async def test_set_dynamic_attr(config):
    await config.set_raw("foobar", value=True)

    assert await config.foobar() is True


@pytest.mark.asyncio
async def test_clear_dynamic_attr(config):
    await config.foo.set(True)
    await config.clear_raw("foo")

    with pytest.raises(KeyError):
        await config.get_raw("foo")


@pytest.mark.asyncio
async def test_get_dynamic_attr(config):
    assert await config.get_raw("foobaz", default=True) is True


# Member Group testing
@pytest.mark.asyncio
async def test_membergroup_allguilds(config, empty_member):
    await config.member(empty_member).foo.set(False)

    all_servers = await config.member.all(int_primary_keys=True)
    assert empty_member.guild.id in all_servers


@pytest.mark.asyncio
async def test_membergroup_allmembers(config, empty_member):
    await config.member(empty_member).foo.set(False)

    all_members = await config.member[empty_member.guild.id].all(int_primary_keys=True)
    assert empty_member.id in all_members


# Clearing testing
@pytest.mark.asyncio
async def test_global_clear(config):
    config.register_global(foo=True, bar=False)

    await config.foo.set(False)
    await config.bar.set(True)

    assert await config.foo() is False
    assert await config.bar() is True

    await config.clear()

    assert await config.foo() is True
    assert await config.bar() is False


@pytest.mark.asyncio
async def test_member_clear(config, member_factory):
    config.member.register(foo=True)

    m1 = member_factory.get()
    await config.member(m1).foo.set(False)
    assert await config.member(m1).foo() is False

    m2 = member_factory.get()
    await config.member(m2).foo.set(False)
    assert await config.member(m2).foo() is False

    assert m1.guild.id != m2.guild.id

    await config.member(m1).clear()
    assert await config.member(m1).foo() is True
    assert await config.member(m2).foo() is False


@pytest.mark.asyncio
async def test_member_clear_all(config, member_factory):
    server_ids = []
    for _ in range(5):
        member = member_factory.get()
        await config.member(member).foo.set(True)
        server_ids.append(member.guild.id)

    assert len(await config.member.all()) == len(server_ids)

    await config.member.clear()

    assert len(await config.member.all()) == 0


@pytest.mark.asyncio
async def test_clear_all(config):
    await config.foo.set(True)
    assert await config.foo() is True

    await config.clear()
    with pytest.raises(KeyError):
        await config.get_raw("foo")


@pytest.mark.asyncio
async def test_clear_value(config):
    await config.foo.set(True)
    await config.foo.clear()

    with pytest.raises(KeyError):
        await config.get_raw("foo")


# Get All testing
@pytest.mark.asyncio
async def test_user_get_all_from_kind(config, user_factory):
    config.user.register(foo=False, bar=True)
    for _ in range(5):
        user = user_factory.get()
        await config.user(user).foo.set(True)

    all_data = await config.user.all()

    assert len(all_data) == 5

    for _, v in all_data.items():
        assert v["foo"] is True
        assert v["bar"] is True


@pytest.mark.asyncio
async def test_user_getalldata(config, user_factory):
    user = user_factory.get()
    config.user.register(foo=True, bar=False)
    await config.user(user).foo.set(False)

    all_data = await config.user(user).all()

    assert "foo" in all_data
    assert "bar" in all_data

    assert config.user(user).defaults["foo"] is True


@pytest.mark.asyncio
async def test_value_ctxmgr(config):
    config.register_global(foo_list=[])

    async with config.foo_list() as foo_list:
        foo_list.append("foo")

    foo_list = await config.foo_list()

    assert "foo" in foo_list


@pytest.mark.asyncio
async def test_value_ctxmgr_saves(config):
    config.register_global(bar_list=[])

    try:
        async with config.bar_list() as bar_list:
            bar_list.append("bar")
            raise RuntimeError()
    except RuntimeError:
        pass

    bar_list = await config.bar_list()

    assert "bar" in bar_list


@pytest.mark.asyncio
async def test_value_ctxmgr_immutable(config):
    config.register_global(foo=True)

    with pytest.raises(AttributeError):
        async with config.foo() as foo:
            foo = False

    foo = await config.foo()
    assert foo is True


@pytest.mark.asyncio
async def test_ctxmgr_no_shared_default(config, member_factory):
    config.member.register(foo=[])
    m1 = member_factory.get()
    m2 = member_factory.get()

    async with config.member(m1).foo() as foo:
        foo.append(1)

    assert 1 not in await config.member(m2).foo()


class AsyncMock(MagicMock):
    async def __call__(self, *args, **kwargs):
        return super().__call__(*args, **kwargs)


@pytest.mark.asyncio
async def test_ctxmgr_no_unnecessary_write(config):
    config.register_global(foo=[])
    foo_value_obj = config.foo
    with patch.object(foo_value_obj, "set") as set_method:
        async with foo_value_obj() as foo:
            pass
        set_method.assert_not_called()


@pytest.mark.asyncio
async def test_get_then_mutate(config):
    """Tests that mutating an object after getting it as a value doesn't mutate the data store."""
    config.register_global(list1=[])
    await config.list1.set([])
    list1 = await config.list1()
    list1.append("foo")
    list1 = await config.list1()
    assert "foo" not in list1


@pytest.mark.asyncio
async def test_set_then_mutate(config):
    """Tests that mutating an object after setting it as a value doesn't mutate the data store."""
    config.register_global(list1=[])
    list1 = []
    await config.list1.set(list1)
    list1.append("foo")
    list1 = await config.list1()
    assert "foo" not in list1


@pytest.mark.asyncio
async def test_call_group_fills_defaults(config):
    config.register_global(subgroup={"foo": True})
    subgroup = await config.subgroup()
    assert "foo" in subgroup


@pytest.mark.asyncio
async def test_group_call_ctxmgr_writes(config):
    config.register_global(subgroup={"foo": True})
    async with config.subgroup() as subgroup:
        subgroup["bar"] = False

    subgroup = await config.subgroup()
    assert subgroup == {"foo": True, "bar": False}


@pytest.mark.asyncio
async def test_all_works_as_ctxmgr(config):
    config.register_global(subgroup={"foo": True})
    async with config.subgroup.all() as subgroup:
        subgroup["bar"] = False

    subgroup = await config.subgroup()
    assert subgroup == {"foo": True, "bar": False}


@pytest.mark.asyncio
async def test_get_raw_mixes_defaults(config):
    config.register_global(subgroup={"foo": True})
    await config.subgroup.set_raw("bar", value=False)

    subgroup = await config.get_raw("subgroup")
    assert subgroup == {"foo": True, "bar": False}


@pytest.mark.asyncio
async def test_cast_str_raw(config):
    await config.set_raw(123, 456, value=True)
    assert await config.get_raw(123, 456) is True
    assert await config.get_raw("123", "456") is True
    await config.clear_raw("123", 456)


@pytest.mark.asyncio
async def test_cast_str_nested(config):
    config.register_global(foo={})
    await config.foo.set({123: True, 456: {789: False}})
    assert await config.foo() == {"123": True, "456": {"789": False}}


def test_config_custom_noinit(config):
    with pytest.raises(ValueError):
        config.custom("TEST", 1, 2, 3)


def test_config_custom_init(config):
    config.init_custom("TEST", 3)
    config.custom("TEST", 1, 2, 3)


def test_config_custom_doubleinit(config):
    config.init_custom("TEST", 3)
    with pytest.raises(ValueError):
        config.init_custom("TEST", 2)


@pytest.mark.asyncio
async def test_config_locks_cache(config, empty_guild):
    lock1 = config.foo.get_lock()
    assert lock1 is config.foo.get_lock()
    lock2 = config.guild(empty_guild).foo.get_lock()
    assert lock2 is config.guild(empty_guild).foo.get_lock()
    assert lock1 is not lock2


@pytest.mark.asyncio
async def test_config_value_atomicity(config):
    config.register_global(foo=[])
    tasks = []
    for _ in range(15):

        async def func():
            async with config.foo.get_lock():
                foo = await config.foo()
                foo.append(0)
                await asyncio.sleep(0.01)
                await config.foo.set(foo)

        tasks.append(func())

    await asyncio.wait(tasks, return_when=asyncio.ALL_COMPLETED)

    assert len(await config.foo()) == 15


@pytest.mark.asyncio
async def test_config_ctxmgr_atomicity(config):
    config.register_global(foo=[])
    tasks = []
    for _ in range(15):

        async def func():
            async with config.foo() as foo:
                foo.append(0)
                await asyncio.sleep(0.01)

        tasks.append(func())

    await asyncio.wait(tasks, return_when=asyncio.ALL_COMPLETED)

    assert len(await config.foo()) == 15


@pytest.mark.asyncio
async def test_config_inc(config):
    config.register_global(foo=0)

    assert await config.foo.inc() == await config.foo() == 1
    assert await config.foo.inc(-1) == await config.foo() == 0

    await config.foo.set(None)
    with pytest.raises(StoredTypeError):
        await config.foo.inc()


@pytest.mark.asyncio
async def test_config_toggle(config):
    config.register_global(foo=False)

    assert await config.foo.toggle() is await config.foo() is True
    assert await config.foo.toggle() is await config.foo() is False

    await config.foo.set(None)
    with pytest.raises(StoredTypeError):
        await config.foo.toggle()


@pytest.mark.asyncio
async def test_config_append(config):
    config.register_global(foo=[])

    assert await config.foo.append(1) == await config.foo() == [1]
    assert await config.foo.append(0, append_left=True) == await config.foo() == [0, 1]
    assert await config.foo.append(2, max_length=2) == await config.foo() == [1, 2]
    assert (
        await config.foo.append(-1, max_length=2, append_left=True)
        == await config.foo()
        == [-1, 1]
    )

    await config.set_raw("foo", value=None)
    with pytest.raises(StoredTypeError):
        await config.foo.append(1)


@pytest.mark.asyncio
async def test_config_extend(config):
    config.register_global(foo=[])

    assert await config.foo.extend((1, 2)) == await config.foo() == [1, 2]
    assert (
        await config.foo.extend((-1, 0), extend_left=True) == await config.foo() == [-1, 0, 1, 2]
    )
    assert await config.foo.extend((3, 4), max_length=5) == await config.foo() == [0, 1, 2, 3, 4]
    assert (
        await config.foo.extend((-3, -2), max_length=3, extend_left=True)
        == await config.foo()
        == [-3, -2, 0]
    )

    await config.set_raw("foo", value=None)
    with pytest.raises(StoredTypeError):
        await config.foo.extend([1])


@pytest.mark.asyncio
async def test_config_insert(config):
    config.register_global(foo=[3])

    assert await config.foo.insert(0, 5) == await config.foo() == [5, 3]
    assert await config.foo.insert(-1, 2) == await config.foo() == [5, 2, 3]
    assert await config.foo.insert(1, 4, max_length=3) == await config.foo() == [5, 4, 2]

    await config.set_raw("foo", value=None)
    with pytest.raises(StoredTypeError):
        await config.foo.insert(0, 1)


@pytest.mark.asyncio
async def test_config_index(config):
    config.register_global(foo=[])
    await config.foo.set(["bar", "baz", "foobar"])

    assert await config.foo.index("baz") == 1
    await config.foo.set(["baz"])
    assert await config.foo.index("baz") == 0

    with pytest.raises(ValueError):
        await config.foo.index("bang")

    await config.set_raw("foo", value=None)
    with pytest.raises(StoredTypeError):
        await config.foo.index("bar")


@pytest.mark.asyncio
async def test_config_element_access(config):
    config.register_global(foo=[])
    await config.foo.set(["bar", "baz", "foobar"])

    assert await config.foo.at(1) == "baz"
    assert await config.foo.at(-1) == "foobar"

    with pytest.raises(IndexError):
        await config.foo.at(3)

    with pytest.raises(IndexError):
        await config.foo.at(-4)

    await config.set_raw("foo", value=None)
    with pytest.raises(StoredTypeError):
        await config.foo.at(0)


@pytest.mark.asyncio
async def test_config_element_assignment(config):
    config.register_global(foo=["foo", "bar"])

    await config.foo.set_at(1, "baz")
    assert await config.foo() == ["foo", "baz"]
    await config.foo.set_at(0, "faz")
    assert await config.foo() == ["faz", "baz"]
    await config.foo.set_at(-1, "bav")
    assert await config.foo() == ["faz", "bav"]

    with pytest.raises(IndexError):
        await config.foo.set_at(2, "bar")

    with pytest.raises(IndexError):
        await config.foo.set_at(-3, "bar")

    await config.set_raw("foo", value=None)
    with pytest.raises(StoredTypeError):
        await config.foo.set_at(0, "bar")


@pytest.mark.asyncio
async def test_config_group_contains(config):
    await config.foo.set(False)
    await config.guild(100).foo.set(True)

    assert await config.contains("foo") is True
    assert await config.contains("baz") is False

    assert await config.guild.contains(100) is True
    assert await config.guild.contains(101) is False

    config.register_global(bar={})
    await config.set_raw("bar", value=None)

    with pytest.raises(StoredTypeError):
        await config.bar.contains(1)


@pytest.mark.asyncio
async def test_config_array_contains(config):
    config.register_global(foo=[])
    await config.foo.set(["bar"])

    assert await config.foo.contains("bar") is True
    assert await config.foo.contains("baz") is False

    await config.set_raw("foo", value=None)
    with pytest.raises(StoredTypeError):
        await config.foo.contains("bar")
