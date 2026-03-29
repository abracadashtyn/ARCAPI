import os

# environment configuration on DigitalOcean Droplet
class DigitalOceanConfig(object):
    # MySQL configuration
    MYSQL_USER = os.environ.get('DB_USER')
    MYSQL_PASSWORD = os.environ.get('DB_PASSWORD')
    MYSQL_HOST = os.environ.get('DB_HOST')
    MYSQL_DB = os.environ.get('DB_NAME')
    SQLALCHEMY_DATABASE_URI = f'mysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}/{MYSQL_DB}'

    BASE_URL = 'https://arcvgc.com'