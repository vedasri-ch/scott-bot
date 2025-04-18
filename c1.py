import asyncio
import discord
import random
from discord.ext import commands
from discord import app_commands, Interaction
from discord.ui import Button, View
from collections import defaultdict, deque

GUILD_ID = discord.Object(id=1358853180179611888)

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.members = True

client = commands.Bot(command_prefix="/", intents=intents)

joined_players = []
roles = {}
turn_order = []
current_turn_index = 0
mr_x_ticket_log = deque(maxlen=5)  # Stores last 5 ticket types
round_counter = 1
MAX_ROUNDS = 24

MAX_PLAYERS = 4
ticket_limits = {"taxi": 10, "bus": 8, "metro": 4}
black_ticket_limit = 5

@client.tree.command(name="startgame", description="Starts a new Mr. X vs Detectives game", guild=GUILD_ID)
async def startgame(interaction: discord.Interaction):
    global joined_players, roles, turn_order, current_turn_index, mr_x_ticket_log
    joined_players = []
    roles = {}
    turn_order = []
    current_turn_index = 0
    mr_x_ticket_log.clear()

    embed = discord.Embed(
        title="Mr. X vs Detectives 🎩",
        description="🕵️ Up to 4 players can /join to participate.\nPick roles: 1 Mr. X and 3 Detectives.",
        color=discord.Color.dark_purple()
    )
    await interaction.response.send_message(embed=embed)