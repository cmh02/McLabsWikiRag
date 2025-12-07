'''
MCLabs Wiki GPT - Discord Bot

Author: Chris Hinkson @cmh02
'''

'''
MODULE IMPORTS
'''

import os
import requests
import discord
from discord import app_commands
from discord.ext import commands

'''
ENVIRONMENTAL VARIABLES
'''

# Configure Discord intents
intents = discord.Intents.default()
intents.messages = True

# Initialize bot
bot = commands.Bot(command_prefix="/", intents=intents, activity=discord.Streaming(name="MCLabs Wiki", url="https://labs-mc.com/wiki/Main_Page"))

@bot.event
async def on_ready():
    print(f"Discord bot is ready!")
    await bot.tree.sync()

@bot.tree.command(name="ask", description="Ask me anything!")
async def ask(interaction: discord.Interaction, question: str):

	# Make API request to wake up the API, trying a few times if necessary
	try:
		wakeup_payload = {"api_token": os.getenv("API_TOKEN")}
		wakeupCount = 0, isAwake = False
		while (wakeupCount < 5) and not isAwake:
			wakeup_response = requests.post(f"https://{os.getenv('RAILWAY_API_DOMAIN')}/wakeup", json=wakeup_payload)
			wakeup_data = wakeup_response.json()
			if wakeup_response.status_code in [200, 429]:
				isAwake = True
			else:
				wakeupCount += 1
		if not isAwake:
			await interaction.response.send_message(content=f"The API is currently unavailable. Please try again later.", ephemeral=True)
			print(f"Wakeup Failed after 5 attempts.")
	except Exception as e:
		await interaction.response.send_message(content=f"An error has occured while waking up the API. Please contact a developer for further assistance!", ephemeral=True)
		print(f"Wakeup Exception [ERROR CODE 001]: {e}")
		return

	# Make sure wakeup was successful
	try:
		if wakeup_response.status_code not in [200, 429]:
			await interaction.response.send_message(content=f"An error has occured while waking up the API. Please contact a developer for further assistance!", ephemeral=True)
			print(f"Wakeup Error {wakeup_response.status_code}: {wakeup_data.get('error', 'Unknown error')}")
			return
	except Exception as e:
		await interaction.response.send_message(content=f"An error has occured while waking up the API. Please contact a developer for further assistance!", ephemeral=True)
		print(f"Wakeup Exception [ERROR CODE 002]: {e}")
		return

	# Make API request to the RAG endpoint and get response
	try:
		query_payload = {"api_token": os.getenv("API_TOKEN"), "question": question, "include_context": "False"}
		query_response = requests.post(f"https://{os.getenv('RAILWAY_API_DOMAIN')}/query", json=query_payload)
		query_data = query_response.json()
	except Exception as e:
		await interaction.response.send_message(content=f"An error has occured while querying the API. Please contact a developer for further assistance!", ephemeral=True)
		print(f"Query Exception [ERROR CODE 003]: {e}")
		return
	
	# Respond in Discord
	try:
		if query_response.status_code == 200:
			answer = query_data.get("answer", "An error has occured while processing your request. Please contact a developer for further assistance!")
			await interaction.response.send_message(content=answer, ephemeral=True)
		elif query_response.status_code == 429:
			await interaction.response.send_message(content=f"We are experiencing an increased number of requests. Please try again later.", ephemeral=True)
			print(f"Rate Limit Hit: {query_data}")
		else:
			await interaction.response.send_message(content=f"An error has occured while processing your request. Please contact a developer for further assistance!", ephemeral=True)
			print(f"Query Error {query_response.status_code}: {query_data.get('error', 'Unknown error')}")
	except Exception as e:
		await interaction.response.send_message(content=f"An error has occured while responding to your request. Please contact a developer for further assistance!", ephemeral=True)
		print(f"Response Exception [ERROR CODE 004]: {e}")

# Run the bot
bot.run(os.getenv("DISCORD_BOT_TOKEN"))