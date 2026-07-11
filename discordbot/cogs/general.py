'''
MCLabs Discord Bot - General Cog

Author: Chris Hinkson @cmh02
'''

'''
MODULE IMPORTS
'''

import logging
import discord
from discord.ext import commands
from mcl_common.mongo import MCL_MongoManager

'''
COG DEFINITION
'''

class General(commands.Cog):
	'''
	# General Cog

	Contains utility and status commands.
	'''

	def __init__(self, bot: commands.Bot):
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

async def setup(bot: commands.Bot):
	await bot.add_cog(General(bot))
