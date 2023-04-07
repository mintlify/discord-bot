import datetime
import json
import os

import discord
import discord.ext
from discord.ext import commands
from EmbedBuilder import EmbedBuilder
from messages import *


class MaintenanceEngine(commands.Cog):
    def __init__(self, bot, db_connection) -> None:
        self.bot = bot
        self.db_connection = db_connection
        self.cursor = self.db_connection.cursor()
        self.config_file = None
        self.scan_results = {}
        with open("../config/config.json", encoding="utf=8") as self.config_file:
            self.config = json.load(self.config_file)
            self.staff_roles = self.config["staff_roles"]
            self.administrator_role = self.config["administrator_role"]
            self.config_file.close()

    @commands.slash_command(
        name="me_scan",
        description="Scan through the entire bot's network for any issues.",
    )
    async def me_scan(self, ctx):
        try:
            ctx.guild.channels
        except AttributeError:
            await ctx.respond(
                "Sending commands in DM is unsupported. Please run this"
                "in the server.",
                ephemeral=True,
            )
        if any(role.id in self.staff_roles for role in ctx.author.roles):
            """
            Database data validity check
            """

            # First scan, check for invalid database values
            self.cursor.execute("SELECT id FROM tickets")
            tickets = self.cursor.fetchall()
            # All ticket IDs must be 8 characters, and must be unique
            for ticket in tickets:
                if len(ticket[0].rstrip()) != 8:
                    self.scan_results[
                        f"Invalid ticket ID: {tickets.index(ticket)}"
                    ] = ticket[0].rstrip()
                    continue
                if ticket[0].rstrip() in self.scan_results.values():
                    self.scan_results[
                        f"Duplicate ticket ID: {tickets.index(ticket)}"
                    ] = ticket[0].rstrip()
            # If there is no Duplicate ticket ID key or Invalid ticket ID key,
            # then there are no issues
            if any(["Duplicate ticket ID", "Invalid ticket ID"]) in self.scan_results:
                self.scan_results["validity_ticketID"] = "No issues found."

            # Second scan, check for NULL category values or invalid category
            # values
            self.cursor.execute("SELECT id, category FROM tickets")
            tickets = self.cursor.fetchall()
            for ticket in tickets:
                if ticket[1] is None:
                    self.scan_results[
                        f"NULL category: {tickets.index(ticket)}"
                    ] = ticket[0].rstrip()
                    continue
                if ticket[1].rstrip() not in [
                    "Bug Report",
                    "Suggestion",
                    "Other",
                    "User " "Report",
                ]:
                    self.scan_results[
                        f"Invalid category: {tickets.index(ticket)}"
                    ] = ticket[0].rstrip()
                    continue
            if any(["NULL category", "Invalid category"]) in self.scan_results:
                self.scan_results["validity_ticketCategory"] = "No issues found."

            # Third scan, check for invalid opened_date values or future values
            # (opened_date must be in the past)
            self.cursor.execute("SELECT id, opened_date FROM tickets")
            tickets = self.cursor.fetchall()
            for ticket in tickets:
                if ticket[1] > datetime.datetime.now():
                    self.scan_results[
                        f"Future opened_date: {tickets.index(ticket)}"
                    ] = ticket[0].rstrip()
                    continue
                elif ticket[1] is None:
                    self.scan_results[
                        f"NULL opened_date: {tickets.index(ticket)}"
                    ] = ticket[0].rstrip()
                    continue
            if (
                any(
                    [
                        "Future opened_date",
                        "NULL opened_date",
                        "Invalid opened_date",
                    ],
                )
                in self.scan_results
            ):
                self.scan_results["validity_ticketOpenedDate"] = "No issues found."

            # Fourth scan, check for invalid Discord IDs
            self.cursor.execute("SELECT opened_by FROM tickets")
            tickets = self.cursor.fetchall()
            for ticket in tickets:
                if ticket[0].rstrip() is None:
                    self.scan_results[
                        f"NULL opened_by: {tickets.index(ticket)}"
                    ] = ticket[0].rstrip()
                    continue
                elif len(ticket[0].rstrip()) != 18:
                    self.scan_results[
                        f"Invalid opened_by: {tickets.index(ticket)}"
                    ] = ticket[0].rstrip()
                    continue
            if any(["NULL opened_by", "Invalid opened_by"]) in self.scan_results:
                self.scan_results["validity_ticketOpenedBy"] = "No issues found."

            # Fifth scan, check for invalid response_time values
            self.cursor.execute(
                "SELECT id, response_time FROM tickets WHERE closed = 'Y'",
            )
            tickets = self.cursor.fetchall()
            for ticket in tickets:
                if ticket[1].rstrip() is None:
                    self.scan_results[
                        f"NULL response_time: {tickets.index(ticket)}"
                    ] = ticket[0].rstrip()
                    continue
            if any(["NULL response_time"]) in self.scan_results:
                self.scan_results["validity_ticketResponseTime"] = "No issues found."

            # Sixth scan, check for invalid time_to_complete values
            self.cursor.execute(
                "SELECT id, time_to_complete FROM tickets WHERE closed = 'Y'",
            )
            tickets = self.cursor.fetchall()
            for ticket in tickets:
                if ticket[1].rstrip() is None:
                    self.scan_results[
                        f"NULL time_to_complete: {tickets.index(ticket)}"
                    ] = ticket[0].rstrip()
                    continue
            if any(["NULL time_to_complete"]) in self.scan_results:
                self.scan_results["validity_ticketTimeToComplete"] = "No issues found."

            # Seventh scan, check resolver Discord name is valid
            # Select unique resolver names
            self.cursor.execute(
                "SELECT DISTINCT resolver FROM tickets WHERE closed = 'Y'",
            )
            tickets = self.cursor.fetchall()
            for ticket in tickets:
                last4digits = ticket[0].rstrip()[-4:]
                try:
                    int(last4digits)
                    invalidLast4Digits = False
                except ValueError:
                    invalidLast4Digits = True
                if ticket[0].rstrip().rstrip() is None:
                    self.scan_results[
                        f"NULL resolver: {tickets.index(ticket)}"
                    ] = ticket[0].rstrip()
                    continue
                elif ticket[0].rstrip()[-5] != "#" or invalidLast4Digits:
                    self.scan_results[
                        f"Invalid resolver: {tickets.index(ticket)}"
                    ] = ticket[0].rstrip()
                    continue
            if any(["NULL resolver", "Invalid resolver"]) in self.scan_results:
                self.scan_results["validity_ticketResolver"] = "No issues found."

            # Eighth scan, check that transcripts are 12 characters and end in
            # .txt
            self.cursor.execute("SELECT transcript FROM tickets WHERE closed = 'Y'")
            tickets = self.cursor.fetchall()
            for ticket in tickets:
                if ticket[0].rstrip().rstrip() is None:
                    self.scan_results[
                        f"NULL transcript: {tickets.index(ticket)}"
                    ] = ticket[0].rstrip()
                    continue
                elif (
                    len(ticket[0].rstrip()) != 12
                    and ticket[0].rstrip()[-4:] != ".txt"
                    and ticket[0].rstrip() != "Bot Bug"
                ):
                    self.scan_results[
                        f"Invalid transcript: {tickets.index(ticket)}"
                    ] = ticket[0].rstrip()
                    continue
            if any(["NULL transcript", "Invalid transcript"]) in self.scan_results:
                self.scan_results["validity_ticketTranscript"] = "No issues found."

            """
            Database data consistency and integrity check
            """

            # First scan, check that all tickets have a corresponding
            # transcript
            self.cursor.execute("SELECT id FROM tickets WHERE closed = 'Y'")
            tickets = self.cursor.fetchall()
            self.cursor.execute("SELECT transcript FROM tickets WHERE closed = 'Y'")
            transcripts = self.cursor.fetchall()
            for ticket in tickets:
                if f"{ticket[0].rstrip()}.txt" not in os.listdir(
                    os.getcwd().replace("src", "transcripts"),
                ) and f"{ticket[0].rstrip().lower()}.txt" not in os.listdir(
                    os.getcwd().replace("src", "transcripts"),
                ):
                    self.scan_results[
                        f"Missing transcript: {tickets.index(ticket)}"
                    ] = ticket[0].rstrip()
                if f"{ticket[0].rstrip()}.txt" not in [
                    x[0] for x in transcripts
                ] and f"{ticket[0].rstrip().lower()}.txt" not in [
                    y[0] for y in transcripts
                ]:
                    self.scan_results[
                        f"Transcript not in database: {tickets.index(ticket)}"
                    ] = ticket[0].rstrip()
            if (
                any(["Missing transcript", "Transcript not in database"])
                in self.scan_results
            ):
                self.scan_results["ci_ticketTranscript"] = "No issues found."

            # Second scan, check that resolver names are still valid
            self.cursor.execute(
                "SELECT DISTINCT resolver FROM tickets WHERE closed = 'Y'",
            )
            tickets = self.cursor.fetchall()
            for ticket in tickets:
                # Get ticket[0] without the last 5 chars
                resolver = ticket[0].rstrip()[:-5]
                # Get ticket[0] but only the last 4 digits
                last4digits = ticket[0].rstrip()[-4:]
                # Search user in server by name (remove last 5 chars),
                # discriminator = last 4 digits
                user = discord.utils.get(
                    self.bot.get_all_members(),
                    name=resolver,
                    discriminator=last4digits,
                )
                if user is None:
                    self.scan_results[
                        f"Resolver name change: {tickets.index(ticket)}"
                    ] = ticket[0].rstrip()
            if any(["Resolver name change"]) in self.scan_results:
                self.scan_results["ci_ticketResolver"] = "No issues found."

            # Third scan, check that all open tickets are still valid channels
            self.cursor.execute("SELECT id, category FROM tickets WHERE closed = 'N'")
            tickets = self.cursor.fetchall()
            for ticket in tickets:
                # Try to get channel
                try:
                    discord.utils.get(
                        ctx.guild.channels,
                        name=ticket[0].lower().rstrip(),
                        category=ticket[1],
                    )
                except discord.errors.NotFound:
                    self.scan_results[
                        f"Ticket status mismatch: {tickets.index(ticket)}"
                    ] = ticket[0].rstrip()
            if any(["Ticket status mismatch"]) in self.scan_results:
                self.scan_results["ci_ticketStatus"] = "No issues found."

            # Fourth scan, check that all closed tickets have values in each
            # field
            self.cursor.execute(
                "SELECT id, category, opened_date, opened_by, response_time, time_to_complete, "
                "resolver, team, transcript, closed FROM tickets WHERE closed = 'Y'",
            )
            tickets = self.cursor.fetchall()
            for ticket in tickets:
                # Check that no values are NULL
                for value in ticket:
                    if value is None:
                        # The last %s should be the column name from the
                        # database
                        match ticket.index(value):
                            case 0:
                                column_name = "id"
                                self.scan_results[
                                    "NULL value found"
                                ] = f"{ticket[0]} has a NULL value: {value}, in the field {column_name}"
                                continue
                            case 1:
                                column_name = "category"
                                self.scan_results[
                                    "NULL value found"
                                ] = f"{ticket[0]} has a NULL value: {value}, in the field {column_name}"
                                continue
                            case 2:
                                column_name = "opened_date"
                                self.scan_results[
                                    "NULL value found"
                                ] = f"{ticket[0]} has a NULL value: {value}, in the field {column_name}"
                                continue
                            case 3:
                                column_name = "opened_by"
                                self.scan_results[
                                    "NULL value found"
                                ] = f"{ticket[0]} has a NULL value: {value}, in the field {column_name}"
                                continue
                            case 4:
                                column_name = "response_time"
                                self.scan_results[
                                    "NULL value found"
                                ] = f"{ticket[0]} has a NULL value: {value}, in the field {column_name}"
                                continue
                            case 5:
                                column_name = "time_to_complete"
                                self.scan_results[
                                    "NULL value found"
                                ] = f"{ticket[0]} has a NULL value: {value}, in the field {column_name}"
                                continue
                            case 6:
                                column_name = "resolver"
                                self.scan_results[
                                    "NULL value found"
                                ] = f"{ticket[0]} has a NULL value: {value}, in the field {column_name}"
                                continue
                            case 7:
                                column_name = "team"
                                self.scan_results[
                                    "NULL value found"
                                ] = f"{ticket[0]} has a NULL value: {value}, in the field {column_name}"
                                continue
                            case 8:
                                column_name = "transcript"
                                self.scan_results[
                                    "NULL value found"
                                ] = f"{ticket[0]} has a NULL value: {value}, in the field {column_name}"
                                continue
                            case 9:
                                column_name = "closed"
                                self.scan_results[
                                    "NULL value found"
                                ] = f"{ticket[0]} has a NULL value: {value}, in the field {column_name}"
                                continue
                            case _:
                                column_name = "Unknown"
                                self.scan_results[
                                    "NULL value found"
                                ] = f"{ticket[0]} has a NULL value: {value}, in the field {column_name}"
            if any(["NULL value found"]) in self.scan_results:
                self.scan_results["ci_ticketNulls"] = "No issues found."

            # Build the embed
            embed = discord.Embed(title="Database scan results", color=0x00FF00)
            embed.add_field(
                name="Database Validity Checks",
                value="These checks ensure that the entered data fits the parameters.",
                inline=False,
            )
            for key, value in list(self.scan_results.items()):
                # Check for all validity checks before checking for key
                # starting with validity_
                if any(
                    [
                        "Duplicate ticket ID" in key,
                        "Invalid ticket ID" in key,
                        "NULL category" in key,
                        "Invalid category" in key,
                        "Future opened_date" in key,
                        "NULL opened_date" in key,
                        "Invalid opened_date" in key,
                        "NULL opened_by" in key,
                        "Invalid opened_by" in key,
                        "NULL response_time" in key,
                        "Negative response_time" in key,
                        "NULL time_to_complete" in key,
                        "Negative time_to_complete" in key,
                        "NULL resolver" in key,
                        "Invalid resolver" in key,
                        "NULL transcript" in key,
                        "Invalid transcript" in key,
                    ],
                ):
                    embed.add_field(name=key, value=value, inline=False)
                    # Remove key from dictionary
                    self.scan_results.pop(key)
                elif any(
                    [
                        "validity_ticketID" in key,
                        "validity_ticketCategory" in key,
                        "validity_openedDate" in key,
                        "validity_openedBy" in key,
                        "validity_responseTime" in key,
                        "validity_timeToComplete" in key,
                        "validity_resolver" in key,
                        "validity_transcript" in key,
                    ],
                ):
                    embed.add_field(name=key, value=value, inline=False)
                    self.scan_results.pop(key)
                else:
                    continue
            embed.add_field(
                name="Database Consistency and Integrity Checks",
                value="These checks ensure that the data is consistent and accurate.",
                inline=False,
            )
            for key, value in list(self.scan_results.items()):
                if any(
                    [
                        "Missing transcript" in key,
                        "Transcript not in database" in key,
                        "Resolver name change" in key,
                        "Ticket status mismatch" in key,
                    ],
                ):
                    embed.add_field(name=key, value=value, inline=False)
                    self.scan_results.pop(key)
                elif any(
                    [
                        "ci_ticketResolver" in key,
                        "ci_ticketStatus" in key,
                        "ci_ticketNulls" in key,
                    ],
                ):
                    embed.add_field(name=key, value=value, inline=False)
                    self.scan_results.pop(key)
                else:
                    continue
        else:
            embed = EmbedBuilder(
                title="Error",
                description="You do not have permission to use this command.",
                color=0xFF0000,
            ).build()
        await ctx.respond(embed=embed, ephemeral=True)
