'''
MCLabs Discord Bot - Developer Cog

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

class Developer(commands.Cog):
	'''
	# Developer Cog

	Contains restricted administrative and testing tools for developers and admins.
	'''

	def __init__(self, bot: commands.Bot):
		self.bot = bot
		self.logger = logging.getLogger("MCL_DISCORD_Logger")
		self.logger.info("Developer Cog initialized!")

	def cog_check(self, ctx: commands.Context) -> bool:
		'''
		Cog-level check to restrict commands to users with specific developer/admin roles.
		'''

		# Ensure that command is being used in server
		if not ctx.guild:
			raise commands.NoPrivateMessage("This command cannot be used in private messages!")
		
		# Ensure that the command is being used by a human member
		if ctx.author.bot:
			raise commands.CheckFailure("This command cannot be used by bots!")
		if not isinstance(ctx.author, discord.Member):
			raise commands.CheckFailure("This command cannot be used by non-guild members!")

		# Define role IDs that are allowed to run developer commands
		allowed_roles = {
			1447520265113174066, # DEV ADMIN
			384788021876359179,  # SERVER OWNER
			384804758407479296,  # SERVER ADMIN
			939667997402992670,  # SERVER TRIAL ADMIN
		}
		
		# Check that member has one of the above roles
		if allowed_roles.isdisjoint({role.id for role in ctx.author.roles}):
			raise commands.CheckFailure("You do not have permission to use developer commands!")
		return True

	async def cog_command_error(self, ctx: commands.Context, error: Exception):
		'''
		Cog-level error handler to catch permission check failures.
		'''
		if isinstance(error, commands.CheckFailure):
			self.logger.warning(f"Unauthorized command attempt by {ctx.author}: {error}!")
			await ctx.send("You do not have permission to run this command!", ephemeral=True)
		else:
			self.logger.exception(f"Error in Developer cog: {error}!")
			raise error

	@commands.hybrid_command(name="ping", description="Ping the bot to check latency and status.")
	async def ping(self, ctx: commands.Context):
		'''
		# Ping Command

		Responds with the current latency of the Discord bot client.
		'''
		self.logger.info(f"Ping command invoked by {ctx.author}!")
		try:
			latency = round(self.bot.latency * 1000)
			await ctx.send(f"Pong! Latency is {latency}ms.")
		except Exception as e:
			self.logger.exception(f"Error executing /ping command: {e}")
			raise e

	@commands.hybrid_command(name="mirror", description="Mirror user details back in an ephemeral embed.")
	async def mirror(self, ctx: commands.Context):
		'''
		# Mirror Command

		Returns user details in an ephemeral embed.
		'''
		self.logger.info(f"Mirror command invoked by {ctx.author}!")
		try:
			embed = discord.Embed(
				title="User Info Mirror",
				description="Here is the user information retrieved from your command invocation:",
				color=discord.Color.green()
			)
			embed.add_field(name="Display Name", value=ctx.author.display_name, inline=True)
			embed.add_field(name="Username", value=ctx.author.name, inline=True)
			embed.add_field(name="User ID", value=str(ctx.author.id), inline=True)
			
			if isinstance(ctx.author, discord.Member):
				embed.add_field(name="Top Role", value=ctx.author.top_role.name, inline=True)
				if ctx.author.joined_at:
					embed.add_field(name="Joined Server", value=ctx.author.joined_at.strftime('%Y-%m-%d %H:%M:%S'), inline=True)
			
			await ctx.send(embed=embed, ephemeral=True)
		except Exception as e:
			self.logger.exception(f"Error executing /mirror command: {e}")
			raise e

async def setup(bot: commands.Bot):
	await bot.add_cog(Developer(bot))
