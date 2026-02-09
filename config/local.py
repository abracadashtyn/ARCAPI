import keyring

# local environment configuration
class LocalConfig(object):
    # MySQL configuration
    '''mysql_server = "localhost"
    db_name = "replaygenie"
    mysql_username = keyring.get_password("replaygenie","mysql_username")
    mysql_password = keyring.get_password("replaygenie","mysql_password")
    SQLALCHEMY_DATABASE_URI = 'mysql://' + mysql_username + ':' + mysql_password + '@' + mysql_server + '/' + db_name'''

    MYSQL_USER = keyring.get_password("replaygenie","mysql_username")
    MYSQL_PASSWORD = keyring.get_password("replaygenie","mysql_password")
    MYSQL_HOST = "localhost"
    MYSQL_DB = "replaygenie"
    SQLALCHEMY_DATABASE_URI = f'mysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}/{MYSQL_DB}'


