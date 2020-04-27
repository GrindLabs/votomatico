import base64
import logging
import os

import cv2
import numpy as np
from jsonrpc import JSONRPCResponseManager, dispatcher
from prettyconf import config
from slugify import slugify
from werkzeug.exceptions import Unauthorized
from werkzeug.serving import run_simple
from werkzeug.wrappers import Request, Response

logging.basicConfig(format='%(asctime)s [%(levelname)s] %(message)s',
                    datefmt='%d-%m-%Y %H:%M:%S%z',
                    level=logging.DEBUG if config('DEBUG', cast=int) else
                    logging.WARNING)


def load_b64image(b64image):
    nparr = np.frombuffer(base64.b64decode(b64image), np.uint8)
    return cv2.imdecode(nparr, cv2.IMREAD_COLOR)


@dispatcher.add_method
def img_recognizer(**kwargs):
    captcha = load_b64image(kwargs['captcha'])
    tiles_path = config('TILES_PATH').format(
        os.path.dirname(os.path.abspath(__file__)),
        slugify(kwargs['word'])
    )
    template = cv2.imread(tiles_path)

    if template is not None:
        width, height = template.shape[:-1]
        match = cv2.matchTemplate(captcha, template, cv2.TM_CCOEFF_NORMED)
        coord = np.where(match >= config('RECOGNITION_THRESHOLD', cast=float))
        x_axis, y_axis = coord[::-1]

        if any(x_axis) and any(y_axis):
            return {
                'posX': int(x_axis[0] + width/2),
                'posY': int(y_axis[0] + height/2)
            }

    return None


@Request.application
def application(request):
    response = JSONRPCResponseManager.handle(request.data, dispatcher)
    return Response(response.json, mimetype='application/json')


if __name__ == '__main__':
    run_simple(config('HOST'), config(
        'PORT', cast=int), application)
