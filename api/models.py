import os

from peewee import *
from playhouse.db_url import connect
from playhouse.pool import PooledMySQLDatabase
from prettyconf import config

if os.environ.get('GAE_ENV') == 'standard':
    unix_socket = '/cloudsql/{}'.format(config('CLOUD_SQL_CONNECTION_NAME'))
    db = PooledMySQLDatabase(config('CLOUD_SQL_DATABASE_NAME'),
                             user=config('CLOUD_SQL_USERNAME'),
                             password=config('CLOUD_SQL_PASSWORD'),
                             unix_socket=unix_socket)
else:
    db = connect(config('MYSQL_CONN_URI').format(
        config('MYSQL_USER'),
        config('MYSQL_PASSWORD'),
        config('MYSQL_HOST'),
        config('MYSQL_PORT'),
        config('MYSQL_DATABASE')
    ))


class UserToken(Model):
    token = TextField(unique=True)
    cookies = TextField()
    updated_at = DateTimeField()

    class Meta:
        database = db
        table_name = 'glb_user_token'


class User(Model):
    email = CharField(max_length=255, unique=True)
    name = CharField(max_length=255)
    birthday = DateField()
    gender = FixedCharField(max_length=1)
    city = CharField(max_length=255)
    state = FixedCharField(max_length=2)
    globo_id = BigIntegerField()
    globo_code = CharField(max_length=255, unique=True)
    globo_uuid = CharField(max_length=255, unique=True)
    glb_user_token_id = ForeignKeyField(
        UserToken, to_field='id', backref='session', on_delete='CASCADE')

    class Meta:
        database = db
        table_name = 'glb_user'


class Vote(Model):
    job_id = CharField(max_length=255, unique=True)
    created_at = DateTimeField()
    finished_at = DateTimeField()
    result = IntegerField()

    class Meta:
        database = db
        table_name = 'vmo_vote'


class Poll(Model):
    vmo_vote_id = ForeignKeyField(Vote, on_delete='CASCADE')
    glb_user_id = ForeignKeyField(User)
    uuid = CharField(max_length=255)

    class Meta:
        database = db
        table_name = 'vmo_poll'
