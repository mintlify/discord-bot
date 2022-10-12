import json
import os
import sys

import discord.ext
import pymysql

from standard_commands import StandardCommands
from TicketSystem import TicketCommands

# ----------------------------------------------------------------
# / Globals
# ----------------------------------------------------------------
token: str | None = os.environ.get("MintlifyBotToken")
username: str | None = os.environ.get("DatabaseUsername")
password: str | None = os.environ.get("DatabasePassword")
database: str | None = os.environ.get("DatabaseNameMintlify")
config_path: str = "../config/config.json"
try:
    db_connection: pymysql.connections.Connection = pymysql.connect(
        host='127.0.0.1',
        user=username,
        password=password,
        database=database,
        port=3306)
    print("\u001b[32mSuccessfully connected to: %s \u001b[0m" %
          (db_connection.get_server_info()))
    cursor: pymysql.cursors.Cursor = db_connection.cursor()
except Exception as e:
    print(
        "\u001b[31mFailed to connect to server/database.\n\u001b[35mError description: %s \u001b[0m" %
        (repr(e)))
    sys.exit(-1)
bot: discord.ext.commands.Bot = discord.Bot(
    intents=discord.Intents.all(),
    command_prefix='/',
    case_insensitive=True)
bot.add_cog(StandardCommands(bot, db_connection))
bot.add_cog(TicketCommands(bot, db_connection))

# / Config
# ----------------------------------------------------------------
with open(config_path) as config_file:
    config: dict = json.load(config_file)
    staff_roles: list = config["staff_roles"]
    administrator_role: str = config["administrator_role"]
    config_file.close()

if __name__ == '__main__':
    try:
        bot.run(token)
    except Exception as e:
        print(
            "\u001b[31mFailed to run bot.\n\u001b[35mError description: %s \u001b[0m" %
            (repr(e)))
        sys.exit(-1)
