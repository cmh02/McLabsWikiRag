from __future__ import annotations
'''
MCLabs Discord Bot - General Cog

Author: Chris Hinkson @cmh02
'''

'''
MODULE IMPORTS
'''

import os
import asyncio
import aiohttp
import logging
import discord
from discord.ext import commands
from typing import TYPE_CHECKING
from mcl_common.mongo import MCL_MongoManager

if TYPE_CHECKING:
	from discordbot.bot import MclBot

'''
COG DEFINITION
'''

class General(commands.Cog):
	'''
	# General Cog

	Contains utility and status commands.
	'''

	def __init__(self, bot: MclBot):
		self.bot = bot
		self.logger = logging.getLogger("MCL_DISCORD_Logger")
		self.logger.info("General Cog initialized!")

	@commands.hybrid_command(name="ip", description="Get the server IP address.")
	async def ip(self, ctx: commands.Context):
		'''
		# IP Command

		Sends the server IP address to the user ephemerally in an embed.
		'''
		self.logger.info(f"IP command invoked by {ctx.author}!")
		try:
			embed = discord.Embed(
				title="MCLabs Server IP",
				description="Connect to the server using the IP address below:",
				color=discord.Color.blue()
			)
			embed.add_field(name="Server IP", value="`play.labs-mc.com`", inline=True)
			await ctx.send(embed=embed, ephemeral=True)
		except Exception as e:
			self.logger.exception(f"Error executing /ip command: {e}")
			raise e

	@commands.hybrid_command(name="version", description="Get the server version.")
	async def version(self, ctx: commands.Context):
		'''
		# Version Command

		Sends the server version to the user ephemerally in an embed.
		'''
		self.logger.info(f"Version command invoked by {ctx.author}!")
		try:
			embed = discord.Embed(
				title="MCLabs Server Version",
				description="Here is the supported version for the server:",
				color=discord.Color.blue()
			)
			embed.add_field(name="Version", value="`1.21.11`", inline=True)
			await ctx.send(embed=embed, ephemeral=True)
		except Exception as e:
			self.logger.exception(f"Error executing /version command: {e}")
			raise e

	@commands.hybrid_command(name="info", description="Get general information about the server.")
	async def info(self, ctx: commands.Context):
		'''
		# Info Command

		Sends an embed with server features, version, and IP ephemerally.
		'''
		self.logger.info(f"Info command invoked by {ctx.author}!")
		try:
			embed = discord.Embed(
				title="MCLabs Server Information",
				description="Welcome to MCLabs! Here is everything you need to know to get started:",
				color=discord.Color.blue()
			)
			embed.add_field(name="Server IP", value="`play.labs-mc.com`", inline=True)
			embed.add_field(name="Version", value="`1.21.11`", inline=True)
			embed.add_field(name="Features & Gameplay", value=(
				"🧪 **Sell Chems:** Build your chemical empire and sell for profits!\n"
				"👥 **Find Community:** Join companies/towns and meet other players!\n"
				"🏆 **Compete on Leaderboards:** Rise to the top of the server leaderboards!"
			), inline=False)
			
			await ctx.send(embed=embed, ephemeral=True)
		except Exception as e:
			self.logger.exception(f"Error executing /info command: {e}")
			raise e

	@commands.hybrid_command(name="status", description="Check the current status and performance of the Minecraft server.")
	async def status(self, ctx: commands.Context):
		'''
		# Status Command

		Queries MongoDB and displays the Minecraft server status ephemerally.
		'''
		self.logger.info(f"Status command invoked by {ctx.author}!")
		try:
			mongo = MCL_MongoManager()
			status = await asyncio.to_thread(mongo.getServerStatus)
			
			if not status or not status.online:
				embed = discord.Embed(
					title="🖥️ MCLabs Server Status",
					description="The Minecraft server is currently offline or status information is unavailable.",
					color=discord.Color.red()
				)
				embed.add_field(name="Status", value="🔴 Offline", inline=True)
				if status and status.last_updated:
					embed.add_field(name="Last Checked", value=f"<t:{int(status.last_updated)}:R>", inline=True)
				embed.set_footer(text="MCLabs Server Status")
				await ctx.send(embed=embed, ephemeral=True)
				return

			# Status is online
			color = discord.Color.green()
			embed = discord.Embed(
				title="🖥️ MCLabs Server Status",
				description="Real-time performance and player activity statistics for the MCLabs Minecraft server.",
				color=color,
				timestamp=discord.utils.utcnow()
			)
			embed.add_field(name="Status", value="🟢 Online", inline=True)
			embed.add_field(name="Players Online", value=f"👥 `{status.player_count} / {status.max_players}`", inline=True)
			embed.add_field(name="Server Uptime", value=f"⏳ {status.uptime}", inline=True)

			# Format TPS status
			tps_val = status.tps
			if tps_val >= 19.5:
				tps_str = f"🟢 `{tps_val:.2f}` (Excellent)"
			elif tps_val >= 18.0:
				tps_str = f"🟡 `{tps_val:.2f}` (Good)"
			else:
				tps_str = f"🔴 `{tps_val:.2f}` (Lagging)"
			
			embed.add_field(name="Performance (TPS)", value=tps_str, inline=True)
			embed.add_field(name="Last Updated", value=f"<t:{int(status.last_updated)}:R>", inline=True)
			embed.set_footer(text="MCLabs Server Status")
			
			await ctx.send(embed=embed, ephemeral=True)
		except Exception as e:
			self.logger.exception(f"Error executing /status command: {e}")
			raise e

	@commands.hybrid_command(name="link", description="Manually link your Discord account to your Minecraft account.")
	@discord.app_commands.describe(name="Your Minecraft username")
	async def link(self, ctx: commands.Context, name: str):
		'''
		# Link Command

		Links a user's Discord account to a Minecraft username by calling the backend's /resolve_player endpoint.
		Displays the resolved profile info in a beautiful ephemeral embed.
		'''
		self.logger.info(f"Link command invoked by {ctx.author} for Minecraft name: {name}!")

		# Defer ephemerally because API/Mojang lookup can take up to a few seconds
		await ctx.defer(ephemeral=True)

		# Get environment settings
		domain_backend = os.getenv("RAILWAY_API_DOMAIN")
		if not domain_backend:
			await ctx.send("Error: RAILWAY_API_DOMAIN environment variable is not set.", ephemeral=True)
			return

		token = os.getenv("API_TOKEN")
		if not token:
			await ctx.send("Error: API_TOKEN environment variable is not set.", ephemeral=True)
			return

		user_agent = os.getenv("USER_AGENT_DISCORDBOT")
		if not user_agent:
			await ctx.send("Error: USER_AGENT_DISCORDBOT environment variable is not set.", ephemeral=True)
			return

		headers = {
			"Content-Type": "application/json",
			"Authorization": token,
			"User-Agent": user_agent
		}

		payload = {
			"playerInfo": {
				"minecraftUsername": name.strip(),
				"discordId": str(ctx.author.id),
				"discordUsername": ctx.author.name
			}
		}

		url = f"https://{domain_backend}/resolve_player"

		try:
			# Make request to backend /resolve_player using self.bot.session
			async with self.bot.session.post(url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
				if resp.status != 200:
					self.logger.error(f"Backend resolve_player endpoint returned status {resp.status}")
					await ctx.send("Failed to communicate with the backend. Please try again later.", ephemeral=True)
					return

				resp_json = await resp.json()
				player_data = resp_json.get("playerInfo")

				if not player_data:
					await ctx.send("Failed to retrieve player information.", ephemeral=True)
					return

				mc_name = player_data.get("minecraftUsername")
				mc_uuid = player_data.get("minecraftUUID")
				discord_name = player_data.get("discordUsername")
				discord_id = player_data.get("discordId")

				# If minecraftUUID wasn't resolved, it means Mojang could not find the username
				if not mc_uuid or mc_uuid == "Unknown" or mc_uuid == "00000000-0000-0000-0000-000000000000":
					embed = discord.Embed(
						title="❌ Account Linking Failed",
						description=f"Could not find a Minecraft account with the username `{name}`.\nPlease verify the name and try again.",
						color=discord.Color.red()
					)
					await ctx.send(embed=embed, ephemeral=True)
					return

				# Successful link - Create a premium-designed, beautiful glassmorphism-style embed
				embed = discord.Embed(
					title="🔗 Account Linked Successfully!",
					description="Your Discord and Minecraft accounts have been successfully associated.",
					color=discord.Color.from_rgb(0, 205, 246), # #00cdf6 - MC Labs Light Blue
					timestamp=discord.utils.utcnow()
				)
				
				embed.add_field(name="🎮 Minecraft Username", value=f"`{mc_name}`", inline=True)
				embed.add_field(name="🆔 Minecraft UUID", value=f"`{mc_uuid}`", inline=False)
				embed.add_field(name="💬 Discord Username", value=f"`{discord_name}`", inline=True)
				embed.add_field(name="🆔 Discord ID", value=f"`{discord_id}`", inline=True)
				
				# Fetch head helm for visual wow factor
				embed.set_thumbnail(url=f"https://minotar.net/helm/{mc_name}/120.png")
				embed.set_footer(text="MCLabs Linking System • Real-Time Database Sync", icon_url=self.bot.user.avatar.url if self.bot.user and self.bot.user.avatar else None)

				await ctx.send(embed=embed, ephemeral=True)

		except aiohttp.ClientConnectorError:
			self.logger.exception("Network connection error to backend resolve_player")
			await ctx.send("Failed to connect to the backend service. It might be asleep or offline.", ephemeral=True)
		except Exception as e:
			self.logger.exception(f"Unexpected error in /link command: {e}")
			await ctx.send(f"An unexpected error occurred: {str(e)}", ephemeral=True)

	@commands.hybrid_command(name="leaderboard", description="View the helper leaderboard for support tickets.")
	async def leaderboard(self, ctx: commands.Context):
		"""
		# Leaderboard Command

		Displays the helper leaderboard based on support tickets claimed and feedback received.
		"""
		self.logger.info(f"Leaderboard command invoked by {ctx.author}!")
		
		# Ensure context is in a guild
		if not ctx.guild or not isinstance(ctx.author, discord.Member):
			await ctx.send("This command can only be used in a server.", ephemeral=True)
			return

		# Check helper permissions
		from discordbot.components.ticket_view import is_helper_plus
		if not is_helper_plus(ctx.author):
			await ctx.send("You do not have permission to view the helper leaderboard.", ephemeral=True)
			return

		await ctx.defer(ephemeral=True)

		try:
			mongo = MCL_MongoManager()
			results = await asyncio.to_thread(mongo.getHelperLeaderboard)

			if not results:
				embed = discord.Embed(
					title="🏆 Helper Leaderboard",
					description="No tickets have been claimed yet.",
					color=discord.Color.from_rgb(0, 205, 246),
					timestamp=discord.utils.utcnow()
				)
				await ctx.send(embed=embed, ephemeral=True)
				return

			embed = discord.Embed(
				title="🏆 Helper Leaderboard",
				description="Leaderboard of staff members ranked by total claimed tickets.",
				color=discord.Color.from_rgb(0, 205, 246),
				timestamp=discord.utils.utcnow()
			)

			leaderboard_text = []
			for idx, row in enumerate(results, 1):
				claimed_by_id = row["_id"]
				total_claimed = row["total_claimed"]
				pos = row["positive"]
				neg = row["negative"]
				no_fb = row["no_feedback"]

				# Resolve the user id to a readable mention or string representation
				member = ctx.guild.get_member(int(claimed_by_id))
				if not member:
					try:
						member = await self.bot.fetch_user(int(claimed_by_id))
					except Exception:
						member = None

				user_name = member.mention if member else f"User ID: {claimed_by_id}"

				leaderboard_text.append(
					f"**{idx}.** {user_name}\n"
					f"└ 🎟️ **Total Claimed:** `{total_claimed}` | 👍 `{pos}` | 👎 `{neg}` | ❔ `{no_fb}`"
				)

			# Embed limit safety: limit to top 15 helpers
			description_content = "\n\n".join(leaderboard_text[:15])
			if len(leaderboard_text) > 15:
				description_content += f"\n\n*And {len(leaderboard_text) - 15} more staff members...*"

			embed.description = f"Leaderboard of staff members ranked by total claimed tickets.\n\n{description_content}"
			embed.set_footer(text="MCLabs Ticket System • Helper Leaderboard", icon_url=self.bot.user.avatar.url if self.bot.user and self.bot.user.avatar else None)
			await ctx.send(embed=embed, ephemeral=True)

		except Exception as e:
			self.logger.exception(f"Error executing /leaderboard command: {e}")
			await ctx.send("An error occurred while generating the leaderboard.", ephemeral=True)

	@commands.hybrid_command(name="help", description="List all available commands and their usage details.")
	async def help(self, ctx: commands.Context):
		'''
		# Help Command

		Sends a beautifully structured list of all bot commands.
		Conditionally displays developer/admin commands if the user has Administrator permissions.
		'''
		self.logger.info(f"Help command invoked by {ctx.author}!")
		try:
			embed = discord.Embed(
				title="📚 MCLabs Help Menu",
				description="Here is a categorized list of all commands you can use with the MCLabs Discord Bot:",
				color=discord.Color.from_rgb(0, 205, 246),
				timestamp=discord.utils.utcnow()
			)

			# General Commands
			general_cmds = (
				"**/info** - Get general information about the server, gameplay features, version, and IP.\n"
				"**/ip** - Get the Minecraft server IP address.\n"
				"**/version** - Get the supported Minecraft game version.\n"
				"**/status** - Check real-time Minecraft server status, player counts, uptime, and TPS.\n"
				"**/link [name]** - Link your Discord account to your Minecraft account."
			)
			embed.add_field(name="🌐 General Commands", value=general_cmds, inline=False)

			# Help & Support
			support_cmds = (
				"**/ask [question]** - Open a private support ticket thread to ask a question."
			)
			embed.add_field(name="🎫 Help & Support", value=support_cmds, inline=False)

			# Check permissions to see if developer/staff commands should be listed
			is_admin = False
			is_helper = False
			if ctx.guild and isinstance(ctx.author, discord.Member):
				is_admin = ctx.author.guild_permissions.administrator
				from discordbot.components.ticket_view import is_helper_plus
				is_helper = is_helper_plus(ctx.author)

			if is_admin or is_helper:
				dev_cmds_list = []
				if is_admin:
					dev_cmds_list.append("**/ping** - Check bot latency and client status.")
					dev_cmds_list.append("**/mirror** - Mirror your Discord user info back in an embed.")
				if is_helper:
					dev_cmds_list.append("**/leaderboard** - View the helper leaderboard for support tickets.")
				
				dev_cmds = "\n".join(dev_cmds_list)
				embed.add_field(name="🛠️ Developer / Staff Commands", value=dev_cmds, inline=False)

			embed.set_footer(text="MCLabs Help System", icon_url=self.bot.user.avatar.url if self.bot.user and self.bot.user.avatar else None)
			await ctx.send(embed=embed, ephemeral=True)
		except Exception as e:
			self.logger.exception(f"Error executing /help command: {e}")
			raise e

async def setup(bot: MclBot):
	await bot.add_cog(General(bot))
