from collections import defaultdict, deque
import os
import live_map
import discord

class GameState:
    def __init__(self):
        self.joined_players = []
        self.roles = {}
        self.turn_order = []
        self.current_turn_index = 0
        self.mr_x_ticket_log = deque(maxlen=5)
        self.mr_x_move_history = []
        self.round_counter = 1
        self.mr_x_id = None
        self.MAX_ROUNDS = 24
        self.MAX_PLAYERS = 5
        self.ticket_limits = {"taxi": 12, "bus": 8, "metro": 4}
        self.black_ticket_limit = 5
        self.BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        self.player_tickets = defaultdict(lambda: {"taxi": 12, "bus": 8, "metro": 4, "black": 5})
        self.player_locations = {}

    def reset(self):
        """Fully reset all game state variables."""
        self.joined_players = []
        self.roles = {}
        self.turn_order = []
        self.current_turn_index = 0
        self.mr_x_ticket_log = deque(maxlen=5)
        self.mr_x_move_history = []
        self.round_counter = 1
        self.mr_x_id = None
        self.player_tickets = defaultdict(lambda: {"taxi": 12, "bus": 8, "metro": 4, "black": 5})
        self.player_locations = {}

    def load_map_from_file(self, filename):
        """Load map data from a file."""
        file_path = os.path.join(self.BASE_DIR, filename)
        with open(file_path, 'r') as f:
            return f.read()

    def get_available_transports(self, user_id, current, dest):
        """Get available transport options between two locations."""
        available = []
        if user_id == self.mr_x_id:
            # Mr. X can use any transport
            if live_map.is_connected(current, dest, "taxi"):
                available.append("taxi")
            if live_map.is_connected(current, dest, "bus"):
                available.append("bus")
            if live_map.is_connected(current, dest, "metro"):
                available.append("metro")
        else:
            # Detectives can only use available tickets
            if live_map.is_connected(current, dest, "taxi") and self.player_tickets[user_id]["taxi"] > 0:
                available.append("taxi")
            if live_map.is_connected(current, dest, "bus") and self.player_tickets[user_id]["bus"] > 0:
                available.append("bus")
            if live_map.is_connected(current, dest, "metro") and self.player_tickets[user_id]["metro"] > 0:
                available.append("metro")
        return available

    def get_current_player(self):
        """Get the player whose turn it is."""
        if not self.turn_order:
            return None
        return self.turn_order[self.current_turn_index]

    def advance_turn(self):
        """Advance to the next player's turn."""
        self.current_turn_index = (self.current_turn_index + 1) % len(self.turn_order)
        if self.current_turn_index == 0:
            self.round_counter += 1

    def check_end_conditions(self):
        """Check if the game has ended."""
        if self.round_counter > self.MAX_ROUNDS:
            return "Mr. X wins! The detectives couldn't catch him in time."
        
        current_player = self.get_current_player()
        if not current_player:
            return None

        if current_player == self.mr_x_id:
            # Check if Mr. X is at the same location as any detective
            mr_x_location = self.player_locations.get(self.mr_x_id)
            for player_id in self.joined_players:
                if player_id != self.mr_x_id and self.player_locations.get(player_id) == mr_x_location:
                    return "Detectives win! They caught Mr. X."
        else:
            # Check if detective has any valid moves
            current_location = self.player_locations.get(current_player)
            if current_location:
                has_valid_moves = False
                for dest in live_map.get_connected_nodes(current_location):
                    if self.get_available_transports(current_player, current_location, dest):
                        has_valid_moves = True
                        break
                if not has_valid_moves:
                    return "Mr. X wins! A detective is trapped with no valid moves."
        
        return None

    def create_mr_x_notepad_embed(self):
        """Create the Mr. X notepad embed."""
        embed = discord.Embed(title="Mr. X's Notepad", color=discord.Color.dark_theme())
        
        # Add round information
        embed.add_field(name="Current Round", value=str(self.round_counter), inline=False)
        
        # Add ticket information
        tickets = self.player_tickets[self.mr_x_id]
        ticket_info = f"Taxi: {tickets['taxi']} | Bus: {tickets['bus']} | Metro: {tickets['metro']} | Black: {tickets['black']}"
        embed.add_field(name="Tickets", value=ticket_info, inline=False)
        
        # Add move history
        if self.mr_x_move_history:
            history = "\n".join([f"Round {i+1}: {move}" for i, move in enumerate(self.mr_x_move_history)])
            embed.add_field(name="Move History", value=history, inline=False)
        
        return embed

    def validate_move(self, user_id, destination, transport):
        """Validate if a move is legal."""
        current_location = self.player_locations.get(user_id)
        if not current_location:
            return False, "You haven't started the game yet."
        
        if not live_map.is_connected(current_location, destination, transport):
            return False, "Invalid move: No connection between locations with that transport."
        
        if user_id != self.mr_x_id:
            if self.player_tickets[user_id][transport] <= 0:
                return False, f"You don't have any {transport} tickets left."
        
        return True, None

    def execute_move(self, user_id, destination, transport):
        """Execute a move and update game state."""
        self.player_locations[user_id] = destination
        if user_id != self.mr_x_id:
            self.player_tickets[user_id][transport] -= 1
        else:
            self.mr_x_ticket_log.append(transport)
            if len(self.mr_x_move_history) < self.round_counter:
                self.mr_x_move_history.append(f"Used {transport} to {destination}")
            else:
                self.mr_x_move_history[self.round_counter - 1] = f"Used {transport} to {destination}"

    def get_player_status(self, user_id):
        """Get the current status of a player."""
        if user_id not in self.roles:
            return "You haven't joined the game yet."
        
        status = f"Role: {self.roles[user_id]}\n"
        if user_id in self.player_locations:
            status += f"Current Location: {self.player_locations[user_id]}\n"
        
        if user_id != self.mr_x_id:
            tickets = self.player_tickets[user_id]
            status += f"Tickets:\nTaxi: {tickets['taxi']}\nBus: {tickets['bus']}\nMetro: {tickets['metro']}"
        
        return status 