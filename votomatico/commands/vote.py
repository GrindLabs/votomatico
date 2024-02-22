import logging

import click

from votomatico.utils.browser import Browser

logger = logging.getLogger(__name__)


@click.command()
@click.argument("url", type=str, required=True)
@click.option("--choice-idx", type=int, help="Which option should be voted", required=True)
@click.option("--concurrency", type=int, help="Amount of simultaneous requests", default=5)
@click.option("--vote-limit", type=int, help="Max amount of votes given (0 to disable the limit)", default=5000)
@click.pass_context
def vote(ctx, url, choice_idx, concurrency, vote_limit):
    """Automatize the vote process"""
    browser: Browser = ctx.obj["BROWSER"]
    page = browser.open_new_tab()
    page.goto(url)

    if page.get_by_text("Votação encerrada"):
        logger.warning("Voting ended")
        return

    choices = page.locator('//*[@id="roulette-root"]/div/main/div[1]/div/ul/li').all()

    try:
        choice = choices[choice_idx]
    except IndexError:
        logger.error("Invalid option index: %d", choice_idx)
        return

    logger.info("Voting to %s...", choice.get_by_role("button").get_attribute("aria-label"))

    for i in range(0, vote_limit):
        choice.get_by_role("button").click()
        page.wait_for_timeout(2000)
        page.wait_for_selector('//*[@id="roulette-root"]/div/main/div[1]/div/div[3]/div[1]/iframe')
        page.frame_locator('//*[@id="roulette-root"]/div/main/div[1]/div/div[3]/div[1]/iframe').locator('//div[@id="checkbox"]').click()
        logger.info("Vote %d of %d to %s", i + 1, vote_limit, choice.get_by_role("button").get_attribute("aria-label"))
        page.wait_for_timeout(2000)
        page.locator('//*[@id="roulette-root"]/div/main/div[9]/div/div/div/div[1]/div[2]/button').click()

    page.close()
