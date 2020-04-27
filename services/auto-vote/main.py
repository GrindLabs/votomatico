import logging

from jobs.globo import do_vote
from jsonrpc import JSONRPCResponseManager, dispatcher
from prettyconf import config
from werkzeug.exceptions import Unauthorized
from werkzeug.serving import run_simple
from werkzeug.wrappers import Request, Response

logging.basicConfig(format='%(asctime)s [%(levelname)s] %(message)s',
                    datefmt='%d-%m-%Y %H:%M:%S%z',
                    level=logging.DEBUG if config('DEBUG', cast=int) else
                    logging.WARNING)


@dispatcher.add_method
def enqueue_bbb_votes(**kwargs):
    return do_vote(
        kwargs['cookies'],
        kwargs['referer'],
        kwargs['pollResourceId'],
        kwargs['optionId'],
        kwargs['optionUuid']
    )


@Request.application
def application(request):
    response = JSONRPCResponseManager.handle(request.data, dispatcher)
    return Response(response.json, mimetype='application/json')


def main():
    run_simple(config('RPC_SERVER_HOST'), config(
        'RPC_SERVER_PORT', cast=int), application)


if __name__ == '__main__':
    main()
