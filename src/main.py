# / Mintlify Bot Version 1.0.0
# ----------------------------------------------------------------
"""
Mintlify Bot is a custom Discord bot to handle the Mintlify Discord server.
Find out more about Mintlify here: https://mintlify.com
"""
# / Imports
# ----------------------------------------------------------------
import asyncio, datetime, json, random, time, discord, pymysql, os, sys, discord.ext
from tcp_latency import measure_latency
from messages import *
# ----------------------------------------------------------------
# / Globals
# ----------------------------------------------------------------
token = os.environ.get("MintlifyBotToken")
username = os.environ.get("DatabaseUsername")
password = os.environ.get("DatabasePassword")
database = os.environ.get("DatabaseNameMintlify")
config_path = "../config/config.json"
bot = discord.Bot(intents=discord.Intents.all(), command_prefix='/', case_insensitive=True)
# / Config
# ----------------------------------------------------------------
with open(config_path) as config_file:
    config = json.load(config_file)
    config_file.close()

# / Classes
# ----------------------------------------------------------------
class EmbedBuilder:
    def __init__(self, title, description, color=0x18e299, image=None):
        self.title = title
        self.description = description
        self.color = color
        self.footer = "Powered by Mintlify"
        self.image = image
    def build(self):
        embed = discord.Embed(title=self.title, description=self.description, color=self.color)
        if self.image:
            embed.set_image(url=self.image)
        embed.set_footer(text=self.footer)
        return embed
# / Procedures
# ----------------------------------------------------------------

# Ping latency
@bot.slash_command(name="ping", description="Check bot latency.")
async def ping(ctx):
    start = time.perf_counter()
    db_connection.ping()
    cursor.execute("SELECT * FROM ping")
    cursor.fetchall()
    db_connection.commit()
    end = time.perf_counter()
    # Calculate database latency
    latency = round((end - start) * 1000)
    network_latency = round(measure_latency(host='google.com')[0], 2)
    embed = EmbedBuilder("Ping", f"**Database Latency:** {latency}ms\n**Network Latency:** {network_latency}ms").build()
    await ctx.respond(embed=embed, ephemeral=True)

# Meet the staff!
@bot.slash_command(name="staff", description="Meet the Mintlify staff!")
async def staff(ctx):
    embed = EmbedBuilder("Meet the Mintlify Staff!", staff_message).build()
    await ctx.respond(embed=embed, ephemeral=True)

# On Bot Load
@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Game('/support'))

# Catch any exceptions
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, discord.DiscordException):
        error_message = EmbedBuilder("Exception", error)
        error_message.build()
        await ctx.respond(embed=error_message, ephemeral=True)
    elif isinstance(error, discord.ext.commands.errors.CommandNotFound):
        error_message = EmbedBuilder("Command Not Found", "The command you entered was not found. Please try again.")
        error_message.build()
        await ctx.respond(embed=error_message, ephemeral=True)
    else:
        # Log error with the timestamp in logs folder
        with open("../logs/error.log", "a") as error_log:
            error_log.write(f"[{datetime.datetime.now()}] | {error}\n")
            error_log.close()
        error_message = EmbedBuilder("Unknown Error", "An unknown error has occurred, this has been logged. \nQuote timestamp: %s " % datetime.datetime.now())
        error_message.build()
        await ctx.respond(embed=error_message, ephemeral=True)

if __name__ == '__main__':
    try:
        db_connection = pymysql.connect(host='127.0.0.1', user=username, password=password, database=database, port=3306)
        print("\u001b[32mSuccessfully connected to: %s \u001b[0m" % (db_connection.get_server_info()))
        cursor = db_connection.cursor()
        bot.run(token)
    except Exception as e:
        print("\u001b[31mFailed to connect to server/database.\n\u001b[35mError description: %s \u001b[0m" % (repr(e)))
        sys.exit(-1)