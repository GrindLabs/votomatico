import logging
import sys

# Logging settings
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)-8s %(name)-15s %(message)s",
    stream=sys.stdout,
)

# Reality Shows settings
TV_SHOW_URL_VALIDATION = {
    "bbb": [
        r".*\/realities\/bbb\/bbb-\d+\/enquete-bbb\/votacao/?",
        r".*\/realities\/bbb\/bbb-\d+\/voto-da-torcida\/votacao\/?",
    ]
}
