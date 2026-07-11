import os
import uuid
import aiohttp
from typing import Optional, Dict, Any

class UserInfoLookup:
	"""
	# UserInfoLookup

	Common helper module to query external systems (Mojang and Discord) for user information using asyncio/aiohttp.
	"""

	# Static System Endpoints
	API_UUID_BY_NAME: str = "https://api.mojang.com/users/profiles/minecraft/"
	API_NAME_BY_UUID: str = "https://sessionserver.mojang.com/session/minecraft/profile/"
	API_DISCORD_USER_BY_ID: str = "https://discord.com/api/v10/users/"

	@staticmethod
	async def getMinecraftUuidByName(username: str) -> Optional[str]:
		"""
		## Get Minecraft UUID By Name

		Queries Mojang's API to get the dashed UUID for a player username.
		"""

		# Validate that username was given
		if not username:
			return None

		# Make request to Mojang API to get UUID
		rawUuid: str | None = None
		url: str = f"{UserInfoLookup.API_UUID_BY_NAME}{username}"
		try:
			async with aiohttp.ClientSession() as session:
				async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
					if response.status == 200:
						data = await response.json()
						rawUuid = data.get("id")
		except Exception:
			pass
		
		# Convert raw UUID to dashed format and return if successful
		if rawUuid:
			rawUuid = str(uuid.UUID(rawUuid))
		return rawUuid

	@staticmethod
	async def getMinecraftNameByUuid(uuidStr: str) -> Optional[str]:
		"""
		## Get Minecraft Name By UUID

		Queries Mojang's API to get the username for a player UUID.
		Supports both dashed and undashed UUID formats.
		"""

		# Validate that uuidStr was given
		if not uuidStr:
			return None

		# Clean UUID if it is dashed for the API endpoint
		cleanUuid = uuidStr.replace("-", "")
		url: str = f"{UserInfoLookup.API_NAME_BY_UUID}{cleanUuid}"
		name: str | None = None
		try:
			async with aiohttp.ClientSession() as session:
				async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
					if response.status == 200:
						data = await response.json()
						name = data.get("name")
		except Exception:
			pass
		return name

	@staticmethod
	async def getDiscordUserById(discordId: str) -> Optional[Dict[str, Any]]:
		"""
		## Get Discord User By ID

		Queries Discord's REST API using the bot token in the environment to get user details.
		"""

		# Validate that discordId was given
		if not discordId:
			return None

		# We use bot token here to auth to Discord API
		botToken: str | None = os.getenv("DISCORD_BOT_TOKEN")
		if not botToken:
			raise EnvironmentError("DISCORD_BOT_TOKEN is not set")

		# We use backend user agent for sending request
		userAgent: str | None = os.getenv("USER_AGENT_BACKEND")
		if not userAgent:
			raise EnvironmentError("USER_AGENT_BACKEND is not set")

		# Make request for Discord user
		url: str = f"{UserInfoLookup.API_DISCORD_USER_BY_ID}{discordId}"
		headers: Dict[str, str] = {
			"Authorization": f"Bot {botToken}",
			"User-Agent": userAgent
		}
		user: Dict[str, Any] | None = None
		try:
			async with aiohttp.ClientSession() as session:
				async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=5)) as response:
					if response.status == 200:
						user = await response.json()
		except Exception:
			pass
		return user

