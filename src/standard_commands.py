import time

from tcp_latency import measure_latency
from discord.ext import commands

from messages import *
from EmbedBuilder import EmbedBuilder


class StandardCommands(commands.Cog):
    def __init__(
        self, bot: commands.Bot, db_connection: object, cursor: object
    ) -> None:
        self.bot = bot
        self.db_connection = db_connection
        self.cursor = cursor

    @commands.slash_command(name="ping", description="Check the bot's latency")
    async def ping(self, ctx: commands.Context) -> None:
        start = time.perf_counter()
        self.db_connection.ping()
        cursor = self.db_connection.cursor()
        cursor.execute("SELECT * FROM ping")
        cursor.fetchall()
        self.db_connection.commit()
        end = time.perf_counter()
        # Calculate database latency
        latency = round((end - start) * 1000)
        network_latency = round(measure_latency(host="google.com")[0], 2)
        embed = EmbedBuilder(
            "Ping",
            f"**Database Latency:** {latency}ms\n**Network Latency:** {network_latency}ms",
        ).build()
        await ctx.respond(embed=embed, ephemeral=True)

    @commands.slash_command(name="staff", description="Meet the Community Staff!")
    async def staff(self, ctx: commands.Context) -> None:
        embed = EmbedBuilder("Meet the Community Staff!", staff_message).build()
        await ctx.respond(embed=embed, ephemeral=True)

    @commands.slash_command(name="help", description="Display help message.")
    async def helpme(self, ctx: commands.Context) -> None:
        embed = EmbedBuilder("Help", help_message).build()
        await ctx.respond(embed=embed, ephemeral=True)
