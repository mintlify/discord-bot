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
token: str | None = os.environ.get("MINTLIFYBOTTOKEN")
username: str | None = os.environ.get("DATABASEUSERNAME")
password: str | None = os.environ.get("DATABASEPASSWORD")
database: str | None = os.environ.get("DATABASENAMEMINTLIFY")
config_path = "../config/config.json"
try:
    db_connection = pymysql.connect(
        host="127.0.0.1",
        user=username,
        password=password,
        database=database,
        port=3306,
    )
    print(
        "\u001b[32mSuccessfully connected to: %s \u001b[0m"
        % (db_connection.get_server_info()),
    )
    cursor = db_connection.cursor()
except Exception as e:
    print(
        "\u001b[31mFailed to connect to server/database.\n\u001b[35mError description: %s \u001b[0m"
        % (repr(e)),
    )
    sys.exit(-1)
bot = discord.Bot(
    intents=discord.Intents.all(),
    command_prefix="/",
    case_insensitive=True,
)
bot.add_cog(StandardCommands(bot, db_connection, cursor))
bot.add_cog(TicketCommands(bot, db_connection))

# / Config
# ----------------------------------------------------------------
with open(config_path, encoding="utf-8") as config_file:
    config = json.load(config_file)
    staff_roles = config["staff_roles"]
    administrator_role = config["administrator_role"]
    config_file.close()

if __name__ == "__main__":
    try:
        bot.run(token)
    except Exception as e:
        print(
            "\u001b[31mFailed to run bot.\n\u001b[35mError description: %s \u001b[0m"
            % (repr(e)),
        )
        sys.exit(-1)
