import logging

import click

import votomatico.settings as settings
from votomatico.commands.vote import vote
from votomatico.utils.browser import Browser

logger = logging.getLogger(__name__)


@click.group()
@click.pass_context
def cli(ctx):
    ctx.ensure_object(dict)
    ctx.obj["SETTINGS"] = settings
    ctx.obj["BROWSER"] = Browser()
    ctx.call_on_close(lambda: ctx.obj["BROWSER"].close())


cli.add_command(vote)

if __name__ == "__main__":
    cli(obj={})
