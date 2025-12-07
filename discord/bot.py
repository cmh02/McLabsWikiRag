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
	try:

		# Make API request to wake up the API
		wakeup_payload = {"api_token": os.getenv("API_TOKEN")}
		wakeup_response = requests.post(f"https://{os.getenv('RAILWAY_API_DOMAIN')}/wakeup", json=wakeup_payload)
		wakeup_data = wakeup_response.json()

		# Make sure wakeup was successful
		if wakeup_response.status_code != 200:
			await interaction.response.send_message(content=f"An error has occured while waking up the API. Please contact a developer for further assistance!", ephemeral=True)
			print(f"Wakeup Error {wakeup_response.status_code}: {wakeup_data.get('error', 'Unknown error')}")
			return

		# Make API request to the RAG endpoint and get response
		query_payload = {"api_token": os.getenv("API_TOKEN"), "question": question, "include_context": "False"}
		query_response = requests.post(f"https://{os.getenv('RAILWAY_API_DOMAIN')}/query", json=query_payload)
		query_data = query_response.json()
		
		# Respond in Discord
		if query_response.status_code == 200:
			answer = query_data.get("answer", "An error has occured while processing your request. Please contact a developer for further assistance!")
			await interaction.response.send_message(content=answer, ephemeral=True)
		else:
			await interaction.response.send_message(content=f"An error has occured while processing your request. Please contact a developer for further assistance!", ephemeral=True)
			print(f"Query Error {query_response.status_code}: {query_data.get('error', 'Unknown error')}")

	except Exception as e:
		await interaction.response.send_message(content=f"An error has occured while processing your request. Please contact a developer for further assistance!", ephemeral=True)
		print(f"Exception: {e}")

# Run the bot
bot.run(os.getenv("DISCORD_BOT_TOKEN"))