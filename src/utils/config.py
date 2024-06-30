"""
Make sure to have a "config.ini" file that has the following template:
[BOT]
token = kansbdqwohzxmnmqweabksdb
verbose = True

[XRPL]
testnet_link = wss://s.altnet.rippletest.net:51233/
mainnet_link = wss://s1.ripple.com/
test_mode = False
verbose = True

[DB]
db_server = 192.168.254.100
db_name = databaseName
db_username = root
db_password = password
"""

from configparser import ConfigParser

baseConfig = ConfigParser()
baseConfig.read("config.ini")

coinsConfig = baseConfig['COINS']
botConfig = baseConfig['BOT']
xrplConfig = baseConfig['XRPL']
dbConfig = baseConfig['DATABASE']