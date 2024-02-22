import logging
import os

from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright
from playwright_stealth import stealth_sync

logger = logging.getLogger(__name__)


class Browser:
    __browser: Browser
    __context: BrowserContext

    def __init__(self) -> None:
        playwright = sync_playwright().start()
        self.__browser = playwright.chromium.launch_persistent_context(
            user_data_dir=f"{os.getcwd()}/votomatico/resources/profiles/",
            headless=False,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-infobars",
                "--single-process",
                "--no-zygote",
                "--no-first-run",
                "--window-size=1280,800",
                "--window-position=0,0",
                "--ignore-certificate-errors",
                "--ignore-certificate-errors-skip-list",
                "--disable-dev-shm-usage",
                "--disable-accelerated-2d-canvas",
                "--disable-gpu",
                "--hide-scrollbars",
                "--disable-notifications",
                "--disable-background-timer-throttling",
                "--disable-backgrounding-occluded-windows",
                "--disable-breakpad",
                "--disable-component-extensions-with-background-pages",
                "--disable-extensions",
                "--disable-features=TranslateUI,BlinkGenPropertyTrees",
                "--disable-ipc-flooding-protection",
                "--disable-renderer-backgrounding",
                "--enable-features=NetworkService,NetworkServiceInProcess",
                "--force-color-profile=srgb",
                "--metrics-recording-only",
                "--mute-audio",
                # TODO: Add hCaptcha extension
                # f"--disable-extensions-except={os.getcwd()}/votomatico/resources/extensions/hCaptcha-Solver",
                # f"--load-extension={os.getcwd()}/votomatico/resources/extensions/hCaptcha-Solver",
            ],
        )
        logger.info("New browser started")
        self.__context = self.__browser
        logger.info("Created new context")
        self.__context.add_cookies(
            [
                {
                    "name": "GLOBO_ID",
                    "value": os.getenv("GLOBO_ID", ""),
                    "domain": ".globo.com",
                    "path": "/",
                },
                {
                    "name": "GLBID",
                    "value": os.getenv("GLBID", ""),
                    "domain": ".globo.com",
                    "path": "/",
                },
                {
                    "name": "AUTH_SESSION_ID",
                    "value": os.getenv("AUTH_SESSION_ID", ""),
                    "domain": "id.globo.com",
                    "path": "/auth/realms/globo.com/",
                },
                {
                    "name": "KEYCLOAK_IDENTITY",
                    "value": os.getenv("KEYCLOAK_IDENTITY", ""),
                    "domain": "id.globo.com",
                    "path": "/auth/realms/globo.com/",
                },
                {
                    "name": "KEYCLOAK_REMEMBER_ME",
                    "value": os.getenv("KEYCLOAK_REMEMBER_ME", ""),
                    "domain": "id.globo.com",
                    "path": "/auth/realms/globo.com/",
                },
                {
                    "name": "KEYCLOAK_SESSION",
                    "value": os.getenv("KEYCLOAK_SESSION", ""),
                    "domain": "id.globo.com",
                    "path": "/auth/realms/globo.com/",
                },
            ]
        )

    def __del__(self) -> None:
        self.close()

    def open_new_tab(self) -> Page:
        page = self.__context.new_page()
        stealth_sync(page)
        return page

    def get_current_context(self) -> BrowserContext:
        return self.__context

    def count_open_contexts(self) -> int:
        return len(self.__browser.contexts())

    def close(self) -> None:
        self.__context.close()
        logger.info("Context closed")
        self.__browser.close()
        logger.info("Browser closed")
