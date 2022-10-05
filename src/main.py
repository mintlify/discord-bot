# / Mintlify Bot Version 1.0.0
# ----------------------------------------------------------------
"""
Mintlify Bot is a custom Discord bot to handle the Mintlify Discord server.
Find out more about Mintlify here: https://mintlify.com
"""
# / Imports
# ----------------------------------------------------------------
import asyncio
import datetime
import json
import os
import random
import string
import sys
import time

import discord
import discord.ext
import pymysql
from tcp_latency import measure_latency

from messages import *

# ----------------------------------------------------------------
# / Globals
# ----------------------------------------------------------------
lst: list[str] = list(string.ascii_letters + string.digits)
token: str | None = os.environ.get("MintlifyBotToken")
username: str | None = os.environ.get("DatabaseUsername")
password: str | None = os.environ.get("DatabasePassword")
database: str | None = os.environ.get("DatabaseNameMintlify")
config_path = "../config/config.json"
bot = discord.Bot(
    intents=discord.Intents.all(),
    command_prefix='/',
    case_insensitive=True)
# / Config
# ----------------------------------------------------------------
with open(config_path) as config_file:
    config = json.load(config_file)
    staff_roles = config["staff_roles"]
    administrator_role = config["administrator_role"]
    config_file.close()


# / Classes
# ----------------------------------------------------------------
class EmbedBuilder:
    def __init__(self, title, description, color=0x18e299, image=None) -> None:
        self.title = title
        self.description = description
        self.color = color
        self.footer = "Powered by Mintlify"
        self.image = image

    def build(self):
        embed = discord.Embed(
            title=self.title,
            description=self.description,
            color=self.color)
        if self.image:
            embed.set_image(url=self.image)
        embed.set_footer(text=self.footer)
        return embed


# / Procedures
# ----------------------------------------------------------------
# / Staff Commands
@bot.slash_command(name="open_tickets",
                   description="Get a list of currently open tickets.")
async def opentickets(ctx) -> None:
    if not any(role.id in staff_roles for role in ctx.author.roles):
        embed = EmbedBuilder(
            "Error", "You do not have permission to use this command.").build()
        await ctx.respond(embed=embed, ephemeral=True)
        return
    else:
        # Make request to database and return all tickets that are currently
        # open
        cursor.execute("SELECT * FROM tickets WHERE closed = 'N'")
        tickets = cursor.fetchall()
        db_connection.commit()
        if len(tickets) == 0:
            embed = EmbedBuilder("No Open Tickets",
                                 "There are currently no open tickets.").build()
            await ctx.respond(embed=embed, ephemeral=True)
            return
        # Create embed
        embed = discord.Embed(
            title="Open Ticket List",
            description="Here is a list of currently open tickets:",
            color=0x18e299)
        # Loop through tickets and add them to the embed
        for ticket in tickets:
            # Put datetime into readable format
            date = ticket[2].strftime("%d/%m/%Y %H:%M:%S")
            embed.add_field(
                name="Ticket ID: %s | Ticket Category: %s" %
                (ticket[0], ticket[1]), value="Ticket Opened: %s | Ticket Resolver: [%s] %s" %
                (date, ticket[7], ticket[6]), inline=True)
        await ctx.respond(embed=embed, ephemeral=True)


@bot.slash_command(name="get_transcript",
                   description="Get a transcript of a ticket.")
async def gettranscript(ctx, ticket_id: str) -> None:
    if any(role.id in staff_roles for role in ctx.author.roles):
        # Check if ticket exists
        db_connection.ping()
        cursor.execute(
            "SELECT transcript FROM tickets WHERE id = '%s'" %
            ticket_id)
        result = cursor.fetchone()
        db_connection.commit()
        if result is None:
            embed = EmbedBuilder(
                "Error", "This ticket does not exist.").build()
            await ctx.respond(embed=embed, ephemeral=True)
            return
        # Get file from transcript name in database
        cursor.execute(
            "SELECT transcript FROM tickets WHERE id = '%s'" %
            ticket_id)
        transcript = cursor.fetchone()
        db_connection.commit()
        path = "../transcripts/%s" % transcript[0]
        # Attach file to embed
        embed = discord.Embed(
            title="Transcript",
            description="Transcript for ticket: %s" %
            ticket_id,
            color=0x18e299)
        file = discord.File(path, filename="transcript.txt")
        await ctx.respond(embed=embed, file=file, ephemeral=True)
    else:
        embed = EmbedBuilder(
            "Error", "You do not have permission to use this command.").build()
        await ctx.respond(embed=embed, ephemeral=True)


@bot.slash_command(name="claim_ticket", description="Claim a ticket.")
async def claimticket(ctx, ticket_id: str) -> None:
    if any(role.id in staff_roles for role in ctx.author.roles):
        # Check if ticket exists
        db_connection.ping()
        cursor.execute("SELECT * FROM tickets WHERE id = '%s'" % ticket_id)
        result = cursor.fetchone()
        db_connection.commit()
        if result is None:
            embed = EmbedBuilder(
                "Error", "This ticket does not exist.").build()
            await ctx.respond(embed=embed, ephemeral=True)
            return
        # Check database to see if ticket has already been claimed
        cursor.execute("SELECT resolver FROM tickets WHERE id = %s", ticket_id)
        resolver = cursor.fetchone()
        db_connection.commit()
        if resolver[0] is not None:
            embed = EmbedBuilder(
                "Error", "This ticket has already been claimed.").build()
            await ctx.respond(embed=embed, ephemeral=True)
            return
        guild = ctx.guild
        # Get channel ID from the name of the channel
        channel = discord.utils.get(guild.channels, name=ticket_id)
        if channel is None:
            embed = EmbedBuilder(
                "Error", "This ticket does not exist.").build()
            await ctx.respond(embed=embed, ephemeral=True)
            return
        embed = discord.Embed(
            title="Ticket Claim",
            description=f"Claimed ticket: %s" %
            ticket_id,
            color=0x18e299)
        await ctx.respond(embed=embed, ephemeral=True)
        # Remove the ticket embed from staff tickets channel
        channel = discord.utils.get(
            guild.channels,
            name="tickets",
            category=discord.utils.get(
                ctx.guild.categories,
                name="Staff"))
        # Find message in channel with the ticket ID in the description
        async for message in channel.history(limit=1000):
            try:
                if ticket_id in message.embeds[0].description:
                    await message.delete()
                    break
            except IndexError:
                pass
            except discord.errors.NotFound:
                pass
            except discord.errors.Forbidden:
                pass
        # View ticket channel for the ticket claimer
        # Get channel where ticket is
        channel = discord.utils.get(guild.channels, name=ticket_id)
        await channel.set_permissions(ctx.author, read_messages=True, send_messages=True)
        # Get first embed sent by the bot in the ticket channel
        async for message in channel.history(limit=1000):
            if message.author == bot.user:
                # Get current time
                now = datetime.datetime.now()
                resolver = ctx.author
                original_embed = message.embeds[0]
                # Get opened date from database
                cursor.execute(
                    "SELECT opened_date FROM tickets WHERE id = %s", (ticket_id,))
                opened_date = cursor.fetchone()
                db_connection.commit()
                # Get time difference in HH:MM:SS
                response_time = now - opened_date[0]
                original_embed.set_footer(
                    text="Ticket claimed by: %s" %
                    ctx.author)
                await message.edit(embed=original_embed)
                await channel.send(f"Ticket claimed by: %s" % ctx.author.mention)
                # Show the channel to only the claimer, not other staff
                await channel.set_permissions(ctx.author, read_messages=True, send_messages=True)
                # Get the name of the top role of the resolver
                top_role = resolver.top_role.name
                # Update database
                cursor.execute(
                    "UPDATE tickets SET resolver = '%s', team = '%s', response_time = '%s' WHERE id = '%s'" %
                    (resolver, top_role, response_time, ticket_id))
                db_connection.commit()
                break
            else:
                pass
    else:
        embed = EmbedBuilder(
            "Error", "You do not have permission to use this command.").build()
        await ctx.respond(embed=embed, ephemeral=True)


@bot.slash_command(name="close_ticket", description="Close a ticket.")
async def closeticket(ctx, ticket_id: str) -> None:
    # Check if user has permission to use command
    if any(role.id in staff_roles for role in ctx.author.roles):
        # Check if ticket exists
        db_connection.ping()
        cursor.execute("SELECT * FROM tickets WHERE id = '%s'" % ticket_id)
        result = cursor.fetchone()
        db_connection.commit()
        if result is None:
            embed = EmbedBuilder(
                "Error", "This ticket does not exist.").build()
            await ctx.respond(embed=embed, ephemeral=True)
            return
        # Check if ticket has been claimed
        cursor.execute(
            "SELECT resolver FROM tickets WHERE id = '%s'" %
            ticket_id)
        resolver = cursor.fetchone()
        db_connection.commit()
        if resolver[0] is None:
            embed = EmbedBuilder(
                "Error", "This ticket has not been claimed.").build()
            await ctx.respond(embed=embed, ephemeral=True)
            return
        # Check database to see if ticket has already been closed
        cursor.execute("SELECT closed FROM tickets WHERE id = %s", ticket_id)
        closed = cursor.fetchone()
        db_connection.commit()
        # Check if closed is "N" or "Y"
        if closed[0] == "Y":
            embed = EmbedBuilder(
                "Error", "This ticket has already been closed.").build()
            await ctx.respond(embed=embed, ephemeral=True)
            return
        guild = ctx.guild
        # Get channel from the name of the channel
        channel = discord.utils.get(guild.channels, name=ticket_id)
        # Get transcript from the channel
        transcript = await channel.history(limit=None).flatten()
        # Delete channel
        await channel.delete()
        # Save transcript to file, starting with the first message
        transcript.reverse()
        transcript_file = open("../transcripts/%s.txt" % ticket_id, "w")
        for message in transcript:
            # Check if the message is an image or file
            if message.attachments:
                # Get the URL of the attachment
                attachment_url = message.attachments[0].url
                # Get the name of the attachment
                attachment_name = message.attachments[0].filename
                # Write the attachment URL to the transcript
                transcript_file.write(
                    f"{message.author}: {attachment_url} ({attachment_name})\n")
            # Check if the message is an embed
            elif message.embeds:
                # Save the message
                transcript_file.write(
                    "%s: %s" %
                    (message.author,
                     message.embeds[0].description.replace(
                         "\n",
                         "|")))
                transcript_file.write("\n")
                continue
            # Check if message is a system message
            elif message.type == discord.MessageType.default:
                transcript_file.write(
                    "%s: %s\n" %
                    (message.author, message.content))
            else:
                transcript_file.write(
                    "[Uncaught Message] %s: %s\n" %
                    (message.author, message.content))
        transcript_file.close()
        # DM the user who opened the ticket
        cursor.execute(
            "SELECT opened_by FROM tickets WHERE id = %s",
            ticket_id)
        opened_by = cursor.fetchone()
        db_connection.commit()
        user = await bot.fetch_user(opened_by[0])
        # Send user embed to alert them the ticket has been closed and who
        # closed it
        embed = discord.Embed(
            title="Ticket Closed",
            description="Your ticket has been closed.",
            color=0x18e299)
        embed.add_field(name="Ticket ID", value=ticket_id, inline=False)
        embed.add_field(name="Closed by", value=ctx.author, inline=False)
        await user.send(embed=embed)
        # Get time elapsed between response_time and closing the ticket
        cursor.execute(
            "SELECT opened_date FROM tickets WHERE id = %s",
            ticket_id)
        opened_date = cursor.fetchone()
        db_connection.commit()
        closed_date = datetime.datetime.now()
        time_elapsed = closed_date - opened_date[0]
        # Update database
        cursor.execute(
            "UPDATE tickets SET time_to_complete = '%s', transcript = '%s.txt', closed = 'Y' WHERE id = '%s'" %
            (time_elapsed, ticket_id, ticket_id))
        db_connection.commit()
        embed = discord.Embed(
            title="Ticket Closed",
            description=f"Closed ticket: %s" %
            ticket_id,
            color=0x18e299)
        await ctx.respond(embed=embed, ephemeral=True)
        # Send a notification into the management ticket channel
        # Get ticket from database with the ticket ID
        cursor.execute("SELECT * FROM tickets WHERE id = '%s'" % ticket_id)
        ticket = cursor.fetchone()
        db_connection.commit()
        embed = discord.Embed(
            title="A ticket has been closed!",
            description=f"Ticket closed: %s | Ticket Resolver: [%s] %s | Transcript: %s" %
            (ticket[0],
             ticket[7],
                ticket[6],
                ticket[8]),
            color=0x18e299)
        channel = discord.utils.get(
            ctx.guild.channels,
            name="tickets",
            category=discord.utils.get(
                guild.categories,
                name="Administrators"))
        # Send embed into channel
        await channel.send(embed=embed)
    else:
        embed = EmbedBuilder(
            "Error", "You do not have permission to use this command.").build()
        await ctx.respond(embed=embed, ephemeral=True)


@bot.slash_command(name="transfer_ticket",
                   description="Transfer a ticket to a higher level.")
async def transferticket(ctx, ticket_id: str, role: discord.Role) -> None:
    if any(role1.id in staff_roles for role1 in ctx.author.roles):
        # Check if ticket exists
        db_connection.ping()
        cursor.execute("SELECT * FROM tickets WHERE id = '%s'" % ticket_id)
        result = cursor.fetchone()
        db_connection.commit()
        if result is None:
            embed = EmbedBuilder(
                "Error", "This ticket does not exist.").build()
            await ctx.respond(embed=embed, ephemeral=True)
            return
        # Check database to see if ticket has already been closed
        cursor.execute("SELECT closed FROM tickets WHERE id = %s", ticket_id)
        closed = cursor.fetchone()
        db_connection.commit()
        # Check if closed is "N" or "Y"
        if closed[0] == "Y":
            embed = EmbedBuilder(
                "Error", "This ticket has already been closed.").build()
            await ctx.respond(embed=embed, ephemeral=True)
            return
        # Check if command issuer is the staff who claimed the ticket
        cursor.execute("SELECT resolver FROM tickets WHERE id = %s", ticket_id)
        resolver = cursor.fetchone()
        db_connection.commit()
        if resolver[0] is None:
            embed = EmbedBuilder(
                "Error", "This ticket has not been claimed.").build()
            await ctx.respond(embed=embed, ephemeral=True)
            return
        if resolver[0] != str(ctx.author):
            embed = EmbedBuilder(
                "Error", "You are not the staff member who claimed this ticket.").build()
            await ctx.respond(embed=embed, ephemeral=True)
            return
        # Check if role is a staff role
        if role.id not in staff_roles:
            embed = EmbedBuilder(
                "Error", "This role is not a staff role.").build()
            await ctx.respond(embed=embed, ephemeral=True)
            return
        # Check if there is a role higher than the issuer's top role
        if role.position <= ctx.author.top_role.position:
            embed = EmbedBuilder(
                "Error",
                "You cannot transfer a ticket to a role that is equal to or lower than your top role.")
            embed.build()
            await ctx.respond(embed=embed, ephemeral=True)
            return
        # Check if the ticket is already claimed by the role
        cursor.execute("SELECT team FROM tickets WHERE id = %s", ticket_id)
        team = cursor.fetchone()
        db_connection.commit()
        if team[0] == role.name:
            embed = EmbedBuilder(
                "Error", "This ticket is already claimed by this team.").build()
            await ctx.respond(embed=embed, ephemeral=True)
            return
        # Get channel from the name of the channel
        channel = discord.utils.get(ctx.guild.channels, name=ticket_id)
        # Get the role to transfer to
        role = discord.utils.get(ctx.guild.roles, name=role.name)
        try:
            # Hide the channel from the claimer
            await channel.set_permissions(ctx.author, read_messages=False)
            # Add the staff to this ticket
            await channel.set_permissions(role, read_messages=True, send_messages=True)
        except discord.errors.Forbidden:
            pass
        except discord.errors.HTTPException:
            pass
        # Update database
        cursor.execute(
            "UPDATE tickets SET resolver = NULL, team = '%s' WHERE id = '%s'" %
            (role.name, ticket_id))
        db_connection.commit()
        embed = discord.Embed(
            title="Ticket Transferred",
            description=f"Transferred ticket: %s" %
            ticket_id,
            color=0x18e299)
        await ctx.respond(embed=embed, ephemeral=True)
        # Send new embed
        embed = discord.Embed(
            title="Ticket Transferred",
            description=f"Ticket transferred to: {role.mention}",
            color=0x18e299)
        await channel.send(embed=embed)
        if str(role.id) == str(administrator_role):
            # Get tickets channel under the administrators category
            tickets_channel = discord.utils.get(
                ctx.guild.channels, name="tickets", category=discord.utils.get(
                    ctx.guild.categories, name="Administrators"))
            # Send an embed in the channel
            embed = discord.Embed(
                title="Ticket Transferred",
                description=f"Ticket {ticket_id} transferred to: {role.mention}",
                color=0x18e299)
            await tickets_channel.send(embed=embed)
            # Send a ping
            await tickets_channel.send(role.mention)
    else:
        embed = EmbedBuilder(
            "Error", "You do not have permission to use this command.").build()
        await ctx.respond(embed=embed, ephemeral=True)


@bot.slash_command(name="update-bot", description="Update the bot.")
async def update(ctx) -> None:
    # Check if the author has a role in staff_roles
    if not any(role.id in staff_roles for role in ctx.author.roles):
        embed = EmbedBuilder(
            "Error", "You do not have permission to use this command.").build()
        await ctx.respond(embed=embed, ephemeral=True)
        return
    # Check if the bot is up to date
    output: str = os.popen("sh ../scripts/autoupdate.sh").read()
    # Get last line from this output
    last_line: str = output.splitlines()[-1]
    # If the output is "Already up to date.", the bot is up to date
    if last_line == "Already up-to-date":
        embed = EmbedBuilder("Error", "The bot is already up to date.").build()
        await ctx.respond(embed=embed, ephemeral=True)
        return
    else:
        embed = EmbedBuilder(
            "Success",
            "The bot has been updated: %s" %
            last_line).build()
        await ctx.respond(embed=embed, ephemeral=True)
        return


# ----------------------------------------------------------------
# / Normal Commands

@bot.slash_command(name="ping", description="Check bot latency.")
async def ping(ctx) -> None:
    start: float = time.perf_counter()
    db_connection.ping()
    cursor.execute("SELECT * FROM ping")
    cursor.fetchall()
    db_connection.commit()
    end: float = time.perf_counter()
    # Calculate database latency
    latency: int = round((end - start) * 1000)
    network_latency = round(measure_latency(host='google.com')[0], 2)
    embed = EmbedBuilder(
        "Ping",
        f"**Database Latency:** {latency}ms\n**Network Latency:** {network_latency}ms").build()
    await ctx.respond(embed=embed, ephemeral=True)


# Meet the staff!
@bot.slash_command(name="staff", description="Meet the Community Staff!")
async def staff(ctx) -> None:
    embed = EmbedBuilder("Meet the Community Staff!", staff_message).build()
    await ctx.respond(embed=embed, ephemeral=True)


@bot.slash_command(name="help", description="Display help message.")
async def helpme(ctx) -> None:
    embed = EmbedBuilder("Help", help_message).build()
    await ctx.respond(embed=embed, ephemeral=True)


@bot.slash_command(name="support", description="Create a ticket.")
async def support(ctx) -> None:
    # Embed to confirm if they want the bot to DM them
    embed = EmbedBuilder("Support", support_message).build()
    await ctx.respond(embed=embed, ephemeral=True)
    # DM command issuer
    dm_embed = discord.Embed(
        title="Create Ticket",
        description=DM_support_message_stage1,
        color=0x18e299)
    message = await ctx.author.send(embed=dm_embed)
    # Add reactions
    await message.add_reaction("1️⃣")
    await message.add_reaction("2️⃣")
    await message.add_reaction("3️⃣")
    await message.add_reaction("4️⃣")
    # Cancel ticket creation
    await message.add_reaction("❌")

    # Wait for reaction on the DM
    def check(user_reaction, user_object) -> bool:
        return user_object == ctx.author and str(user_reaction.emoji) in [
            "1️⃣", "2️⃣", "3️⃣", "4️⃣", "❌"]

    try:
        reaction, user = await bot.wait_for("reaction_add", timeout=60.0, check=check)
        # Delete the message
        await message.delete()
        db_connection.ping()
        if reaction.emoji == "1️⃣":
            message = None
            # Update embed
            dm_embed = discord.Embed(
                title="Bug Report",
                description="Please describe the bug you have found. Include any screenshots by "
                "adding Imgur links.",
                color=0x18e299)
            stage2message = await ctx.author.send(embed=dm_embed)

            # Wait for message
            def check2(user_message) -> bool:
                return user_message.author == ctx.author and user_message.channel == ctx.author.dm_channel

            try:
                message = await bot.wait_for("message", timeout=300.0, check=check2)
                # Create ticket
                ticket_id = ""
                for i in range(1, 9):
                    ticket_id += random.choice(lst)
                cursor.execute(
                    "SELECT * FROM tickets WHERE id = '%s'" %
                    ticket_id)
                while cursor.rowcount != 0:
                    ticket_id = ""
                    for i in range(1, 9):
                        ticket_id += random.choice(lst)
                    cursor.execute(
                        "SELECT * FROM tickets WHERE id = '%s'" %
                        ticket_id)
                ticket_category = "Bug Report"
                ticket_opened_datetime = datetime.datetime.now()
                ticket_opened_by = ctx.author.id
                # Insert ticket to database
                cursor.execute(
                    "INSERT INTO tickets (id, category, opened_date, opened_by, response_time, time_to_complete, "
                    "resolver, team, transcript, closed) VALUES ('%s', '%s', '%s', '%s', NULL, NULL, NULL, NULL, "
                    "NULL, 'N')" %
                    (ticket_id, ticket_category, ticket_opened_datetime, ticket_opened_by))
                db_connection.commit()
                await stage2message.delete()
                # Create ticket channel
                guild = ctx.guild
                category = discord.utils.get(
                    guild.categories, name="Bug Reports")
                channel = await guild.create_text_channel(name=ticket_id, category=category)
                # Hide the channel from everyone but the issuer
                await channel.set_permissions(guild.default_role, view_channel=False)
                await channel.set_permissions(ctx.author, view_channel=True, send_messages=True)
                # Hide channel from Staff role
                staff_role = discord.utils.get(guild.roles, name="Moderators")
                await channel.set_permissions(staff_role, view_channel=False)
                # Send message to channel
                embed = discord.Embed(
                    title="Bug Report",
                    description=f"Ticket ID: {ticket_id} \n Description: {message.content}",
                    color=0x18e299)
                await channel.send(embed=embed)
                # Send message to user
                embed = discord.Embed(
                    title="Bug Report",
                    description=f"Ticket ID: {ticket_id} \n Description: {message.content} \n\n "
                    f"Ticket created. A member of staff will be with you shortly.",
                    color=0x18e299)
                await ctx.author.send(embed=embed)
                # Send message in the staff tickets channel
                embed = discord.Embed(
                    title="Bug Report",
                    description=f"Ticket ID: {ticket_id} \n Description: {message.content} \n\n "
                    f"Ticket created by {ctx.author.mention}.",
                    color=0x18e299)
                staff_channel = discord.utils.get(
                    guild.channels, name="tickets", category=discord.utils.get(
                        ctx.guild.categories, name="Staff"))
                await staff_channel.send(embed=embed)
            except asyncio.TimeoutError:
                # Edit embed
                dm_embed = discord.Embed(
                    title="Bug Report",
                    description="You took too long to respond. Please try again.",
                    color=0x18e299)
                await message.edit(embed=dm_embed)
        elif reaction.emoji == "2️⃣":
            message = None
            # Update embed
            dm_embed = discord.Embed(
                title="Suggestion",
                description="Please describe the suggestion. Include any screenshots by adding "
                "Imgur links.")
            stage2message = await ctx.author.send(embed=dm_embed)

            # Wait for message
            def check2(user_message) -> bool:
                return user_message.author == ctx.author and user_message.channel == ctx.author.dm_channel

            try:
                message = await bot.wait_for("message", timeout=300.0, check=check2)
                # Create ticket
                ticket_id = ""
                for i in range(1, 9):
                    ticket_id += random.choice(lst)
                cursor.execute(
                    "SELECT * FROM tickets WHERE id = '%s'" %
                    ticket_id)
                while cursor.rowcount != 0:
                    ticket_id = ""
                    for i in range(1, 9):
                        ticket_id += random.choice(lst)
                    cursor.execute(
                        "SELECT * FROM tickets WHERE id = '%s'" %
                        ticket_id)
                ticket_category = "Suggestion"
                ticket_opened_datetime = datetime.datetime.now()
                ticket_opened_by = ctx.author.id
                # Insert ticket to database
                cursor.execute(
                    "INSERT INTO tickets (id, category, opened_date, opened_by, response_time, time_to_complete, "
                    "resolver, team, transcript, closed) VALUES ('%s', '%s', '%s', '%s', NULL, NULL, NULL, NULL, "
                    "NULL, 'N')" %
                    (ticket_id, ticket_category, ticket_opened_datetime, ticket_opened_by))
                db_connection.commit()
                await stage2message.delete()
                # Create ticket channel
                guild = ctx.guild
                category = discord.utils.get(
                    guild.categories, name="Suggestions")
                channel = await guild.create_text_channel(name=ticket_id, category=category)
                # Hide the channel from everyone but the issuer
                await channel.set_permissions(guild.default_role, view_channel=False)
                await channel.set_permissions(ctx.author, view_channel=True, send_messages=True)
                # Hide channel from Staff role
                staff_role = discord.utils.get(guild.roles, name="Moderators")
                await channel.set_permissions(staff_role, view_channel=False)
                # Send message to channel
                embed = discord.Embed(
                    title="Suggestion",
                    description=f"Ticket ID: {ticket_id} \n Description: {message.content}",
                    color=0x18e299)
                await channel.send(embed=embed)
                # Send message to user
                embed = discord.Embed(
                    title="Suggestion",
                    description=f"Ticket ID: {ticket_id} \n Description: {message.content} \n\n "
                    f"Ticket created. A member of staff will be with you shortly.",
                    color=0x18e299)
                await ctx.author.send(embed=embed)
                # Send message in the staff tickets channel
                embed = discord.Embed(
                    title="Suggestion",
                    description=f"Ticket ID: {ticket_id} \n Description: {message.content} \n\n "
                    f"Ticket created by {ctx.author.mention}.",
                    color=0x18e299)
                staff_channel = discord.utils.get(
                    guild.channels, name="tickets", category=discord.utils.get(
                        ctx.guild.categories, name="Staff"))
                await staff_channel.send(embed=embed)
            except asyncio.TimeoutError:
                # Edit embed
                dm_embed = discord.Embed(
                    title="Suggestion",
                    description="You took too long to respond. Please try again.",
                    color=0x18e299)
                await message.edit(embed=dm_embed)
        elif reaction.emoji == "3️⃣":
            message = None
            # Update embed
            dm_embed = discord.Embed(
                title="Report User",
                description="Please detail the report. Include any screenshots by adding Imgur "
                "links.")
            stage2message = await ctx.author.send(embed=dm_embed)

            # Wait for message
            def check2(user_message) -> bool:
                return user_message.author == ctx.author and user_message.channel == ctx.author.dm_channel

            try:
                message = await bot.wait_for("message", timeout=300.0, check=check2)
                # Create ticket
                ticket_id = ""
                for i in range(1, 9):
                    ticket_id += random.choice(lst)
                cursor.execute(
                    "SELECT * FROM tickets WHERE id = '%s'" %
                    ticket_id)
                while cursor.rowcount != 0:
                    ticket_id = ""
                    for i in range(1, 9):
                        ticket_id += random.choice(lst)
                    cursor.execute(
                        "SELECT * FROM tickets WHERE id = '%s'" %
                        ticket_id)
                ticket_category = "User Report"
                ticket_opened_datetime = datetime.datetime.now()
                ticket_opened_by = ctx.author.id
                # Insert ticket to database
                cursor.execute(
                    "INSERT INTO tickets (id, category, opened_date, opened_by, response_time, time_to_complete, "
                    "resolver, team, transcript, closed) VALUES ('%s', '%s', '%s', '%s', NULL, NULL, NULL, NULL, "
                    "NULL, 'N')" %
                    (ticket_id, ticket_category, ticket_opened_datetime, ticket_opened_by))
                db_connection.commit()
                await stage2message.delete()
                # Create ticket channel
                guild = ctx.guild
                category = discord.utils.get(
                    guild.categories, name="User Reports")
                channel = await guild.create_text_channel(name=ticket_id, category=category)
                # Hide the channel from everyone but the issuer
                await channel.set_permissions(guild.default_role, view_channel=False)
                # Add the user who created the ticket to the channel
                # permissions
                await channel.set_permissions(ctx.author, view_channel=True, send_messages=True)
                # Hide channel from Staff role
                staff_role = discord.utils.get(guild.roles, name="Moderators")
                await channel.set_permissions(staff_role, view_channel=False)
                # Send message to channel
                embed = discord.Embed(
                    title="Report User",
                    description=f"Ticket ID: {ticket_id} \n Description: {message.content}",
                    color=0x18e299)
                await channel.send(embed=embed)
                # Send message to user
                embed = discord.Embed(
                    title="Report User",
                    description=f"Ticket ID: {ticket_id} \n Description: {message.content} \n\n "
                    f"Ticket created. A member of staff will be with you shortly.",
                    color=0x18e299)
                await ctx.author.send(embed=embed)
                # Send message in the staff tickets channel
                embed = discord.Embed(
                    title="Report User",
                    description=f"Ticket ID: {ticket_id} \n Description: {message.content} \n\n "
                    f"Ticket created by {ctx.author.mention}.",
                    color=0x18e299)
                staff_channel = discord.utils.get(
                    guild.channels, name="tickets", category=discord.utils.get(
                        ctx.guild.categories, name="Staff"))
                await staff_channel.send(embed=embed)
            except asyncio.TimeoutError:
                # Edit embed
                dm_embed = discord.Embed(
                    title="Report User",
                    description="You took too long to respond. Please try again.",
                    color=0x18e299)
                await message.edit(embed=dm_embed)
        elif reaction.emoji == "4️⃣":
            message = None
            # Update embed
            dm_embed = discord.Embed(
                title="Other",
                description="Please detail the issue you are having. Include any screenshots by "
                "adding Imgur links.",
                color=0x18e299)
            stage2message = await ctx.author.send(embed=dm_embed)

            # Wait for message
            def check2(user_message) -> bool:
                return user_message.author == ctx.author and user_message.channel == ctx.author.dm_channel

            try:
                message = await bot.wait_for("message", timeout=300.0, check=check2)
                # Create ticket
                ticket_id = ""
                for i in range(1, 9):
                    ticket_id += random.choice(lst)
                cursor.execute(
                    f"SELECT * FROM tickets WHERE id = '{ticket_id}'")
                while cursor.rowcount != 0:
                    ticket_id = ""
                    for i in range(1, 9):
                        ticket_id += random.choice(lst)
                    cursor.execute(
                        f"SELECT * FROM tickets WHERE id = '{ticket_id}'")
                ticket_category = "Other"
                ticket_opened_datetime = datetime.datetime.now()
                ticket_opened_by = ctx.author.id
                # Insert ticket to database
                cursor.execute(
                    "INSERT INTO tickets (id, category, opened_date, opened_by, response_time, time_to_complete, "
                    "resolver, team, transcript, closed) VALUES ('%s', '%s', '%s', '%s', NULL, NULL, NULL, NULL, "
                    "NULL, 'N')" %
                    (ticket_id, ticket_category, ticket_opened_datetime, ticket_opened_by))
                db_connection.commit()
                await stage2message.delete()
                # Create ticket channel
                guild = ctx.guild
                category = discord.utils.get(guild.categories, name="Other")
                channel = await guild.create_text_channel(name=ticket_id, category=category)
                # Hide the channel from everyone but the issuer
                await channel.set_permissions(guild.default_role, view_channel=False)
                # Hide channel from Staff role
                staff_role = discord.utils.get(guild.roles, name="Moderators")
                await channel.set_permissions(staff_role, view_channel=False)
                await channel.set_permissions(ctx.author, view_channel=True, send_messages=True)
                # Send message to channel
                embed = discord.Embed(
                    title="Other",
                    description=f"Ticket ID: {ticket_id} \n Description: {message.content}",
                    color=0x18e299)
                await channel.send(embed=embed)
                # Send message to user
                embed = discord.Embed(
                    title="Other",
                    description=f"Ticket ID: {ticket_id} \n Description: {message.content} \n\n "
                    f"Ticket created. A member of staff will be with you shortly.",
                    color=0x18e299)
                await ctx.author.send(embed=embed)
                # Send message in the staff tickets channel
                embed = discord.Embed(
                    title="Other",
                    description=f"Ticket ID: {ticket_id} \n Description: {message.content} \n\n "
                    f"Ticket created by {ctx.author.mention}.",
                    color=0x18e299)
                staff_channel = discord.utils.get(
                    guild.channels, name="tickets", category=discord.utils.get(
                        ctx.guild.categories, name="Staff"))
                await staff_channel.send(embed=embed)
            except asyncio.TimeoutError:
                # Edit embed
                dm_embed = discord.Embed(
                    title="Other",
                    description="You took too long to respond. Please try again.",
                    color=0x18e299)
                await message.edit(embed=dm_embed)
        elif reaction.emoji == "❌":
            # Update embed
            dm_embed = discord.Embed(
                title="Ticket Creation",
                description="Ticket creation cancelled.",
                color=0x18e299)
            # Send message, not edit
            await ctx.author.send(embed=dm_embed)
    except asyncio.TimeoutError:
        # Delete the embed
        await message.delete()
        await ctx.author.send("You took too long to respond.")


# On Bot Load
@bot.event
async def on_ready() -> None:
    await bot.change_presence(activity=discord.Game('/support'))


# Catch any exceptions
@bot.event
async def on_command_error(ctx, error) -> None:
    if isinstance(error, discord.DiscordException):
        error_message = EmbedBuilder("Exception", error)
        error_message.build()
        await ctx.respond(embed=error_message, ephemeral=True)
    elif isinstance(error, discord.ext.commands.errors.CommandNotFound):
        error_message = EmbedBuilder(
            "Command Not Found",
            "The command you entered was not found. Please try again.")
        error_message.build()
        await ctx.respond(embed=error_message, ephemeral=True)
    else:
        # Log error with the timestamp in logs folder
        with open("../logs/error.log", "a") as error_log:
            error_log.write(f"[{datetime.datetime.now()}] | {error}\n")
            error_log.close()
        error_message = EmbedBuilder(
            "Unknown Error",
            "An unknown error has occurred, this has been logged. \nQuote timestamp: %s " %
            datetime.datetime.now())
        error_message.build()
        await ctx.respond(embed=error_message, ephemeral=True)


if __name__ == '__main__':
    try:
        db_connection = pymysql.connect(
            host='127.0.0.1',
            user=username,
            password=password,
            database=database,
            port=3306)
        print(
            "\u001b[32mSuccessfully connected to: %s \u001b[0m" %
            (db_connection.get_server_info()))
        cursor = db_connection.cursor()
        bot.run(token)
    except Exception as e:
        print(
            "\u001b[31mFailed to connect to server/database.\n\u001b[35mError description: %s \u001b[0m" %
            (repr(e)))
        sys.exit(-1)
