from __future__ import annotations
'''
MCLabs Discord Bot - General Cog

Author: Chris Hinkson @cmh02
'''

'''
MODULE IMPORTS
'''

import os
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
			status = mongo.getServerStatus()
			
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

async def setup(bot: MclBot):
	await bot.add_cog(General(bot))
