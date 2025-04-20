import discord
from discord.ext import commands
from discord import app_commands, Interaction
from discord.ui import Button, View
import os
from dotenv import load_dotenv
from game import GameState
import io
import random

# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD_ID = discord.Object(id=int(os.getenv('GUILD_ID')))

# Set up bot
intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.members = True

client = commands.Bot(command_prefix="/", intents=intents)
game_state = GameState()

class TransportSelectView(View):
    def __init__(self, user: discord.User, dest: int, interaction: Interaction):
        super().__init__(timeout=60)
        self.user = user
        self.dest = dest
        self.interaction = interaction
        self.current_location = game_state.player_locations.get(user.id)
        self.available_transports = game_state.get_available_transports(user.id, self.current_location, dest)
        
        for transport in self.available_transports:
            self.add_item(self.TransportButton(transport, user, dest, interaction, self))

    async def on_timeout(self):
        await self.interaction.followup.send("Selection timed out. Please try again.", ephemeral=True)

    class TransportButton(Button):
        def __init__(self, transport, user, dest, interaction, parent):
            super().__init__(label=transport, style=discord.ButtonStyle.primary)
            self.transport = transport
            self.user = user
            self.dest = dest
            self.interaction = interaction
            self.parent = parent

        async def callback(self, interaction: discord.Interaction):
            if interaction.user != self.user:
                await interaction.response.send_message("This is not your move!", ephemeral=True)
                return

            is_valid, error_message = game_state.validate_move(self.user.id, self.dest, self.transport)
            if not is_valid:
                await interaction.response.send_message(error_message, ephemeral=True)
                return

            game_state.execute_move(self.user.id, self.dest, self.transport)
            
            # Check for game end
            end_message = game_state.check_end_conditions()
            if end_message:
                await interaction.response.send_message(end_message)
                game_state.reset()
                return

            # Advance turn
            game_state.advance_turn()
            
            # Update map
            await self.parent.interaction.followup.send(f"{self.user.mention} moved to {self.dest} using {self.transport}")
            await send_map(interaction.channel, interaction, zoom_player=self.user.id)

class RoleSelectView(View):
    def __init__(self, user):
        super().__init__(timeout=60)
        self.user = user

    async def on_timeout(self):
        await self.user.send("Role selection timed out. Please try joining again.")

    @discord.ui.button(label="🕵 Detective", style=discord.ButtonStyle.primary)
    async def detect(self, interaction: Interaction, button: Button):
        if interaction.user != self.user:
            await interaction.response.send_message("This selection is not for you!", ephemeral=True)
            return

        if "Detective" in game_state.roles.values():
            await interaction.response.send_message("A detective has already been chosen!", ephemeral=True)
            return

        game_state.roles[interaction.user.id] = "Detective"
        game_state.joined_players.append(interaction.user.id)
        await interaction.response.send_message("You have chosen to be a Detective!", ephemeral=True)
        self.stop()

    @discord.ui.button(label="🕶 Mr. X", style=discord.ButtonStyle.danger)
    async def mr_x(self, interaction: Interaction, button: Button):
        if interaction.user != self.user:
            await interaction.response.send_message("This selection is not for you!", ephemeral=True)
            return

        if game_state.mr_x_id is not None:
            await interaction.response.send_message("Mr. X has already been chosen!", ephemeral=True)
            return

        game_state.roles[interaction.user.id] = "Mr. X"
        game_state.joined_players.append(interaction.user.id)
        game_state.mr_x_id = interaction.user.id
        await interaction.response.send_message("You have chosen to be Mr. X!", ephemeral=True)
        self.stop()

async def send_map(channel, interaction=None, zoom_player=None, is_turn=False):
    map_image = live_map.generate_map(
        game_state.player_locations,
        game_state.round_counter,
        zoom_player,
        game_state.mr_x_id
    )
    
    # Convert PIL Image to bytes
    img_byte_arr = io.BytesIO()
    map_image.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    
    # Send the image
    file = discord.File(img_byte_arr, filename='map.png')
    if interaction:
        await interaction.followup.send(file=file)
    else:
        await channel.send(file=file)

@client.tree.command(name="startgame", description="Start a new game", guild=GUILD_ID)
async def startgame(interaction: discord.Interaction):
    if game_state.joined_players:
        await interaction.response.send_message("A game is already in progress!", ephemeral=True)
        return

    game_state.reset()
    await interaction.response.send_message("A new game has started! Use /join to participate.")

@client.tree.command(name="join", description="Join the game", guild=GUILD_ID)
async def join(interaction: discord.Interaction):
    if interaction.user.id in game_state.joined_players:
        await interaction.response.send_message("You have already joined the game!", ephemeral=True)
        return

    if len(game_state.joined_players) >= game_state.MAX_PLAYERS:
        await interaction.response.send_message("The game is full!", ephemeral=True)
        return

    view = RoleSelectView(interaction.user)
    await interaction.response.send_message("Choose your role:", view=view, ephemeral=True)

@client.tree.command(name="map", description="Display the current game map", guild=GUILD_ID)
async def map(interaction: discord.Interaction):
    await interaction.response.defer()
    await send_map(interaction.channel, interaction)

@client.tree.command(name="begin", description="Begin the game", guild=GUILD_ID)
async def begin(interaction: discord.Interaction):
    if not game_state.joined_players:
        await interaction.response.send_message("No players have joined yet!", ephemeral=True)
        return

    if game_state.mr_x_id is None:
        await interaction.response.send_message("Mr. X has not been chosen yet!", ephemeral=True)
        return

    if len(game_state.joined_players) < 2:
        await interaction.response.send_message("Need at least 2 players to start!", ephemeral=True)
        return

    # Initialize player locations
    for player_id in game_state.joined_players:
        game_state.player_locations[player_id] = random.choice(live_map.get_all_nodes())

    game_state.turn_order = game_state.joined_players.copy()
    random.shuffle(game_state.turn_order)

    await interaction.response.send_message("The game has begun! Mr. X, make your first move.")
    await send_map(interaction.channel, interaction, zoom_player=game_state.mr_x_id)

@client.tree.command(name="move", description="Make a move to a new location", guild=GUILD_ID)
@app_commands.describe(destination="Where do you want to move?")
async def move(interaction: discord.Interaction, destination: int):
    if interaction.user.id not in game_state.joined_players:
        await interaction.response.send_message("You haven't joined the game yet!", ephemeral=True)
        return

    if game_state.get_current_player() != interaction.user.id:
        await interaction.response.send_message("It's not your turn!", ephemeral=True)
        return

    current_location = game_state.player_locations.get(interaction.user.id)
    if not current_location:
        await interaction.response.send_message("The game hasn't started yet!", ephemeral=True)
        return

    view = TransportSelectView(interaction.user, destination, interaction)
    await interaction.response.send_message("Choose your transport:", view=view, ephemeral=True)

@client.tree.command(name="status", description="Check your current status in the game", guild=GUILD_ID)
async def status(interaction: Interaction):
    status_message = game_state.get_player_status(interaction.user.id)
    await interaction.response.send_message(status_message, ephemeral=True)

@client.tree.command(name="endgame", description="End the current game and reset", guild=GUILD_ID)
async def endgame(interaction: discord.Interaction):
    if not game_state.joined_players:
        await interaction.response.send_message("No game is in progress!", ephemeral=True)
        return

    game_state.reset()
    await interaction.response.send_message("The game has been ended and reset.")

@client.tree.command(name="moves", description="Show possible moves and tickets from your current location", guild=GUILD_ID)
async def moves(interaction: discord.Interaction):
    if interaction.user.id not in game_state.joined_players:
        await interaction.response.send_message("You haven't joined the game yet!", ephemeral=True)
        return

    current_location = game_state.player_locations.get(interaction.user.id)
    if not current_location:
        await interaction.response.send_message("The game hasn't started yet!", ephemeral=True)
        return

    connected_nodes = live_map.get_connected_nodes(current_location)
    available_moves = []
    
    for dest in connected_nodes:
        transports = game_state.get_available_transports(interaction.user.id, current_location, dest)
        if transports:
            available_moves.append(f"Location {dest}: {', '.join(transports)}")

    if not available_moves:
        await interaction.response.send_message("No valid moves available from your current location!", ephemeral=True)
        return

    message = "Available moves:\n" + "\n".join(available_moves)
    await interaction.response.send_message(message, ephemeral=True)

@client.tree.command(name="help", description="Show all commands and game rules", guild=GUILD_ID)
async def help(interaction: discord.Interaction):
    help_message = """
**Game Commands:**
- `/startgame` - Start a new game
- `/join` - Join the current game
- `/begin` - Begin the game after players have joined
- `/move <destination>` - Make a move to a new location
- `/map` - Display the current game map
- `/status` - Check your current status
- `/moves` - Show possible moves from your location
- `/endgame` - End the current game

**Game Rules:**
1. One player is Mr. X, others are Detectives
2. Mr. X moves secretly, revealing their location every 5 rounds
3. Detectives must catch Mr. X before the game ends
4. Each player has limited tickets for different transport types
5. Mr. X wins if they survive all rounds or if a detective is trapped
    """
    await interaction.response.send_message(help_message, ephemeral=True)

@client.command()
@commands.has_permissions(administrator=True)
async def sync(ctx):
    try:
        synced = await client.tree.sync(guild=GUILD_ID)
        await ctx.send(f"Synced {len(synced)} command(s)")
    except Exception as e:
        await ctx.send(f"Failed to sync commands: {e}")

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')
    try:
        synced = await client.tree.sync(guild=GUILD_ID)
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(e)

client.run(TOKEN) 