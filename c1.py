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

@client.tree.command(name="join", description="Join the Game", guild=GUILD_ID)
async def join(interaction: discord.Interaction):
    user = interaction.user
    if user in joined_players:
        await interaction.response.send_message("You've already joined!", ephemeral=True)
        return
    if len(joined_players) >= MAX_PLAYERS:
        await interaction.response.send_message("Game is full!", ephemeral=True)
        return
    joined_players.append(user)
    await interaction.response.send_message(f"👤 {user.mention} joined!", ephemeral=False)
    # await send_role_selection(user, interaction.channel)


@client.tree.command(name="begin", description="Begin the game", guild=GUILD_ID)
async def begin(interaction: discord.Interaction):
    global turn_order, current_turn_index

    if not roles or sum(1 for r in roles.values() if r["role"] == "Mr. X") != 1:
        await interaction.response.send_message("❌ Need exactly 1 Mr. X and some Detectives to start!", ephemeral=True)
        return

    for user in joined_players:
        location = random.randint(1, 200)
        roles[user.id]["location"] = location
        # live_map_attempt_2.update_player_location(user.id,location,roles)

    mr_x_id = next(uid for uid, r in roles.items() if r["role"] == "Mr. X")
    turn_order = [mr_x_id] + [uid for uid, r in roles.items() if r["role"] == "Detective"]
    current_turn_index = 0

    detectives = [f"<@{uid}> → **Detective** at location {roles[uid]['location']}" for uid in turn_order if roles[uid]["role"] == "Detective"]
    await interaction.response.send_message(embed=discord.Embed(
        title="✅ Game Started!",
        description="**Final Teams:**\n" + "\n".join(detectives),
        color=discord.Color.green()
    ))

    mr_x = await interaction.guild.fetch_member(mr_x_id)
    try:
        await mr_x.send(f"🔒 Your secret starting location is **{roles[mr_x_id]['location']}**")
    except discord.Forbidden:
        await interaction.followup.send("❌ Couldn't send Mr. X their location. Please enable DMs from server members.", ephemeral=True)
    # await send_map(interaction.channel)
    next_player = await interaction.guild.fetch_member(turn_order[current_turn_index])
    await interaction.followup.send(f"🎲 It's {next_player.mention}'s turn!", ephemeral=False)
