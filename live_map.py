import io
from PIL import Image, ImageDraw, ImageFont
import os

# Define the map dimensions and position coordinates
MAP_WIDTH = 1280
MAP_HEIGHT = 959
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MAP_IMAGE_PATH = os.path.join(BASE_DIR, 'map.png')
NODES_PATH = os.path.join(BASE_DIR, 'nodes.txt')
CONNECTIONS_PATH = os.path.join(BASE_DIR, 'connections.txt')

# Store player positions and appearance information
PLAYER_COLOURS = {
    "Mr. X": "black",
    "Detective_1": "blue",
    "Detective_2": "red",
    "Detective_3": "purple",
    "Detective_4" : "pink"
}
COLOUR_RGBA = {
    "black": (0, 0, 0, 128),    # 50% opacity
    "blue": (0, 0, 255, 128),
    "red": (255, 0, 0, 128),
    "pink" : (255,192,203,128),
    "purple": (128, 0, 128, 128),
    "white": (255, 255, 255, 128)
}

# Store node coordinates and connections
POSITION_COORDS = {}
CONNECTIONS = {}

# Mr. X reveal rounds
REVEAL_ROUNDS = [3, 8, 13, 18, 24]

def load_node_coordinates(filename='nodes.txt'):
    """Load node coordinates from nodes.txt."""
    coords = {}
    try:
        with open(NODES_PATH, 'r') as f:
            for line in f:
                parts = line.strip().split(',')
                if len(parts) == 3:
                    node, x, y = map(int, parts)
                    if 0 <= x <= MAP_WIDTH and 0 <= y <= MAP_HEIGHT:
                        coords[node] = (x, y)
                    else:
                        print(f"Warning: Node {node} coordinates ({x}, {y}) out of bounds")
        if not coords:
            raise Exception("No valid coordinates loaded from nodes.txt")
        print(f"Loaded {len(coords)} coordinates from {filename}")
        return coords
    except FileNotFoundError:
        raise Exception("nodes.txt not found")
    except ValueError as e:
        raise Exception("Invalid format in nodes.txt")

def load_connections(filename='connections.txt'):
    """Load station connections from connections.txt (comma-separated)."""
    connections = {}
    try:
        with open(CONNECTIONS_PATH, 'r') as f:
            for line in f:
                parts = line.strip().split(',')
                if len(parts) == 3:
                    station1, station2, transport = int(parts[0]), int(parts[1]), parts[2]
                    if transport not in ['taxi', 'bus', 'underground']:
                        print(f"Warning: Invalid transport type {transport} in connections.txt")
                        continue
                    if station1 not in connections:
                        connections[station1] = []
                    if station2 not in connections:
                        connections[station2] = []
                    connections[station1].append((station2, transport))
                    connections[station2].append((station1, transport))
        if not connections:
            raise Exception("No valid connections loaded from connections.txt")
        print(f"Loaded connections for {len(connections)} stations from {filename}")
        return connections
    except FileNotFoundError:
        raise Exception(f"connections.txt not found at {CONNECTIONS_PATH}")
    except ValueError as e:
        raise Exception("Invalid format in connections.txt")

def init_map():
    """Initialize the map with default settings"""
    global POSITION_COORDS, CONNECTIONS
    try:
        POSITION_COORDS = load_node_coordinates()
        CONNECTIONS = load_connections()
    except Exception as e:
        print(f"Failed to initialize map: {e}")
    if not os.path.exists(MAP_IMAGE_PATH):
        raise Exception(f"Map image not found at {MAP_IMAGE_PATH}")

def get_possible_moves(current_location, roles, is_mr_x=False, mr_x_id = None):
    """Return possible moves and required tickets from the current location."""
    try:
        if current_location not in CONNECTIONS:
            return {"error": f"No connections found for station {current_location}"}
        if current_location not in POSITION_COORDS:
            return {"error": f"Station {current_location} not found in nodes.txt"}

        # Get occupied stations
        occupied = {r["location"] for uid, r in roles.items() if r.get("location") and uid != mr_x_id}

        moves = {}
        for dest, transport in CONNECTIONS[current_location]:
            if dest in occupied:
                continue  # Skip occupied stations
            if dest not in moves:
                moves[dest] = []
            moves[dest].append(transport)
            if is_mr_x:
                moves[dest].append("black")  # Mr. X can use black tickets for any move

        # Remove duplicates and sort tickets
        for dest in moves:
            moves[dest] = sorted(list(set(moves[dest])))

        if not moves:
            return {"error": f"No valid moves from station {current_location} (all destinations occupied)"}
        return moves
    except Exception as e:
        print(f"[get_possible_moves] Error: {type(e).__name__}: {e}")
        return {"error": f"Error calculating moves: {str(e)}"}

def update_player_location(player_id, location, roles):
    """Update a player's location in the roles dictionary."""
    try:
        if player_id not in roles:
            return f"Player {player_id} not found."
        if location not in POSITION_COORDS:
            return f"Invalid node {location}."
        roles[player_id]['location'] = location
        print(f"Updated location for player {player_id}: {location}")
        return f"Moved to location {location}!"
    except Exception as e:
        print(f"Error in update_player_location: {type(e).__name__}: {e}")
        return f"Error updating location: {str(e)}"

def generate_map(player_locations, current_round, zoom_player=None, mr_x_id=None):
    """Generate the game map with all players' positions"""
    try:
        # Load the base map image
        base_map = Image.open(MAP_IMAGE_PATH).convert("RGBA")
        if base_map.size != (MAP_WIDTH, MAP_HEIGHT):
            base_map = base_map.resize((MAP_WIDTH, MAP_HEIGHT), Image.Resampling.LANCZOS)
        draw = ImageDraw.Draw(base_map)
        
        # Try to load a font, fall back to default if not available
        try:
            font = ImageFont.truetype("arial.ttf", 16)
            small_font = ImageFont.truetype("arial.ttf", 12)
        except IOError:
            font = ImageFont.load_default()
            small_font = ImageFont.load_default()
                
        token_radius = 15
        glow_radius = 20
        
        detective_count = 0        
        for player_id, role_info in player_locations.items():
            location = role_info.get("location")
            role = role_info.get("role")
            
            # Skip if the location is not defined
            if not location or not role or location not in POSITION_COORDS:
                continue
                
            # Hide Mr. X's token for non-Mr. X perspectives outside reveal rounds
            if role == "Mr. X" and player_id == mr_x_id:
                if zoom_player != mr_x_id and current_round not in REVEAL_ROUNDS:
                    continue
                
            x, y = POSITION_COORDS[location]
            if role == "Detective":
                detective_count += 1
                color_key = f"Detective_{min(detective_count, 3)}"
            else:
                color_key = role
            color = PLAYER_COLOURS.get(color_key, "white")
            glow_color = COLOUR_RGBA.get(color, COLOUR_RGBA["white"])
                
            # added glow token effect
            draw.ellipse(
                (x-glow_radius, y-glow_radius, x+glow_radius, y+glow_radius), 
                fill=glow_color, outline=None
            )

            draw.ellipse(
                (x-token_radius, y-token_radius, x+token_radius, y+token_radius), 
                fill=color, outline="white", width=2
            )
                
            # Add player label (X or D)
            label = "X" if role == "Mr. X" else "D"
            text_bbox = draw.textbbox((0, 0), label, font=small_font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
            draw.text(
                (x - text_width // 2, (y - text_height // 2) - 2),
                label, fill="white", font=small_font, stroke_width=1, stroke_fill="black"
            )  

        # Zoom in if zoom_player is specified
        if zoom_player and zoom_player in player_locations:
            location = player_locations[zoom_player].get("location")
            if location in POSITION_COORDS:
                x, y = POSITION_COORDS[location]
                left = max(0, x - 150)
                top = max(0, y - 150)
                right = min(MAP_WIDTH, x + 150)
                bottom = min(MAP_HEIGHT, y + 150)
                base_map = base_map.crop((left, top, right, bottom))
                base_map = base_map.resize((300, 300), Image.Resampling.LANCZOS)

        # Convert the image to bytes to send to Discord
        img_byte_arr = io.BytesIO()
        base_map.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)

        # Check file size (Discord limit: ~8MB)
        if img_byte_arr.getbuffer().nbytes > 7.5 * 1024 * 1024:
            base_map = base_map.resize((MAP_WIDTH // 2, MAP_HEIGHT // 2), Image.Resampling.LANCZOS)
            img_byte_arr = io.BytesIO()
            base_map.save(img_byte_arr, format='PNG')
            img_byte_arr.seek(0)

        return img_byte_arr
        
    except Exception as e:
        print(f"Error generating map: {type(e).__name__}: {e}")
        return None

# Initialize the map on module import
init_map()