import json
import logging
import random
import time

import requests

from definitions import PROXIES_FILE
from prettyconf import config

logging.basicConfig(format='%(asctime)s [%(levelname)s] %(message)s',
                    datefmt='%d-%m-%Y %H:%M:%S%z',
                    level=logging.DEBUG if config('DEBUG', cast=int) else
                    logging.WARNING)


def wait():
    time.sleep(random.randint(
        config('VOTOMATICO_MIN_WAIT', cast=int),
        config('VOTOMATICO_MAX_WAIT', cast=int)
    ))


def get_poll_session(cookies, referer, poll_resource_id):
    try:
        r = requests.get(
            config('GLOBO_POLL_SESSION_URI').format(poll_resource_id),
            headers={
                'Origin': config('GLOBO_HEADER_ORIGIN'),
                'User-Agent': config('VOTOMATICO_USER_AGENT'),
                'Referer': referer
            },
            cookies=cookies
        )
        r.raise_for_status()
        json_data = r.json()
        return {
            'captcha': json_data['configuration']['challenge'],
            'word': json_data['configuration']['word'],
            'session': json_data['session']
        }
    except (json.decoder.JSONDecodeError, requests.exceptions.HTTPError,
            KeyError):
        logging.error('The poll session is over')
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        logging.error('Unable to access the URL')

    return None


def do_vote(cookies, referer, poll_resource_id, option_id, option_uuid):
    valid_votes = 0
    proxies = json.load(open(PROXIES_FILE))
    logging.info('Starting votes for option %s', option_uuid)

    while True:
        poll = get_poll_session(
            requests.utils.cookiejar_from_dict(json.loads(cookies)),
            referer,
            poll_resource_id
        )

        if poll is None:
            break

        try:
            r = requests.post(
                config('VOTOMATICO_IMGRECON_SERVICE_URI'),
                json={
                    'method': 'img_recognizer',
                    'params': poll,
                    'jsonrpc': '2.0',
                    'id': int(round(time.time() * 1000))
                }
            )
            axis = r.json()['result']
            logging.debug('The axis result is %s', axis)
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout):
            logging.error('Unable to access the image recognition service')
            continue
        except (KeyError, json.decoder.JSONDecodeError):
            logging.error(
                'There is an error with the image recognition service %s',
                r.text)
            continue

        if axis is None:
            logging.warn('Impossible to solve the captcha... retrying')
            wait()
            continue

        try:
            r = requests.post(
                config('GLOBO_VOTE_URI').format(
                    poll_resource_id,
                    axis['posX'],
                    axis['posY'],
                    poll['session']
                ),
                json={
                    'optionId': option_id,
                    'optionUUID': option_uuid,
                    'value': option_id,
                    'pollResourceId': poll_resource_id
                },
                cookies=requests.utils.cookiejar_from_dict(
                    json.loads(cookies)),
                headers={
                    'Origin': config('GLOBO_HEADER_ORIGIN'),
                    'User-Agent': config('VOTOMATICO_USER_AGENT'),
                    'Referer': referer
                },
                proxies=random.choice(proxies)
            )
            logging.debug('Server response with status %s and data %s',
                          r.status_code, r.text)

            if r.raise_for_status() is None and not r.json():
                valid_votes += 1
            else:
                logging.debug('Leaving the vote worker [status=%s] %s',
                              r.status_code, r.text)
                break
        except (json.decoder.JSONDecodeError,
                requests.exceptions.HTTPError):
            logging.warn('The user reaches his vote limit')
            break
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout):
            logging.error(
                'Unable to reach the Globo\'s Vote Service... retrying')
            continue

        logging.debug('It has %s valid votes for option %s',
                      valid_votes, option_uuid)
        wait()

    logging.info('Finished votes for option %s with %s valid votes',
                 option_uuid, valid_votes)
    return valid_votes
