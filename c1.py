import asyncio
import discord
import random
from discord.ext import commands
from discord import app_commands, Interaction
from discord.ui import Button, View
from collections import defaultdict, deque
import live_map 

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

def load_map_from_file(filename):
    conn_map = defaultdict(list)
    with open(filename, "r") as f:
        for line in f:
            a, b = map(int, line.strip().split(","))
            conn_map[a].append(b)
            conn_map[b].append(a)
    return conn_map


taxi_map = load_map_from_file("taxi_map.txt")
bus_map = load_map_from_file("bus_map.txt")
metro_map = load_map_from_file("metro_map.txt")

def get_available_transports(user_id, current, dest):
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
    return options

def check_end_conditions(channel):
    mr_id = next((uid for uid, info in roles.items() if info.get("role") == "Mr. X"), None)
    if mr_id is None:
        return None
    mr_loc = roles[mr_id]["location"]
    detective_locs = [info["location"] for uid, info in roles.items() if info.get("role") == "Detective"]
    if mr_loc in detective_locs:
        return f"🕵 Mr. X caught at {mr_loc}! Detectives win!"
    detectives = [uid for uid, info in roles.items() if info.get("role") == "Detective"]
    if detectives and all(
            not get_available_transports(uid, roles[uid]["location"], d) for uid in detectives for d in range(1, 201)):
        return "🕶 All detectives stuck! Mr. X escapes and wins!"
    if round_counter > MAX_ROUNDS:
        return "⏳ 24 rounds over. Mr. X wins!"
    return None

class TransportSelectView(View):
    def _init_(self, user, dest, interaction):
        super()._init_(timeout=90)
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
        def _init_(self, transport, user, dest, interaction, parent):
            style = discord.ButtonStyle.danger if transport == "Black" else discord.ButtonStyle.primary
            emoji = {"Taxi": "🚕", "Bus": "🚌", "Metro": "🚇", "Black": "❓"}[transport]
            super()._init_(label=transport, style=style, emoji=emoji)
            self.transport, self.user, self.dest = transport, user, dest
            self.interaction, self.parent = interaction, parent

        async def callback(self, interaction: Interaction):
            if interaction.user != self.user:
                return await interaction.response.send_message("Not for you!", ephemeral=True)
            info = roles[self.user.id]
            if info.get("role") == "Detective":
                info["tickets"][self.transport.lower()] -= 1
            else:
                if self.transport == "Black":
                    info["black_tickets"] -= 1
                mr_x_ticket_log.append(self.transport)
            info["location"] = self.dest
            live_map.update_player_location(self.user.id, self.dest, roles)
            if info.get("role") == "Detective":
                await interaction.response.edit_message(
                    content=f"🕵 {self.user.mention} moved to {self.dest} via {self.transport}", view=None)
            else:
                await interaction.response.edit_message(content="✅ Move recorded.", view=None)
                await interaction.channel.send(f"🕶 Mr. X used {self.transport} ticket.")
            if round_counter in [3, 8, 13, 18, 24] and info.get("role") == "Mr. X":
                await interaction.channel.send(f"📍 Mr. X location: *{self.dest}*")
            res = check_end_conditions(interaction.channel)
            if res:
                await interaction.channel.send(res)
                self.parent.stop()
                return
            # nxt, new_round = advance_turn()
            # if new_round:
            #     await self.interaction.channel.send(f"Round {round_counter} has started!")
            #     # await send_map(self.interaction.channel)
            # member = await interaction.guild.fetch_member(nxt)
            # await interaction.channel.send(f"🔁 It's {member.mention}'s turn! (Round {round_counter})")
            self.parent.stop()


class RoleSelectView(View):
    def _init_(self, user):
        super()._init_(timeout=60)
        self.user = user
        self.message = None

    async def on_timeout(self):
        try:
            for item in self.children:
                item.disabled = True
            if self.message:
                await self.message.edit(view=self)
        except Exception as e:
            print(f"Error in RoleSelectView timeout: {e}")

    @discord.ui.button(label="🕵 Detective", style=discord.ButtonStyle.primary)
    async def detect(self, interaction: Interaction, button: Button):
        try:
            if interaction.user != self.user:
                await interaction.response.send_message("Not for you!", ephemeral=True)
                return

            if interaction.user.id in roles:
                await interaction.response.send_message("Role already chosen.", ephemeral=True)
                return

            if sum(r.get('role') == 'Detective' for r in roles.values()) >= MAX_PLAYERS - 1:
                await interaction.response.send_message("Detective slots full.", ephemeral=True)
                return

            roles[interaction.user.id] = {
                'role': 'Detective',
                'location': None,
                'tickets': ticket_limits.copy()
            }
            await interaction.response.edit_message(content="✅ You are Detective", view=None)

        except Exception as e:
            print(f"Error in detective selection: {e}")
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

            if interaction.user.id in roles:
                await interaction.response.send_message("Role already chosen.", ephemeral=True)
                return

            if any(r.get('role') == 'Mr. X' for r in roles.values()):
                await interaction.response.send_message("Mr. X already taken.", ephemeral=True)
                return

            roles[interaction.user.id] = {
                'role': 'Mr. X',
                'location': None,
                'tickets': {'taxi': 999, 'bus': 999, 'metro': 999},
                'black_tickets': black_ticket_limit
            }
            await interaction.response.edit_message(content="✅ You are Mr. X", view=None)

        except Exception as e:
            print(f"Error in Mr. X selection: {e}")
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
    except Exception as e:
        print(f"Error in send_role_selection: {e}")
        try:
            await channel.send("Failed to send role selection. Please try again.")
        except:
            pass

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
