import hashlib
import json
import logging
import random
import time
from datetime import datetime, timedelta, timezone

import google.auth
import requests
from google.cloud import tasks_v2beta3
from google.protobuf import timestamp_pb2

import hug
from definitions import PROXIES_FILE
from googleapiclient import discovery
from googleapiclient.errors import HttpError
from models import Poll, User, UserToken, Vote
from prettyconf import config
from requests_html import HTMLSession

logging.basicConfig(format='%(asctime)s [%(levelname)s] %(message)s',
                    datefmt='%d-%m-%Y %H:%M:%S%z',
                    level=logging.DEBUG if config('DEBUG', cast=int) else
                    logging.WARNING)
proxies = json.load(open(PROXIES_FILE))


@hug.directive()
def cors(support=config('VOTOMATICO_CORS'), response=None, **kwargs):
    response and response.set_header('Access-Control-Allow-Origin', support)


@hug.local()
def globo_user_info(cookies):
    r = requests.post(
        config('GLOBO_AUTH_USER_URL'),
        headers={
            'Origin': config('GLOBO_HEADER_ORIGIN'),
            'User-Agent': config('VOTOMATICO_USER_AGENT')
        },
        cookies=cookies,
        proxies=random.choice(proxies)
    ).json()
    return r


@hug.local()
def save_tasks(tasks):
    salty = config('VOTOMATICO_HMAC_KEY')
    poll_uuid = hashlib.sha1('{0}{1}'.format(
        salty, datetime.now().isoformat()).encode('utf-8')).hexdigest()

    for task in tasks:
        user = User.get(User.id == task['userId'])
        vote = Vote.create(
            job_id=task['task'].name,
            created_at=datetime.fromtimestamp(task['task'].create_time.seconds)
            .isoformat()
        )
        Poll.create(
            vmo_vote_id=vote,
            glb_user_id=user,
            uuid=poll_uuid
        )

    return poll_uuid


@hug.local()
def assert_hashes(hug_cors, hashes, users):
    return hashes == captcha_hashes(hug_cors, {'users[]': users})['data']


@hug.local()
def captcha_verify(token, hashes):
    r = requests.post(
        config('VOTOMATICO_CRYPTOLOOT_URI'),
        json={
            'secret': config('VOTOMATICO_CRYPTOLOOT_KEY'),
            'token': token,
            'hashes': hashes
        },
        headers={
            'Content-type': 'application/x-www-form-urlencoded'
        }
    )
    json_data = r.json()

    return json_data['success'] if 'success' in json_data else False


@hug.post('/contactus')
def contact(hug_cors, body):
    name = body['name'] if body and 'name' in body else ''
    email = body['email'] if body and 'email' in body else ''
    subject = body['subject'] if body and 'subject' in body else ''
    message = body['message'] if body and 'message' in body else ''
    token = body['token'] if body and 'token' in body else ''

    logging.debug([name, email, subject, message, token])

    if not name or not email or not subject or not message or not token:
        return {
            'error': True,
            'message': 'Um ou mais campos inválidos',
            'data': None
        }

    if not captcha_verify(token, 1024):
        return {
            'error': True,
            'message': 'Captcha inválido',
            'data': None
        }

    r = requests.post(
        config('MAILGUN_ENDPOINT').format(config('MAILGUN_DOMAIN')),
        auth=('api', config('MAILGUN_APIKEY')),
        data={
            'from': '{0} <{1}>'.format(name, email),
            'to': [config('MAILGUN_VALID_EMAIL')],
            'subject': subject,
            'text': message
        }
    )

    try:
        r.raise_for_status()
    except requests.exceptions.HTTPError:
        return {
            'error': True,
            'message': 'O servidor de e-mails não está respondendo',
            'data': None
        }

    json_data = r.json()
    logging.debug(json_data)
    return {
        'error': False,
        'message': 'E-mail enviado com sucesso',
        'data': None
    }


@hug.post('/captcha/hashes')
def captcha_hashes(hug_cors, body):
    users_uuids = body['users[]'] if body and 'users[]' in body else []
    logging.debug(users_uuids)
    logging.debug(body)

    if not users_uuids:
        return {
            'error': False,
            'message': 'Nenhum usuário selecionado',
            'data': config('VOTOMATICO_CRYPTOLOOT_HASHES', cast=int)
        }

    if not isinstance(users_uuids, list):
        users_uuids = [users_uuids]

    try:
        votes = (Vote
                 .select()
                 .join(Poll)
                 .join(User)
                 .where(
                     User.id << (User
                                 .select()
                                 .where(User.globo_uuid << users_uuids)),
                     Vote.created_at >= (
                         datetime.utcnow() - timedelta(hours=1))
                 ))
        logging.debug(votes)
    except (User.DoesNotExist, Vote.DoesNotExist):
        return {
            'error': True,
            'message': 'Informações inválidas',
            'data': None
        }

    return {
        'error': False,
        'message': 'Hash computado',
        'data': config('VOTOMATICO_CRYPTOLOOT_HASHES', cast=int) * (
            len(votes) if len(votes) else 1)
    }


@hug.get('/poll/{id}')
def watch_poll(hug_cors, id: hug.types.text):
    polls = (User
             .select(User.id, User.name, User.email, Vote.job_id, Vote.result)
             .join(Poll)
             .join(Vote)
             .where(Poll.uuid == id)
             .dicts())

    if not polls:
        return {
            'error': True,
            'message': 'Identificador de votação inválido',
            'data': None
        }

    credentials, _ = google.auth.default(
        scopes=['https://www.googleapis.com/auth/cloud-tasks'])
    vmo_queue = discovery.build(
        'cloudtasks', 'v2beta3', credentials=credentials,
        cache_discovery=False)

    for poll in polls:
        try:
            req = vmo_queue.projects().locations(
            ).queues().tasks().get(name=poll['job_id'])
            res = req.execute()
            logging.debug(res)
        except HttpError:
            query = Poll.delete().where(
                Poll.uuid == id,
                Poll.glb_user_id == poll['id']
            )
            query.execute()
            return {
                'error': True,
                'message': 'Votação com erros ou não finalizada',
                'data': None
            }

    return None
    #     r = requests.post(
    #         config('VOTOMATICO_VOTE_SERVICE_URI'),
    #         json={
    #             'method': 'get_result',
    #             'params': {
    #                 'job_id': poll['job_id']
    #             },
    #             'jsonrpc': '2.0',
    #             'id': int(round(time.time() * 1000))
    #         }
    #     )

    #     try:
    #         r.raise_for_status()
    #     except requests.exceptions.HTTPError:
    #         return {
    #             'error': True,
    #             'message': 'O serviço de votação não está respondendo',
    #             'data': None
    #         }

    #     json_data = r.json()

    #     if 'error' in json_data:
    #         return {
    #             'error': True,
    #             'message': 'O serviço não conseguiu recuperar os resultados',
    #             'data': None
    #         }

    #     if json_data['result']:
    #         vote = Vote.get(Vote.job_id == poll['job_id'])

    #         if not vote.result:
    #             vote.finished_at = datetime.strptime(
    #                 json_data['result']['finishedAt'], '%Y-%m-%dT%H:%M:%S.%f')
    #             vote.result = json_data['result']['result']
    #             vote.save()

    # return {
    #     'error': False,
    #     'message': 'Acompanhamento da votação',
    #     'data': [{
    #         'name': p['name'],
    #         'email': p['email'],
    #         'result': p['result']
    #     } for p in polls]
    # }


@hug.post('/globo/login')
def globo_login(hug_cors, body):
    email = body['email'] if body and 'email' in body else ''
    password = body['password'] if body and 'password' in body else ''
    r = requests.post(
        config('GLOBO_AUTH_URL'),
        json={
            'payload': {
                'email': email,
                'password': password,
                'serviceId': config('GLOBO_AUTH_SERVICE_ID', cast=int)
            },
            'fingerprint': config('GLOBO_AUTH_FINGERPRINT'),
            'captcha': config('GLOBO_AUTH_CAPTCHA')
        },
        headers={
            'Origin': config('GLOBO_HEADER_ORIGIN'),
            'User-Agent': config('VOTOMATICO_USER_AGENT')
        },
        proxies=random.choice(proxies)
    )
    json_data = r.json()
    has_error = True if json_data['id'] != 'Authenticated' else False

    if not has_error:
        cookies = r.cookies
        user_info = globo_user_info(cookies)

        try:
            user = User.get(User.globo_uuid == user_info['globoId'])
        except User.DoesNotExist:
            user_token = UserToken.create(
                token=user_info['token'],
                cookies=json.dumps(cookies.get_dict()),
                updated_at=datetime.now(timezone.utc)
            )
            birthday = datetime.strptime(user_info['dateOfBirth'],
                                         '%Y-%m-%dT%H:%M:%S%z') \
                if 'dateOfBirth' in user_info else None
            user = User.create(
                email=user_info['email'],
                name=user_info['name'] if 'name' in user_info else None,
                birthday=datetime.strftime(
                    birthday, '%Y-%m-%d') if birthday else None,
                gender=user_info['gender'] if 'gender' in user_info else None,
                city=user_info['address']['city'] if 'address' in user_info
                else None,
                state=user_info['address']['state'] if 'address' in user_info
                else None,
                globo_id=user_info['id'] if 'id' in user_info else None,
                globo_code=user_info['code'] if 'code' in user_info else None,
                globo_uuid=user_info['globoId'] if 'globoId' in user_info
                else None
            )
            user.glb_user_token_id = user_token
            user.save()

    return {
        'error': has_error,
        'message': json_data['userMessage'],
        'data': None if has_error else {
            'name': user.name,
            'email': user.email,
            'uuid': user.globo_uuid
        }
    }


@hug.get('/globo/bbb/status')
def globo_bbb_status(hug_cors):
    session = HTMLSession()
    r = session.get(
        config('GLOBO_POLL_STATUS'),
        headers={
            'Origin': config('GLOBO_HEADER_ORIGIN'),
            'User-Agent': config('VOTOMATICO_USER_AGENT')
        },
        proxies=random.choice(proxies)
    )
    status = r.html.find('div.type-enquete a', first=True)

    if status:
        return {
            'error': False,
            'message': 'Votação aberta',
            'data': status.attrs['href']
        }

    return {
        'error': True,
        'message': 'Votação encerrada',
        'data': None
    }


@hug.get('/globo/bbb/poll')
def globo_bbb_poll(hug_cors):
    status = globo_bbb_status(hug_cors)

    if not status['error']:
        session = HTMLSession()
        r = session.get(
            status['data'],
            headers={
                'Origin': config('GLOBO_HEADER_ORIGIN'),
                'User-Agent': config('VOTOMATICO_USER_AGENT')
            },
            proxies=random.choice(proxies)
        )
        poll = r.html.find(
            'a.glb-poll-option-title, a.glb-poll-option-hover-action')
        options = []

        for option in poll:
            options.append({
                'pollId': option.attrs['data-poll-resource-id'],
                'optionId': option.attrs['data-option-id'],
                'optionUUID': option.attrs['data-option-uuid'],
                'optionTitle': option.attrs['data-title'],
                'optionImageURL': option.attrs['data-image'] if 'data-image'
                in option.attrs else None
            })

        return {
            'error': False,
            'message': 'Votação em andamento',
            'data': {
                'referer': status['data'],
                'options': options
            }
        }

    return {
        'error': True,
        'message': 'Não há votação em andamento',
        'data': None
    }


@hug.post('/globo/bbb/vote')
def globo_bbb_vote(hug_cors, body):
    users = body['users[]'] if body and 'users[]' in body else []
    referer = body['referer'] if body and 'referer' in body else ''
    poll_resource_id = body['pollResourceId'] if body and 'pollResourceId' \
        in body else ''
    option_id = int(body['optionId']) if body and 'optionId' in body else None
    option_uuid = body['optionUuid'] if body and 'optionUuid' in body else ''
    token = body['token'] if body and 'token' in body else None
    hashes = int(body['hashes']) if body and 'hashes' in body else None

    # Fix list issue when the variable is a string
    if not isinstance(users, list):
        users = [users]

    if not users or not referer or not poll_resource_id \
            or not isinstance(option_id, int) or not option_uuid or not token \
            or not isinstance(hashes, int):
        return {
            'error': True,
            'message': 'Um ou mais campos inválidos',
            'data': None
        }

    if not assert_hashes(hug_cors, hashes, users):
        return {
            'error': True,
            'message': 'Hash incompatível, por favor atualize a página',
            'data': None
        }

    if not captcha_verify(token, hashes):
        return {
            'error': True,
            'message': 'Captcha inválido',
            'data': None
        }

    cookie_jar = []

    try:
        for globo_uuid in users:
            user = User.get(User.globo_uuid == globo_uuid)
            cookie_jar.append({
                'userId': user.id,
                'cookies': user.glb_user_token_id.cookies
            })
    except User.DoesNotExist:
        return {
            'error': True,
            'message': 'O usuário informado não existe',
            'data': None
        }

    client = tasks_v2beta3.CloudTasksClient()
    parent = client.queue_path(
        config('CLOUD_QUEUE_PROJECT_ID'),
        config('CLOUD_QUEUE_LOCATION'),
        config('CLOUD_QUEUE_ID')
    )
    task = {
        'app_engine_http_request': {
            'app_engine_routing': {
                'service': 'vmo-vote'
            },
            'http_method': 'POST',
            'relative_uri': '/jsonrpc'
        }
    }
    tasks = []

    for cookies in cookie_jar:
        payload = {
            'method': 'enqueue_bbb_votes',
            'params': {
                'cookies': cookies['cookies'],
                'referer': referer,
                'pollResourceId': poll_resource_id,
                'optionId': option_id,
                'optionUuid': option_uuid
            },
            'jsonrpc': '2.0',
            'id': int(round(time.time() * 1000))
        }
        task['app_engine_http_request']['body'] = (json.dumps(
            payload)).encode('utf-8')
        curr_time = datetime.utcnow() + timedelta(seconds=1)
        timestamp = timestamp_pb2.Timestamp()
        timestamp.FromDatetime(curr_time)
        task['schedule_time'] = timestamp
        res = client.create_task(parent, task)
        tasks.append({
            'userId': cookies['userId'],
            'task': res
        })
        logging.debug(res)

    return {
        'error': False,
        'message': 'Votação automática iniciada',
        'data': save_tasks(tasks)
    }
