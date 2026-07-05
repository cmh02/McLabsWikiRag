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

		Sends the server IP address to the user ephemerally.
		'''
		self.logger.info(f"IP command invoked by {ctx.author}!")
		try:
			await ctx.send("Server IP: play.labs-mc.com", ephemeral=True)
		except Exception as e:
			self.logger.exception(f"Error executing /ip command: {e}")
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
				"👥 **Find Community:** Join factions/towns and meet other players!\n"
				"🏗️ **Claim & Build:** Secure your territory and build your dream base!"
			), inline=False)
			
			await ctx.send(embed=embed, ephemeral=True)
		except Exception as e:
			self.logger.exception(f"Error executing /info command: {e}")
			raise e

async def setup(bot: commands.Bot):
	await bot.add_cog(General(bot))
