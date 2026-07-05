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

	@commands.hybrid_command(name="ping", description="Ping the bot to check latency and status.")
	async def ping(self, ctx: commands.Context):
		'''
		# Ping Command

		Responds with the current latency of the Discord bot client.
		'''
		self.logger.info(f"Ping command invoked by {ctx.author} in {ctx.channel}.")
		try:
			latency = round(self.bot.latency * 1000)
			await ctx.send(f"Pong! Latency is {latency}ms.")
		except Exception as e:
			self.logger.exception(f"Error executing /ping command: {e}")
			raise e

async def setup(bot: commands.Bot):
	await bot.add_cog(General(bot))
