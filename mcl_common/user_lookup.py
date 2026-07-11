import os
import uuid
import aiohttp
from typing import Optional, Dict, Any

class UserInfoLookup:
	"""
	# UserInfoLookup

	Common helper module to query external systems (Mojang and Discord) for user information using asyncio/aiohttp.
	"""

	@staticmethod
	async def getMinecraftUuidByName(username: str) -> Optional[str]:
		"""
		## Get Minecraft UUID By Name

		Queries Mojang's API to get the dashed UUID for a player username.
		"""
		if not username:
			return None

		url = f"https://api.mojang.com/users/profiles/minecraft/{username}"
		try:
			async with aiohttp.ClientSession() as session:
				async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
					if response.status == 200:
						data = await response.json()
						rawUuid = data.get("id")
						if rawUuid:
							# Convert undashed UUID to standard dashed UUID format
							return str(uuid.UUID(rawUuid))
		except Exception:
			pass
		return None

	@staticmethod
	async def getMinecraftNameByUuid(uuidStr: str) -> Optional[str]:
		"""
		## Get Minecraft Name By UUID

		Queries Mojang's API to get the username for a player UUID.
		Supports both dashed and undashed UUID formats.
		"""
		if not uuidStr:
			return None

		# Clean UUID if it is dashed for the API endpoint
		cleanUuid = uuidStr.replace("-", "")
		url = f"https://sessionserver.mojang.com/session/minecraft/profile/{cleanUuid}"
		try:
			async with aiohttp.ClientSession() as session:
				async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
					if response.status == 200:
						data = await response.json()
						return data.get("name")
		except Exception:
			pass
		return None

	@staticmethod
	async def getDiscordUserById(discordId: str) -> Optional[Dict[str, Any]]:
		"""
		## Get Discord User By ID

		Queries Discord's REST API using the bot token in the environment to get user details.
		"""
		if not discordId:
			return None

		botToken = os.getenv("DISCORD_BOT_TOKEN")
		if not botToken:
			return None

		url = f"https://discord.com/api/v10/users/{discordId}"
		headers = {
			"Authorization": f"Bot {botToken}",
			"User-Agent": "MCLabsWikiGpt (https://github.com/cmh02, v1.0.0)"
		}
		try:
			async with aiohttp.ClientSession() as session:
				async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=5)) as response:
					if response.status == 200:
						return await response.json()
		except Exception:
			pass
		return None

