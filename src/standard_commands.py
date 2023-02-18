import time

from tcp_latency import measure_latency
from discord.ext import commands

from messages import *
from EmbedBuilder import EmbedBuilder


class StandardCommands(commands.Cog):

    def __init__(self, bot, db_connection, cursor):
        self.bot = bot
        self.db_connection = db_connection
        self.cursor = cursor

    @commands.slash_command(name="ping", description="Check the bot's latency")
    async def ping(self, ctx):
        start: float = time.perf_counter()
        self.db_connection.ping()
        cursor = self.db_connection.cursor()
        cursor.execute("SELECT * FROM ping")
        cursor.fetchall()
        self.db_connection.commit()
        end: float = time.perf_counter()
        # Calculate database latency
        latency: int = round((end - start) * 1000)
        network_latency: float = round(
            measure_latency(host='google.com')[0], 2)
        embed = EmbedBuilder(
            "Ping",
            f"**Database Latency:** {latency}ms\n**Network Latency:** {network_latency}ms").build()
        await ctx.respond(embed=embed, ephemeral=True)

    @commands.slash_command(name="staff",
                            description="Meet the Community Staff!")
    async def staff(self, ctx) -> None:
        embed = EmbedBuilder(
            "Meet the Community Staff!",
            STAFF_MESSAGE).build()
        await ctx.respond(embed=embed, ephemeral=True)

    @commands.slash_command(name="help", description="Display help message.")
    async def helpme(self, ctx) -> None:
        embed = EmbedBuilder("Help", HELP_MESSAGE).build()
        await ctx.respond(embed=embed, ephemeral=True)
