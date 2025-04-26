import discord
import random
from discord.ext import commands
from discord import app_commands, Interaction
from discord.ui import Button, View
from collections import defaultdict, deque
import live_map
import os

# ---------- CONFIGURATION ----------
GUILD_ID = discord.Object(id=1358853180179611888)

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.members = True

client = commands.Bot(command_prefix="/", intents=intents)

# ---------- GAME STATE ----------
joined_players = []
roles = {}
turn_order = []
current_turn_index = 0
mr_x_ticket_log = deque(maxlen=5)
mr_x_move_history = []
round_counter = 1
mr_x_id = None  # Cache Mr. X's ID

MAX_ROUNDS = 24
MAX_PLAYERS = 5

ticket_limits = {"taxi": 10, "bus": 8, "metro": 4}
black_ticket_limit = 5

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# ---------- HELPERS ----------
def reset_game_state():
    """Fully reset all global game state variables."""
    global joined_players, roles, turn_order, current_turn_index, mr_x_ticket_log
    global mr_x_move_history, round_counter, mr_x_id
    joined_players = []
    roles = {}
    turn_order = []
    current_turn_index = 0
    mr_x_ticket_log = deque(maxlen=5)
    mr_x_move_history = []
    round_counter = 1
    mr_x_id = None
    print("[reset_game_state] Cleared turn_order and all game state")

def load_map_from_file(filename):
    conn_map = defaultdict(list)
    full_path = os.path.join(BASE_DIR, filename)
    try:
        with open(full_path, "r") as f:
            for line in f:
                a, b = map(int, line.strip().split(","))
                conn_map[a].append(b)
                conn_map[b].append(a)
        print(f"[load_map_from_file] Loaded map from {full_path}")
        return conn_map
    except FileNotFoundError:
        print(f"[load_map_from_file] Error: File not found at {full_path}")
        return conn_map

taxi_map = load_map_from_file("taxi_map.txt")
bus_map = load_map_from_file("bus_map.txt")
metro_map = load_map_from_file("metro_map.txt")

def get_available_transports(user_id, current, dest):
    if user_id not in roles:
        print(f"[get_available_transports] User {user_id} not in roles")
        return []
    info = roles[user_id]
    options = []
    if dest in taxi_map[current] and info["tickets"].get("taxi", 0) > 0:
        options.append("Taxi")
    if dest in bus_map[current] and info["tickets"].get("bus", 0) > 0:
        options.append("Bus")
    if dest in metro_map[current] and info["tickets"].get("metro", 0) > 0:
        options.append("Metro")
    if info.get("role") == "Mr. X" and info.get("black_tickets", 0) > 0 and options:
        options.append("Black")
    print(f"[get_available_transports] User {user_id}, current={current}, dest={dest}, options={options}")
    return options

def get_current_player():
    global turn_order, current_turn_index
    if not turn_order or len(turn_order) == 0:
        print(f"[get_current_player] No players in turn_order")
        return None
    if current_turn_index >= len(turn_order):
        print(f"[get_current_player] Resetting current_turn_index from {current_turn_index} to 0")
        current_turn_index = 0
    player_id = turn_order[current_turn_index]
    player_role = roles.get(player_id, {}).get("role", "Unknown")
    print(f"[get_current_player] player_id={player_id}, role={player_role}, turn_order={turn_order}, current_turn_index={current_turn_index}")
    return player_id

def advance_turn():
    global current_turn_index, round_counter, turn_order
    if not turn_order or len(turn_order) == 0:
        print(f"[advance_turn] No players in turn_order")
        return None, False
    
    mr_x_count = sum(1 for pid in turn_order if roles.get(pid, {}).get("role") == "Mr. X")
    if mr_x_count != 1:
        print(f"[advance_turn] Invalid turn_order, mr_x_count={mr_x_count}, turn_order={turn_order}, roles={roles}")
        return None, False
    
    current_turn_index = (current_turn_index + 1) % len(turn_order)
    new_round = (current_turn_index == 0)
    if new_round:
        round_counter += 1

    next_player_id = turn_order[current_turn_index]
    next_role = roles.get(next_player_id, {}).get("role", "Unknown")
    
    # Ensure Mr. X is first in a new round
    if new_round and next_role != "Mr. X" and mr_x_id:
        print(f"[advance_turn] Warning: Expected Mr. X at round start, got {next_role} ({next_player_id}). Correcting to Mr. X {mr_x_id}")
        next_player_id = mr_x_id
        current_turn_index = turn_order.index(mr_x_id)
        next_role = "Mr. X"
    
    print(f"[advance_turn] next_player_id={next_player_id}, role={next_role}, round={round_counter}, new_round={new_round}, turn_order={turn_order}, current_turn_index={current_turn_index}")
    return next_player_id, new_round

def check_end_conditions(channel):
    global mr_x_id
    if not mr_x_id:
        print(f"[check_end_conditions] No Mr. X found, roles={roles}")
        return "❌ No Mr. X found. Game cannot continue."
    mr_x_location = roles[mr_x_id]["location"]
    detective_locations = [info["location"] for uid, info in roles.items() if info["role"] == "Detective"]
    
    print(f"[check_end_conditions] mr_x_id={mr_x_id}, mr_x_location={mr_x_location}, detective_locations={detective_locations}, round={round_counter}")
    
    if mr_x_location in detective_locations:
        print(f"[check_end_conditions] Mr. X caught at {mr_x_location}")
        return f"🕵️ Mr. X has been caught at location {mr_x_location}! Detectives win!"

    stuck_detectives = 0
    for uid, info in roles.items():
        if info["role"] == "Detective":
            current = info["location"]
            possible = False
            for dest in range(1, 201):
                if get_available_transports(uid, current, dest):
                    possible = True
                    break
            if not possible:
                stuck_detectives += 1
    if stuck_detectives == len([r for r in roles.values() if r["role"] == "Detective"]):
        print(f"[check_end_conditions] All detectives stuck, count={stuck_detectives}")
        return "🕶️ All detectives are stuck! Mr. X escapes and wins!"

    if round_counter > MAX_ROUNDS:
        print(f"[check_end_conditions] Max rounds ({MAX_ROUNDS}) exceeded")
        return "⏳ 24 rounds are over. Mr. X wins!"

    return None

async def send_map(channel, interaction=None, zoom_player=None, is_turn=False):
    try:
        buffer = live_map.generate_map(roles, round_counter, zoom_player=zoom_player, mr_x_id=mr_x_id)
        if buffer is None:
            raise Exception("Failed to generate map")
        player_role = roles.get(zoom_player, {}).get("role", "Unknown") if zoom_player else "None"

        if zoom_player and is_turn:
            player_location = roles.get(zoom_player, {}).get("location", "Unknown")
            player = await channel.guild.fetch_member(zoom_player)

            if player_role == "Detective":
                print(f"[send_map] Sending public map to Detective {zoom_player} at location {player_location}")
                await channel.send(
                    content=f"🔎 {player.mention}'s current location is {player_location} (Round {round_counter}):",
                    file=discord.File(buffer, 'zoom_map.png')
                )
            elif player_role == "Mr. X":
                print(f"[send_map] Sending private map to Mr. X {zoom_player} at location {player_location}")
                # Prefer direct DM to ensure correct recipient
                try:
                    await player.send(
                        content=f"🕶 Your current location {player_location} (Round {round_counter}):",
                        file=discord.File(buffer, 'zoom_map.png'),
                        embed=create_mr_x_notepad_embed()
                    )
                    await channel.send(f"🕶 Map sent to Mr. X privately.")
                except discord.Forbidden:
                    print(f"[send_map] Failed to send DM to Mr. X {zoom_player}: Forbidden")
                    if interaction:
                        await interaction.followup.send(
                            content="❌ Unable to send map to Mr. X via DM. Please enable DMs.",
                            ephemeral=True
                        )
                    else:
                        await channel.send("❌ Unable to send map to Mr. X via DM. Please enable DMs.")
            else:
                print(f"[send_map] Invalid role for player {zoom_player}: {player_role}")
                if interaction:
                    await interaction.followup.send(f"⚠️ Invalid role for player <@{zoom_player}>. Map not sent.", ephemeral=True)
                else:
                    await channel.send(f"⚠️ Invalid role for player <@{zoom_player}>. Map not sent.")
        else:
            print(f"[send_map] Sending general map for Round {round_counter}")
            await channel.send(file=discord.File(buffer, 'map.png'))

    except Exception as e:
        print(f"[send_map] Error: {type(e).__name__}: {e}")
        if interaction:
            try:
                await interaction.followup.send("Error generating map. Please check bot configuration.", ephemeral=True)
            except:
                await channel.send("Error generating map. Please check bot configuration.")
        else:
            await channel.send("Error generating map. Please check bot configuration.")

# ---------- VIEWS ----------
class TransportSelectView(View):
    def __init__(self, user: discord.User, dest: int, interaction: Interaction):
        super().__init__(timeout=90.0)
        self.user, self.dest, self.interaction = user, dest, interaction
        for t in get_available_transports(user.id, roles[user.id]["location"], dest):
            self.add_item(self.TransportButton(t, user, dest, interaction, self))

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        try:
            await self.interaction.edit_original_response(view=self)
        except Exception:
            pass

    class TransportButton(Button):
        def __init__(self, transport, user, dest, interaction, parent):
            style = discord.ButtonStyle.danger if transport == "Black" else discord.ButtonStyle.primary
            emoji = {"Taxi": "🚕", "Bus": "🚌", "Metro": "🚇", "Black": "❓"}[transport]
            super().__init__(label=transport, style=style, emoji=emoji)
            self.transport, self.user, self.dest = transport, user, dest
            self.interaction, self.parent = interaction, parent

        async def callback(self, interaction: discord.Interaction):
            if interaction.user != self.user:
                await interaction.response.send_message("Not for you!", ephemeral=True)
                return
            
            info = roles[self.user.id]
            Role = info["role"]
            start_location = info["location"]
            print(f"[TransportSelectView.callback] Current player={self.user.id}, role={Role}, moving from {start_location} to {self.dest} via {self.transport}")

            if Role == "Detective":
                info["tickets"][self.transport.lower()] -= 1
            else:
                if self.transport == "Black":
                    info["black_tickets"] -= 1
                mr_x_ticket_log.append(self.transport)
                mr_x_move_history.append((self.transport, start_location, self.dest))

            info["location"] = self.dest
            live_map.update_player_location(self.user.id, self.dest, roles)
            
            if Role == "Detective":
                await interaction.response.edit_message(
                    content=f"🕵 {self.user.mention} moved to {self.dest} via {self.transport}", view=None)
                await self.interaction.channel.send(f"🕵️ {self.user.mention} moved to location **{self.dest}** using **{self.transport}** ticket")
            elif Role == "Mr. X":
                await interaction.response.edit_message(content="✅ Move recorded.", view=None)
                await self.interaction.channel.send(f"🕶 Mr. X has moved using {self.transport} ticket.")
            
            res = check_end_conditions(self.interaction.channel)
            if res:
                print(f"[TransportSelectView.callback] Game ended: {res}")
                await self.interaction.channel.send(res)
                reset_game_state()
                self.parent.stop()
                return
            
            nxt, new_round = advance_turn()
            if not nxt:
                print(f"[TransportSelectView.callback] No valid next player, roles={roles}, turn_order={turn_order}")
                await self.interaction.channel.send("❌ No valid next player. Game stopped. Use `/endgame` to reset.")
                reset_game_state()
                self.parent.stop()
                return

            if new_round:
                print(f"[TransportSelectView.callback] New round started: {round_counter}")
                await self.interaction.channel.send(f"Round {round_counter} has started!")
                if round_counter in [3, 8, 13, 18, 24] and mr_x_id:
                    mr_x_location = roles[mr_x_id]["location"]
                    await self.interaction.channel.send(f"📍 Mr. X location: *{mr_x_location}*")
                    await send_map(self.interaction.channel, interaction=interaction)
                else:
                    await send_map(self.interaction.channel, interaction=interaction)

            try:
                member = await self.interaction.guild.fetch_member(nxt)
                await self.interaction.channel.send(f"🔁 It's {member.mention}'s turn! Use `/move <destination>` to make your move. (Round {round_counter})")
                print(f"[TransportSelectView.callback] Next player={nxt}, role={roles.get(nxt, {}).get('role', 'Unknown')}, mr_x_id={mr_x_id}, turn_order={turn_order}, current_turn_index={current_turn_index}")
                
                # Set zoom_player based on nxt matching mr_x_id
                zoom_player = mr_x_id if nxt == mr_x_id else nxt
                print(f"[TransportSelectView.callback] Setting zoom_player to {'Mr. X' if nxt == mr_x_id else 'Detective'} {zoom_player}")
                await send_map(self.interaction.channel, interaction=interaction, zoom_player=zoom_player, is_turn=True)
            except discord.errors.NotFound:
                print(f"[TransportSelectView.callback] Player {nxt} not found")
                await self.interaction.channel.send(f"❌ Player <@{nxt}> not found. Skipping their turn.")
                
                nxt, new_round = advance_turn()
                if not nxt:
                    print(f"[TransportSelectView.callback] No valid next player after skip, roles={roles}, turn_order={turn_order}")
                    await self.interaction.channel.send("❌ No valid next player. Game stopped. Use `/endgame` to reset.")
                    reset_game_state()
                    self.parent.stop()
                    return
                if new_round:
                    print(f"[TransportSelectView.callback] New round started after skip: {round_counter}")
                    await self.interaction.channel.send(f"Round {round_counter} has started!")
                    if round_counter in [3, 8, 13, 18, 24] and mr_x_id:
                        mr_x_location = roles[mr_x_id]["location"]
                        await self.interaction.channel.send(f"📍 Mr. X location: *{mr_x_location}*")
                        await send_map(self.interaction.channel, interaction=interaction)
                    else:
                        await send_map(self.interaction.channel, interaction=interaction)

                try:
                    member = await self.interaction.guild.fetch_member(nxt)
                    embed = discord.Embed(
                        title="🔁 It's Your Turn!",
                        description=f"{member.mention}, use /move <destination> to make your move. (Round {round_counter})",
                        color=discord.Color.blue()  
                    )
                    embed.set_footer(text="Make your move!")  
                    await self.interaction.channel.send(embed=embed)

                    print(f"[TransportSelectView.callback] Next player after skip={nxt}, role={roles.get(nxt, {}).get('role', 'Unknown')}, mr_x_id={mr_x_id}, turn_order={turn_order}, current_turn_index={current_turn_index}")
                    zoom_player = mr_x_id if nxt == mr_x_id else nxt
                    print(f"[TransportSelectView.callback] Setting zoom_player to {'Mr. X' if nxt == mr_x_id else 'Detective'} {zoom_player} after skip")
                    await send_map(self.interaction.channel, interaction=interaction, zoom_player=zoom_player, is_turn=True)
                except discord.errors.NotFound:
                    print(f"[TransportSelectView.callback] Next player not found after second skip")
                    await self.interaction.channel.send("❌ Next player not found. Game may need to be reset with `/endgame`.")
                    reset_game_state()
                    self.parent.stop()
                    return

            self.parent.stop()

class RoleSelectView(View):
    def __init__(self, user):
        super().__init__(timeout=60)
        self.user = user
        self.message = None

    async def on_timeout(self):
        try:
            for item in self.children:
                item.disabled = True
            if self.message:
                await self.message.edit(view=self)
        except Exception as e:
            print(f"[RoleSelectView.on_timeout] Error: {e}")

    @discord.ui.button(label="🕵 Detective", style=discord.ButtonStyle.primary)
    async def detect(self, interaction: Interaction, button: Button):
        try:
            if interaction.user != self.user:
                await interaction.response.send_message("Not for you!", ephemeral=True)
                return

            if interaction.user.id in roles and roles[interaction.user.id]["role"]:
                await interaction.response.send_message("Role already chosen.", ephemeral=True)
                return

            if sum(r.get('role') == 'Detective' for r in roles.values()) >= MAX_PLAYERS - 1:
                await interaction.response.send_message("Detective slots full.", ephemeral=True)
                return

            roles[interaction.user.id] = {
                "role": "Detective",
                "location": None,
                "tickets": ticket_limits.copy()
            }
            print(f"[RoleSelectView.detect] User {interaction.user.id} chose Detective, roles={roles}")
            await interaction.response.edit_message(content="✅ You are Detective", view=None)
            await interaction.channel.send(f"🕵 {interaction.user.mention} has chosen **Detective**!")
        except Exception as e:
            print(f"[RoleSelectView.detect] Error: {e}")
            try:
                await interaction.response.send_message("Error selecting role.", ephemeral=True)
            except:
                pass

    @discord.ui.button(label="🕶 Mr. X", style=discord.ButtonStyle.danger)
    async def mr_x(self, interaction: Interaction, button: Button):
        try:
            if interaction.user != self.user:
                await interaction.response.send_message("Not for you!", ephemeral=True)
                return

            if interaction.user.id in roles and roles[interaction.user.id]["role"]:
                await interaction.response.send_message("Role already chosen.", ephemeral=True)
                return

            if any(r.get('role') == 'Mr. X' for r in roles.values()):
                await interaction.response.send_message("Mr. X already taken.", ephemeral=True)
                return

            roles[interaction.user.id] = {
                "role": "Mr. X",
                "location": None,
                "tickets": {"taxi": 999, "bus": 999, "metro": 999},
                "black_tickets": black_ticket_limit
            }
            print(f"[RoleSelectView.mr_x] User {interaction.user.id} chose Mr. X, roles={roles}")
            await interaction.response.edit_message(content="✅ You are Mr. X", view=None)
            await interaction.channel.send(f"🕶 {interaction.user.mention} has chosen **Mr. X**!")
        except Exception as e:
            print(f"[RoleSelectView.mr_x] Error: {e}")
            try:
                await interaction.response.send_message("Error selecting role.", ephemeral=True)
            except:
                pass

async def send_role_selection(user, channel):
    try:
        view = RoleSelectView(user)
        embed = discord.Embed(
            title="🎭 Choose Your Role",
            description="Click to become Mr. X or Detective.",
            color=discord.Color.gold()
        )
        message = await channel.send(content=user.mention, embed=embed, view=view)
        view.message = message
        print(f"[send_role_selection] Sent role selection for user {user.id}")
    except Exception as e:
        print(f"[send_role_selection] Error: {e}")
        try:
            await channel.send("Failed to send role selection. Please try again.")
        except:
            pass

def create_mr_x_notepad_embed():
    embed = discord.Embed(
        title="🕶️ Mr. X's Notepad",
        description="Your secret move history:",
        color=discord.Color.dark_red()
    )
    if not mr_x_move_history:
        embed.add_field(name="Moves", value="No moves yet.", inline=False)
    else:
        for i, (ticket, start_node, end_node) in enumerate(mr_x_move_history, 1):
            ticket_emoji = {"Taxi": "🚕", "Bus": "🚌", "Metro": "🚇", "Black": "❓"}.get(ticket, ticket)
            embed.add_field(
                name=f"Move {i}",
                value=f"{ticket_emoji} {ticket}: {start_node} → {end_node}",
                inline=False
            )
    print(f"create_mr_x_notepad_embed() Generated notepad, move_history={mr_x_move_history}")
    return embed

# ---------- COMMANDS ----------
@client.tree.command(name="startgame", description="Start a new game", guild=GUILD_ID)
async def startgame(interaction: discord.Interaction):
    try:
        reset_game_state()
        roles[interaction.user.id] = {"role": None, "location": None, "tickets": {}, "black_tickets": 0}

        embed = discord.Embed(
        title="🎩 Scotland Yard",
        description="🕵‍♂ **Mr. X vs Detectives",
        color=discord.Color.dark_blue()
        )

        embed.add_field(
        name="🧭 /join",
        value="Join the ongoing game lobby as either *Mr. X* or a *Detective*. First come, first served!",
        inline=False
        )

        embed.add_field(
        name="🎮 /begin",
        value="Start the game once the required number of players have joined. Mr. X receives their role in secret via DM, while detectives work together in the open.",
        inline=False
        )

        embed.add_field(
        name="📜 /help",
        value="Get detailed instructions on how to play, including roles, movement, turns, transport types, and win conditions.",
        inline=False
        )
        
        image_path = os.path.join(BASE_DIR, "startgame_image.png")
        
        
        if not os.path.exists(image_path):
            print(f"[startgame] Image file not found at {image_path}")
            await interaction.response.send_message("Error: Start game image not found.", ephemeral=True)
            return
        
        file = discord.File(image_path, filename="startgame_image.png")
        embed.set_image(url="attachment://startgame_image.png")
        
        print(f"[startgame] Started game by {interaction.user.id}, roles={roles}")
    
        await interaction.response.send_message(embed=embed, file=file)
    except Exception as e:
        print(f"[startgame] Error: {type(e).__name__}: {e}")
        try:
            await interaction.response.send_message("Failed to start game. Please try again.", ephemeral=True)
        except:
            pass

@client.tree.command(name="join", description="Join the game", guild=GUILD_ID)
async def join(interaction: discord.Interaction):
    try:
        user = interaction.user
        if len(joined_players) >= MAX_PLAYERS:
            await interaction.response.send_message("Game is full!", ephemeral=True)
            return
        if user in joined_players:
            await interaction.response.send_message("You've already joined!", ephemeral=True)
            return
        
        joined_players.append(user)
        roles[user.id] = {"role": None, "location": None, "tickets": {}, "black_tickets": 0}
        print(f"[join] User {user.id} joined, joined_players={len(joined_players)}, roles={roles}")
        await interaction.response.send_message(f"👤 {user.mention} joined!")
        await send_role_selection(user, interaction.channel)
    except Exception as e:
        print(f"[join] Error: {e}")
        try:
            await interaction.response.send_message("An error occurred while processing your request.")
        except:
            pass

@client.tree.command(name="map", description="Display the current game map", guild=GUILD_ID)
async def map(interaction: discord.Interaction):
    try:
        await interaction.response.defer()
        if not roles:
            print(f"[map] No game in progress, roles={roles}")
            await interaction.followup.send("No game in progress.", ephemeral=True)
            return
        buffer = live_map.generate_map(roles, round_counter)
        print(f"[map] Generated map for round {round_counter}")
        await send_map(interaction.channel, interaction=interaction, zoom_player=None, is_turn=False)
        # await interaction.followup.send(file=discord.File(buffer, 'map.png'))
    except Exception as e:
        print(f"[map] Error: {type(e).__name__}: {e}")
        if not interaction.response.is_done():
            await interaction.response.send_message("Error generating map. Please check bot configuration.", ephemeral=True)
        else:
            await interaction.followup.send("Error generating map. Please check bot configuration.", ephemeral=True)

@client.tree.command(name="begin", description="Begin the game", guild=GUILD_ID)
async def begin(interaction: discord.Interaction):
    try:
        await interaction.response.defer()
        global turn_order, current_turn_index, mr_x_id

        mr_x_count = sum(1 for r in roles.values() if r["role"] == "Mr. X")
        detective_count = sum(1 for r in roles.values() if r["role"] == "Detective")
        
        if mr_x_count != 1 or detective_count < 1 or (mr_x_count + detective_count) != len(joined_players):
            print(f"[begin] Invalid roles: mr_x_count={mr_x_count}, detective_count={detective_count}, joined_players={len(joined_players)}, roles={roles}")
            await interaction.followup.send("❌ Need exactly 1 Mr. X and at least 1 Detective to start!", ephemeral=True)
            return

        for user_id in roles:
            roles[user_id]["location"] = random.randint(1, 200)

        mr_x_id = next((uid for uid, r in roles.items() if r["role"] == "Mr. X"), None)
        if not mr_x_id:
            print(f"[begin] No Mr. X found, roles={roles}")
            await interaction.followup.send("❌ No Mr. X found. Please reset the game and try again.", ephemeral=True)
            return
        
        turn_order = [mr_x_id] + [uid for uid, r in roles.items() if r["role"] == "Detective"]
        current_turn_index = 0
        print(f"[begin] Initialized game: turn_order={turn_order}, current_turn_index={current_turn_index}, mr_x_id={mr_x_id}, roles={roles}")

        detectives = [f"<@{uid}> → *Detective* at location {roles[uid]['location']}"
                      for uid in turn_order if roles[uid]["role"] == "Detective"]
        embed = discord.Embed(
            title="✅ Game Started!",
            description="*Final Teams:*\n" + "\n".join(detectives),
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed)

        await send_map(interaction.channel, interaction = interaction)

        try:
            mr_x = await interaction.guild.fetch_member(mr_x_id)
            mr_x_location = roles[mr_x_id]["location"]
            buffer = live_map.generate_map(roles, round_counter, zoom_player=mr_x_id,mr_x_id=mr_x_id)
            print(f"[begin] Sending initial private map to Mr. X {mr_x_id} at location {mr_x_location}")
            await mr_x.send(
                content=f"🔒 Your secret starting location is **{mr_x_location}** (Round {round_counter}):",
                file=discord.File(buffer, 'zoom_map.png'),
                embed=create_mr_x_notepad_embed()
            )
            await interaction.channel.send(f"🕶 Map sent to Mr. X privately.")
        except discord.Forbidden:
            print(f"[begin] Failed to send DM to Mr. X {mr_x_id}: Forbidden")
            await interaction.followup.send("❌ Couldn't send Mr. X their location. Please enable DMs.", ephemeral=True)
            return

        await interaction.followup.send(f"🎲 It's {mr_x.mention}'s turn! Use `/move <destination>` to make your move. (Round {round_counter})")

    except Exception as e:
        print(f"[begin] Error: {e}")
        try:
            await interaction.followup.send("Failed to begin game. Please try again.", ephemeral=True)
        except:
            pass

@client.tree.command(name="move", description="Make a move to a new location", guild=GUILD_ID)
@app_commands.describe(destination="Where do you want to move?")
async def move(interaction: discord.Interaction, destination: int):
    try:
        user = interaction.user
        current_player_id = get_current_player()
        print(f"[move] User {user.id} attempting move to {destination}, current_player_id={current_player_id}, turn_order={turn_order}, current_turn_index={current_turn_index}")

        if user.id != current_player_id:
            print(f"[move] Not user's turn: user_id={user.id}, current_player_id={current_player_id}")
            await interaction.response.send_message("❌ It's not your turn!", ephemeral=True)
            return

        if user.id not in roles or not roles[user.id]["role"]:
            print(f"[move] User {user.id} not in game or no role, roles={roles}")
            await interaction.response.send_message("You're not in the game.", ephemeral=True)
            return
        
        if destination < 1 or destination > 200:
            print(f"[move] Invalid destination: {destination}")
            await interaction.response.send_message("Invalid destination!", ephemeral=True)
            return

        current = roles[user.id]["location"]
        available = get_available_transports(user.id, current, destination)
        if not available:
            print(f"[move] No available transports for user {user.id} from {current} to {destination}")
            await interaction.response.send_message("You can't move there with any available transport.", ephemeral=True)
            return

        view = TransportSelectView(user, destination, interaction)
        print(f"[move] Presenting transport options for user {user.id} to {destination}")
        await interaction.response.send_message(
            f"Choose how to move to *{destination}*:",
            view=view,
            ephemeral=(roles[user.id]["role"] == "Mr. X")
        )
    except Exception as e:
        print(f"[move] Error: {e}")
        await interaction.response.send_message("Error processing move. Please try again.", ephemeral=True)

@client.tree.command(name="status", description="Check your current status in the game", guild=GUILD_ID)
async def status(interaction: Interaction):
    try:
        user = interaction.user

        if user.id not in roles or not roles[user.id]["role"]:
            print(f"[status] User {user.id} not in game or no role, roles={roles}")
            await interaction.response.send_message("You're not in the game.", ephemeral=True)
            return

        role_info = roles[user.id]
        role = role_info["role"]
        location = role_info["location"]
        tickets = role_info.get("tickets", {})
        black_tickets = role_info.get("black_tickets", 0)

        ticket_info = "\n".join([f"{ticket.capitalize()}: {count}" for ticket, count in tickets.items()])
        status_message = f"**{user.name}'s Status**:\n"
        status_message += f"**Role: {role}**\n"
        status_message += f"**Location**: {location if location else 'Unknown'}\n"
        if role == "Mr. X":
            status_message += f"**Black Tickets**: {black_tickets}"
        else:
            status_message += f"**Tickets**:\n{ticket_info}\n"
        print(f"[status] User {user.id} status: role={role}, location={location}, tickets={tickets}, black_tickets={black_tickets}")
        await interaction.response.send_message(status_message, ephemeral=True)
    except Exception as e:
        print(f"[status] Error: {e}")
        await interaction.response.send_message("Error fetching status. Please try again.", ephemeral=True)

@client.tree.command(name="endgame", description="End the current game and reset", guild=GUILD_ID)
async def endgame(interaction: discord.Interaction):
    try:
        if not roles:
            print(f"[endgame] No game in progress, roles={roles}")
            await interaction.response.send_message("No game in progress.", ephemeral=True)
            return

        reset_game_state()
        print(f"[endgame] Game ended and state reset")
        
        # Create embed for game ended message
        embed = discord.Embed(
            title="🛑 Game Ended",
            description="The current game has been terminated. Start a new game with /startgame.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=False)
        
    except Exception as e:
        print(f"[endgame] Error: {e}")
        await interaction.response.send_message("Error ending game. Please try again.",ephemeral=True)

@client.tree.command(name="moves", description="Show possible moves and tickets from your current location", guild=GUILD_ID)
async def moves(interaction: discord.Interaction):
    try:
        await interaction.response.defer(ephemeral=True)
        user_id = interaction.user.id

        if not roles or user_id not in roles:
            print(f"[moves] User {user_id} not in game, roles={roles}")
            await interaction.followup.send("You are not in the game. Join with `/join`.", ephemeral=True)
            return

        role_info = roles[user_id]
        current_location = role_info.get("location")
        role = role_info.get("role")

        if not current_location or not role:
            print(f"[moves] Invalid role or location for user {user_id}: role={role}, location={current_location}")
            await interaction.followup.send("Your location or role is not set. Start the game with `/begin`.", ephemeral=True)
            return

        if role == "Mr. X":
            print(f"[moves] User {user_id} is Mr. X, command restricted")
            await interaction.followup.send("This command is for detectives only.", ephemeral=True)
            return

        possible_moves = live_map.get_possible_moves(current_location, roles, is_mr_x=False)
        if "error" in possible_moves:
            print(f"[moves] Error for user {user_id}: {possible_moves['error']}")
            await interaction.followup.send(possible_moves["error"], ephemeral=True)
            return

        embed = discord.Embed(
            title=f"Possible Moves from Station {current_location}",
            description="Here are the stations you can move to and the required tickets:",
            color=discord.Color.blue()
        )

        moves_list = []
        for dest, tickets in sorted(possible_moves.items()):
            tickets_str = ", ".join(tickets)
            moves_list.append(f"Station **{dest}**: {tickets_str}")
        if not moves_list:
            embed.add_field(name="No Moves Available", value="All possible destinations are occupied or invalid.", inline=False)
        else:
            embed.add_field(name="Destinations", value="\n".join(moves_list), inline=False)

       
        await interaction.followup.send(embed=embed, ephemeral=False)  # Public for detectives
        print(f"[moves] Sent public moves for detective {user_id} (role={role}, location={current_location}): {possible_moves}")

    except Exception as e:
        print(f"[moves] Error: {type(e).__name__}: {e}")
        await interaction.followup.send("Error calculating possible moves. Please check bot configuration.", ephemeral=True)

@client.tree.command(name="help", description="Show all commands and game rules", guild=GUILD_ID)
async def help(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🕵 Scotland Yard Bot Help",
        description="A detective chase game where players work together to catch Mr. X!",
        color=discord.Color.blurple()
    )
    
    # Command List
    embed.add_field(
        name="🔹 Game Commands",
        value="""
        /startgame - Start a new game
        /join - Join the current game
        /begin - Start the game after players join
        /move <location> - Move to a numbered location (1-200)
        /status - Check your location and tickets
        /moves - List of all possible moves detective can make
        /endgame - Force stop the current game
        """,
        inline=False
    )
    
    # Game Rules
    embed.add_field(
        name="🔹 How to Play",
        value="""
        • 1 Mr. X vs <=4 Detectives
        • Mr. X moves secretly, Detectives move openly
        • Use tickets: 🚕 Taxi (11), 🚌 Bus (8), 🚇 Metro (5)
        • Mr. X's location is revealed on rounds 3, 8, 13, 18, 24
        • Detectives win if they land on Mr. X's location
        • Mr. X wins if he survives 24 rounds or detectives get stuck
        """,
        inline=False
    )
    
    # Transport Key
    embed.add_field(
        name="🔹 Transport Types",
        value="""
        🚕 Taxi: Short distances
        🚌 Bus: Medium distances
        🚇 Metro: Long distances
        ❓ Black Ticket: Mr. X only (mimics any transport)
        """,
        inline=False
    )
    await interaction.response.send_message(embed=embed,ephemeral=True)
                                            
@client.command()
@commands.has_permissions(administrator=True)
async def sync(ctx):
    try:
        synced = await ctx.bot.tree.sync(guild=GUILD_ID)
        print(f"[sync] Synced {len(synced)} commands")
        await ctx.send(f"✅ Synced {len(synced)} commands to the current guild.")
    except Exception as e:
        print(f"[sync] Error: {e}")
        await ctx.send(f"❌ Failed to sync commands: {e}")

@client.event
async def on_ready():
    print(f"[on_ready] Logged in as {client.user}")
    try:
        synced = await client.tree.sync(guild=GUILD_ID)
        print(f"[on_ready] Synced commands ({len(synced)}): {[cmd.name for cmd in synced]}")
    except Exception as e:
        print(f"[on_ready] Error syncing commands: {e}")

client.run("TOKEN")
