'''
MCLabs Discord Bot - Outbound Relay

Author: Chris Hinkson @cmh02
'''

from discord import sticker
import os
import asyncio
import logging
import aiohttp
from typing import Dict, Any, Optional
from mcl_common.datatypes import PlayerInfo

logger = logging.getLogger("MCL_DISCORD_Logger")

class MCL_OutboundRelay:
	'''
	MCL Outbound Relay
	
	Manages outbound API calls to the MCLabs backend RAG API.
	Provides exponential backoff and automatic retry logic.
	'''
	_instance = None

	def __new__(cls, *args, **kwargs):
		if cls._instance is None:
			cls._instance = super(MCL_OutboundRelay, cls).__new__(cls)
		return cls._instance

	def initialize(self, bot):
		'''
		Initializes the relay with the bot instance and configuration variables.
		'''
		self.bot = bot

		# Get configuration variables
		self.token = os.getenv("API_TOKEN")
		if self.token is None:
			raise ValueError("API_TOKEN environment variable is not set.")
		self.apiUrl = os.getenv("RAILWAY_API_DOMAIN")
		if self.apiUrl is None:
			raise ValueError("RAILWAY_API_DOMAIN environment variable is not set.")
		self.userAgent = os.getenv("USER_AGENT_DISCORDBOT")
		if self.userAgent is None:
			raise ValueError("USER_AGENT_DISCORDBOT environment variable is not set.")

		# Track last successful API response time for lazy wakeup
		self._last_success_time = 0.0

		logger.info("Initialized MCL Outbound Relay for Discord Bot.")

	async def _post_with_retry(self, endpoint: str, json_data: Dict[str, Any], max_tries: int = 5, initial_delay: float = 3.0) -> bool:
		'''
		Helper to post data to the backend with exponential backoff.
		'''
		if not self.apiUrl:
			logger.error("RAILWAY_API_DOMAIN environment variable is not set.")
			return False

		url = f"https://{self.apiUrl}{endpoint}"
		headers = {
			"Content-Type": "application/json",
			"Authorization": self.token or "",
			"User-Agent": self.userAgent or "Discord-Bot"
		}

		import time
		delay = initial_delay
		for attempt in range(max_tries):
			# Ensure API is awake only if last success was > 5 minutes ago
			current_time = time.time()
			if current_time - self._last_success_time > 300.0:
				wakeup_tries = max_tries if attempt == 0 else 1
				logger.info(f"API last active check failed or timed out. Ensuring backend is awake (attempt {attempt + 1})...")
				is_awake = await self.bot.ensureApiAwake(numberTries=wakeup_tries, sleepInterval=int(delay))
				if not is_awake:
					logger.warning(f"Backend API is not awake on attempt {attempt + 1}.")
					self._last_success_time = 0.0
				else:
					self._last_success_time = time.time()

			try:
				async with self.bot.session.post(url, headers=headers, json=json_data, timeout=aiohttp.ClientTimeout(total=10)) as response:
					if response.status == 200:
						logger.info(f"Successfully posted to {endpoint} on attempt {attempt + 1}")
						self._last_success_time = time.time()
						return True
					else:
						text = await response.text()
						logger.warning(f"Failed POST to {endpoint} on attempt {attempt + 1}. Status {response.status}: {text}")
						self._last_success_time = 0.0
			except Exception as e:
				logger.error(f"Exception during POST to {endpoint} on attempt {attempt + 1}: {e}")
				self._last_success_time = 0.0

			await asyncio.sleep(delay)
			delay *= 2

		return False

	async def claim_ticket(self, ticket_id: int, claimed_by: str) -> bool:
		'''
		# Claim Ticket

		Sends a request to the backend RAG API to claim a ticket.
		'''
		return await self._post_with_retry(
			endpoint="/claim_ticket",
			json_data={
				"ticketId": ticket_id,
				"claimedBy": claimed_by
			}
		)

	async def unclaim_ticket(self, ticket_id: int) -> bool:
		'''
		# Unclaim Ticket

		Sends a request to the backend RAG API to unclaim a ticket.
		'''
		return await self._post_with_retry(
			endpoint="/unclaim_ticket",
			json_data={
				"ticketId": ticket_id
			}
		)

	async def close_ticket(self, ticket_id: int, closed_by: str) -> bool:
		'''
		# Close Ticket

		Sends a request to the backend RAG API to close/delete a ticket.
		'''
		return await self._post_with_retry(
			endpoint="/close_ticket",
			json_data={
				"ticketId": ticket_id,
				"closedBy": closed_by
			}
		)

	async def acknowledge_update(self, update_id: str) -> bool:
		'''
		# Acknowledge Update

		Sends a request to the backend RAG API to acknowledge a received relay update.
		'''
		return await self._post_with_retry(
			endpoint="/acknowledge_update",
			json_data={
				"guid": update_id
			}
		)

	async def update_ticket_thread(self, ticket_id: int, thread_id: int, status_message_id: Optional[int] = None) -> bool:
		'''
		# Update Ticket Thread

		Sends a request to the backend RAG API to set/update a ticket's thread ID and status message ID.
		'''
		json_data = {
			"ticketId": ticket_id,
			"threadId": thread_id
		}
		if status_message_id is not None:
			json_data["statusMessageId"] = status_message_id

		return await self._post_with_retry(
			endpoint="/update_ticket_thread",
			json_data=json_data
		)

	async def set_ticket_feedback(self, ticket_id: int, feedback: str) -> bool:
		'''
		# Set Ticket Feedback

		Sends a request to the backend RAG API to set feedback for a ticket.
		'''
		return await self._post_with_retry(
			endpoint="/set_ticket_feedback",
			json_data={
				"ticketId": ticket_id,
				"feedback": feedback
			}
		)

	async def append_ticket_message(self, ticket_id: int, content: str, sender: PlayerInfo) -> bool:
		'''
		# Append Ticket Message

		Sends a request to the backend RAG API to append a message to a ticket conversation.
		'''
		return await self._post_with_retry(
			endpoint="/append_ticket_message",
			json_data={
				"ticketId": ticket_id,
				"content": content,
				"sender": sender.toDict()
			}
		)
