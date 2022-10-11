import asyncio
import datetime
import discord
import discord.ext
import json
import random
import string

from discord.ext import commands

from messages import *
from EmbedBuilder import EmbedBuilder


class TicketCommands(commands.Cog):

    def __init__(self, bot, db_connection):
        self.bot = bot
        self.db_connection = db_connection
        self.lst: list[str] = list(string.ascii_letters + string.digits)
        self.cursor = self.db_connection.cursor()
        self.config_file = None
        with open("../config/config.json") as self.config_file:
            self.config = json.load(self.config_file)
            self.staff_roles = self.config["staff_roles"]
            self.administrator_role = self.config["administrator_role"]
            self.config_file.close()

    # / Staff Commands

    @commands.slash_command(name="open_tickets",
                            description="Get a list of currently open tickets.")
    async def opentickets(self, ctx) -> None:
        if not any(role.id in self.staff_roles for role in ctx.author.roles):
            embed = EmbedBuilder(
                "Error", "You do not have permission to use this command.").build()
            await ctx.respond(embed=embed, ephemeral=True)
            return
        else:
            # Make request to database and return all tickets that are
            # currently open
            self.cursor.execute("SELECT * FROM tickets WHERE closed = 'N'")
            tickets = self.cursor.fetchall()
            self.db_connection.commit()
            if len(tickets) == 0:
                embed = EmbedBuilder(
                    "No Open Tickets",
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

    @commands.slash_command(name="get_transcript",
                            description="Get a transcript of a ticket.")
    async def gettranscript(self, ctx, ticket_id: str) -> None:
        if any(role.id in self.staff_roles for role in ctx.author.roles):
            # Check if ticket exists
            self.db_connection.ping()
            self.cursor.execute(
                "SELECT transcript FROM tickets WHERE id = '%s'" %
                ticket_id)
            result = self.cursor.fetchone()
            self.db_connection.commit()
            if result is None:
                embed = EmbedBuilder(
                    "Error", "This ticket does not exist.").build()
                await ctx.respond(embed=embed, ephemeral=True)
                return
            # Get file from transcript name in database
            self.cursor.execute(
                "SELECT transcript FROM tickets WHERE id = '%s'" %
                ticket_id)
            transcript = self.cursor.fetchone()
            self.db_connection.commit()
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

    @commands.slash_command(name="claim_ticket", description="Claim a ticket.")
    async def claimticket(self, ctx, ticket_id: str) -> None:
        if any(role.id in self.staff_roles for role in ctx.author.roles):
            # Check if ticket exists
            self.db_connection.ping()
            self.cursor.execute(
                "SELECT category FROM tickets WHERE id = '%s'" %
                ticket_id)
            result = self.cursor.fetchone()
            if not result:
                embed = EmbedBuilder(
                    "Error", "This ticket does not exist.").build()
                await ctx.respond(embed=embed, ephemeral=True)
                return
            self.db_connection.commit()
            # Check database to see if ticket has already been claimed
            self.cursor.execute(
                "SELECT resolver FROM tickets WHERE id = %s", ticket_id)
            resolver = self.cursor.fetchone()
            self.db_connection.commit()
            if resolver[0] is not None:
                embed = EmbedBuilder(
                    "Error", "This ticket has already been claimed.").build()
                await ctx.respond(embed=embed, ephemeral=True)
                return
            guild = ctx.guild
            # Get channel ID from the name of the channel
            channel = discord.utils.get(guild.channels, name=ticket_id.lower())
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
            channel = discord.utils.get(guild.channels, name=ticket_id.lower())
            await channel.set_permissions(ctx.author, read_messages=True, send_messages=True)
            # Get first embed sent by the bot in the ticket channel
            async for message in channel.history(limit=1000):
                if message.author == self.bot.user:
                    # Get current time
                    now = datetime.datetime.now()
                    resolver = ctx.author
                    original_embed = message.embeds[0]
                    # Get opened date from database
                    self.cursor.execute(
                        "SELECT opened_date FROM tickets WHERE id = %s", (ticket_id,))
                    opened_date = self.cursor.fetchone()
                    self.db_connection.commit()
                    # Get time difference in HH:MM:SS
                    response_time = now - opened_date[0]
                    original_embed.set_footer(
                        text="Ticket claimed by: %s" % ctx.author)
                    await message.edit(embed=original_embed)
                    await channel.send(f"Ticket claimed by: %s" % ctx.author.mention)
                    # Show the channel to only the claimer, not other staff
                    await channel.set_permissions(ctx.author, read_messages=True, send_messages=True)
                    # Get the name of the top role of the resolver
                    top_role = resolver.top_role.name
                    # Update database
                    self.cursor.execute(
                        "UPDATE tickets SET resolver = '%s', team = '%s', response_time = '%s' WHERE id = '%s'" %
                        (resolver, top_role, response_time, ticket_id))
                    self.db_connection.commit()
                    break
                else:
                    pass
        else:
            embed = EmbedBuilder(
                "Error", "You do not have permission to use this command.").build()
            await ctx.respond(embed=embed, ephemeral=True)

    @commands.slash_command(name="close_ticket", description="Close a ticket.")
    async def closeticket(self, ctx, ticket_id: str) -> None:
        # Check if user has permission to use command
        if any(role.id in self.staff_roles for role in ctx.author.roles):
            # Check if ticket exists
            self.db_connection.ping()
            self.cursor.execute(
                "SELECT * FROM tickets WHERE id = '%s'" %
                ticket_id)
            result = self.cursor.fetchone()
            self.db_connection.commit()
            if result is None:
                embed = EmbedBuilder(
                    "Error", "This ticket does not exist.").build()
                await ctx.respond(embed=embed, ephemeral=True)
                return
            # Check if ticket has been claimed
            self.cursor.execute(
                "SELECT resolver FROM tickets WHERE id = '%s'" %
                ticket_id)
            resolver = self.cursor.fetchone()
            self.db_connection.commit()
            if resolver[0] is None:
                embed = EmbedBuilder(
                    "Error", "This ticket has not been claimed.").build()
                await ctx.respond(embed=embed, ephemeral=True)
                return
            # Check database to see if ticket has already been closed
            self.cursor.execute(
                "SELECT closed FROM tickets WHERE id = %s", ticket_id)
            closed = self.cursor.fetchone()
            self.db_connection.commit()
            # Check if closed is "N" or "Y"
            if closed[0] == "Y":
                embed = EmbedBuilder(
                    "Error", "This ticket has already been closed.").build()
                await ctx.respond(embed=embed, ephemeral=True)
                return
            guild = ctx.guild
            # Get channel from the name of the channel
            channel = discord.utils.get(guild.channels, name=ticket_id.lower())
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
            self.cursor.execute(
                "SELECT opened_by FROM tickets WHERE id = %s", ticket_id)
            opened_by = self.cursor.fetchone()
            self.db_connection.commit()
            user = await self.bot.fetch_user(opened_by[0])
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
            self.cursor.execute(
                "SELECT opened_date FROM tickets WHERE id = %s", ticket_id)
            opened_date = self.cursor.fetchone()
            self.db_connection.commit()
            closed_date = datetime.datetime.now()
            time_elapsed = closed_date - opened_date[0]
            # Update database
            self.cursor.execute(
                "UPDATE tickets SET time_to_complete = '%s', transcript = '%s.txt', closed = 'Y' WHERE id = '%s'" %
                (time_elapsed, ticket_id, ticket_id))
            self.db_connection.commit()
            embed = discord.Embed(
                title="Ticket Closed",
                description=f"Closed ticket: %s" %
                ticket_id,
                color=0x18e299)
            await ctx.respond(embed=embed, ephemeral=True)
            # Send a notification into the management ticket channel
            # Get ticket from database with the ticket ID
            self.cursor.execute(
                "SELECT * FROM tickets WHERE id = '%s'" %
                ticket_id)
            ticket = self.cursor.fetchone()
            self.db_connection.commit()
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

    @commands.slash_command(name="transfer_ticket",
                            description="Transfer a ticket to a higher level.")
    async def transferticket(self, ctx, ticket_id: str, role: discord.Role) -> None:
        if any(role1.id in self.staff_roles for role1 in ctx.author.roles):
            # Check if ticket exists
            self.db_connection.ping()
            self.cursor.execute(
                "SELECT * FROM tickets WHERE id = '%s'" %
                ticket_id)
            result = self.cursor.fetchone()
            self.db_connection.commit()
            if result is None:
                embed = EmbedBuilder(
                    "Error", "This ticket does not exist.").build()
                await ctx.respond(embed=embed, ephemeral=True)
                return
            # Check database to see if ticket has already been closed
            self.cursor.execute(
                "SELECT closed FROM tickets WHERE id = %s", ticket_id)
            closed = self.cursor.fetchone()
            self.db_connection.commit()
            # Check if closed is "N" or "Y"
            if closed[0] == "Y":
                embed = EmbedBuilder(
                    "Error", "This ticket has already been closed.").build()
                await ctx.respond(embed=embed, ephemeral=True)
                return
            # Check if command issuer is the staff who claimed the ticket
            self.cursor.execute(
                "SELECT resolver FROM tickets WHERE id = %s", ticket_id)
            resolver = self.cursor.fetchone()
            self.db_connection.commit()
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
            if role.id not in self.staff_roles:
                embed = EmbedBuilder(
                    "Error", "This role is not a staff role.").build()
                await ctx.respond(embed=embed, ephemeral=True)
                return
            # Check if there is a role higher than the issuer's top role
            if role.position <= ctx.author.top_role.position:
                embed = EmbedBuilder(
                    "Error",
                    "You cannot transfer a ticket to a role that is equal to or lower than your top "
                    "role.")
                embed.build()
                await ctx.respond(embed=embed, ephemeral=True)
                return
            # Check if the ticket is already claimed by the role
            self.cursor.execute(
                "SELECT team FROM tickets WHERE id = %s", ticket_id)
            team = self.cursor.fetchone()
            self.db_connection.commit()
            if team[0] == role.name:
                embed = EmbedBuilder(
                    "Error", "This ticket is already claimed by this team.").build()
                await ctx.respond(embed=embed, ephemeral=True)
                return
            # Get channel from the name of the channel
            channel = discord.utils.get(
                ctx.guild.channels, name=ticket_id.lower())
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
            self.cursor.execute(
                "UPDATE tickets SET resolver = NULL, team = '%s' WHERE id = '%s'" %
                (role.name, ticket_id))
            self.db_connection.commit()
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
            if str(role.id) == str(self.administrator_role):
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

    # / Normal Commands

    @commands.slash_command(name="support", description="Create a ticket.")
    async def support(self, ctx) -> None:
        # Embed to confirm if they want the bot to DM them
        embed = EmbedBuilder("Support", support_message).build()
        await ctx.respond(embed=embed, ephemeral=True)
        # DM command issuer
        dm_embed = discord.Embed(
            title="Create Ticket",
            description=DM_support_message_stage1,
            color=0x18e299)
        message = await ctx.author.send(embed=dm_embed)
        guild = ctx.guild
        staff_role = discord.utils.get(guild.roles, name="Moderators")
        ticket_opened_datetime = datetime.datetime.now()
        ticket_opened_by = ctx.author.id
        ticket_id = ""
        category = None
        ticket_category = None
        stage2message = None
        staff_channel = discord.utils.get(
            guild.channels, name="tickets", category=discord.utils.get(
                ctx.guild.categories, name="Staff"))
        for i in range(1, 9):
            ticket_id += random.choice(self.lst)
        self.cursor.execute(
            "SELECT * FROM tickets WHERE id = '%s'" %
            ticket_id)
        while self.cursor.rowcount != 0:
            ticket_id = ""
            for i in range(1, 9):
                ticket_id += random.choice(self.lst)
            self.cursor.execute(
                "SELECT * FROM tickets WHERE id = '%s'" %
                ticket_id)
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
            reaction, user = await self.bot.wait_for("reaction_add", timeout=60.0, check=check)
            # Delete the message
            await message.delete()
            self.db_connection.ping()
            if reaction.emoji == "1️⃣":
                message = None
                category = discord.utils.get(
                    guild.categories, name="Bug Reports")
                ticket_category = "Bug Report"
                # Update embed
                dm_embed = EmbedBuilder(
                    title="Bug Report",
                    description="Please describe the bug you have found. Include " +
                    "any screenshots by adding Imgur links.").build()
                stage2message = await ctx.author.send(embed=dm_embed)

            elif reaction.emoji == "2️⃣":
                message = None
                category = discord.utils.get(
                    guild.categories, name="Suggestions")
                ticket_category = "Suggestion"
                # Update embed
                dm_embed = EmbedBuilder(
                    title=category,
                    description="Please describe the suggestion. Include any screenshots by "
                    "adding "
                    "Imgur links.") .build()
                stage2message = await ctx.author.send(embed=dm_embed)

            elif reaction.emoji == "3️⃣":
                message = None
                category = discord.utils.get(
                    guild.categories, name="User Reports")
                ticket_category = "User Report"
                # Update embed
                dm_embed = EmbedBuilder(
                    title=category,
                    description="Please detail the report. Include any screenshots by adding "
                    "Imgur "
                    "links.") .build()
                stage2message = await ctx.author.send(embed=dm_embed)

            elif reaction.emoji == "4️⃣":
                message = None
                category = discord.utils.get(guild.categories, name="Other")
                ticket_category = "Other"
                # Update embed
                dm_embed = EmbedBuilder(
                    title="Other",
                    description="Please detail the issue you are having. Include any screenshots "
                    "by "
                    "adding Imgur links.") .build()
                stage2message = await ctx.author.send(embed=dm_embed)

            elif reaction.emoji == "❌":
                # Update embed
                dm_embed = EmbedBuilder(
                    title="Ticket Creation",
                    description="Ticket creation cancelled.") .build()
                # Send message, not edit
                await ctx.author.send(embed=dm_embed)
                return

            def check2(user_message) -> bool:
                return user_message.author == ctx.author and user_message.channel == ctx.author.dm_channel

            message = await self.bot.wait_for("message", timeout=300.0, check=check2)
            channel = await guild.create_text_channel(name=ticket_id, category=category)

            # Insert ticket to database
            self.cursor.execute(
                "INSERT INTO tickets (id, category, opened_date, opened_by, response_time, time_to_complete, "
                "resolver, team, transcript, closed) VALUES ('%s', '%s', '%s', '%s', NULL, NULL, NULL, NULL, "
                "NULL, 'N')" %
                (ticket_id, ticket_category, ticket_opened_datetime, ticket_opened_by))
            self.db_connection.commit()
            await stage2message.delete()
            # Create ticket channel
            first_embed = EmbedBuilder(
                title=category,
                description=f"Ticket ID: {ticket_id} \n Description: {message.content}") .build()
            second_embed = EmbedBuilder(
                title=category,
                description=f"Ticket ID: {ticket_id} \n Description: {message.content} \n\n "
                f"Ticket created. A member of staff will be with you shortly.") .build()
            third_embed = EmbedBuilder(
                title=category,
                description=f"Ticket ID: {ticket_id} \n Description: {message.content} \n\n "
                f"Ticket created by {ctx.author.mention}.") .build()
            # Hide the channel from everyone but the issuer
            await channel.set_permissions(guild.default_role, view_channel=False)
            await channel.set_permissions(ctx.author, view_channel=True, send_messages=True)
            # Hide channel from Staff role
            await channel.set_permissions(staff_role, view_channel=False)
            # Send message to channel
            await channel.send(embed=first_embed)
            # Send message to user
            await ctx.author.send(embed=second_embed)
            # Send message in the staff tickets channel
            await staff_channel.send(embed=third_embed)
        except asyncio.TimeoutError:
            # Delete the embed
            await message.delete()
            await ctx.author.send("You took too long to respond.")
            return
