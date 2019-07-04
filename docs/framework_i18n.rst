.. i18n framework reference

==============================
Internationalization Framework
==============================

-----------
Basic Usage
-----------

.. code-block:: python

    # cogpackage/examplecog.py
    from redbot.core import commands
    from redbot.core.i18n import Translator

    _ = Translator(__package__)

    class ExampleCog(commands.Cog, translator=_):
        """description"""

        @commands.command()
        async def mycom(self, ctx):
            """command description"""
            await ctx.send(_("This is a test command"))

----------------------------------
Creating Translations For Your Cog
----------------------------------

After making your cog, generate a ``messages.pot`` file in the ``locales/`` sub-directory of
your cog package using `redgettext <https://pypi.org/p/redgettext>`_, like so:

.. code-block:: none

    redgettext --command-docstrings path/to/cogpackage

The new ``messages.pot`` file will contain entries for every string inside a ``_()`` call, as well
as every command and cog docstring.

Now, to create translations for your cog, make a copy of the ``messages.pot`` file in the same
directory, and name it in the form ``ll-CC.po``, where ``ll`` is the `ISO 639 language code
<https://www.gnu.org/software/gettext/manual/html_node/Language-Codes.html#Language-Codes>`_, and
``CC`` is the `ISO 3166 country code
<https://www.gnu.org/software/gettext/manual/html_node/Country-Codes.html#Country-Codes>`_. You may
now fill out the ``msgstr`` entries within this file with your translations.

.. note::

    If your cog package contains nested packages, and those packages contain strings which you want
    to translate, you should create a ``locales`` directory in each one. To do this in one command
    with redgettext:

    .. code-block:: none

        redgettext --command-docstrings --recursive path/to/cogpackage

-------------
API Reference
-------------

.. automodule:: redbot.core.i18n
    :members:
    :special-members: __call__
    :member-order: bysource
