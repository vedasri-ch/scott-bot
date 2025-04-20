# Scotland Yard Discord Bot

A Discord bot implementation of the classic Scotland Yard board game, where players take on the roles of detectives trying to catch the elusive Mr. X.

## Features

- Real-time game state management
- Interactive map visualization : Sends customized map image ( zoomed in ), for ease of player, Automatic + updated map generation
- Multiple transportation modes (Taxi, Bus, Metro)
- Role-based gameplay (Mr. X and Detectives)
- Ticket management system
- Turn-based movement
- Automatic game state tracking

## Project Structure

- `bot.py` - Main Discord bot implementation
- `game.py` - Game logic and state management
- `live_map.py` - Map visualization and node management
- `.env` - Configuration file for sensitive data
- `requirements.txt` - Project dependencies

### Data Files
- `bus_map.txt` - Bus route connections
- `metro_map.txt` - Metro route connections
- `taxi_map.txt` - Taxi route connections
- `nodes.txt` - Node/point data for the map
- `map.png` - Base map image
- `startgame_image.png` - Game start screen image
- `connections.txt` - All possible moves, and tickets required for the moves

## Setup and Running Instructions

### Prerequisites
- Python 3.8 or higher
- pip (Python package manager)
- A Discord account
- A Discord server where you have administrator permissions

### Step 1: Get Discord Bot Token
1. Go to the [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application" and give it a name
3. Go to the "Bot" section in the left sidebar
4. Click "Add Bot"
5. Under the bot's username, click "Reset Token"
6. Copy the token (you'll need this for the `.env` file)

### Step 2: Invite Bot to Your Server
1. In the Discord Developer Portal, go to "OAuth2" > "URL Generator"
2. Select these scopes:
   - `bot`
   - `applications.commands`
3. Select these bot permissions:
   - `Send Messages`
   - `Embed Links`
   - `Attach Files`
   - `Read Message History`
   - `Add Reactions`
   - `Use Slash Commands`
4. Copy the generated URL and open it in your browser
5. Select your server and authorize the bot

### Step 3: Project Setup
1. Clone the repository:
   ```bash
   git clone [your-repository-url]
   cd [repository-name]
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create and configure `.env` file:
   ```
   DISCORD_TOKEN=your_discord_token_here
   GUILD_ID=your_guild_id_here
   ```
   Replace `your_discord_token_here` with the token you copied earlier
   Replace `your_guild_id_here` with your Discord server ID (right-click server name > Copy Server ID)

### Step 4: Run the Bot
1. Open a terminal/command prompt
2. Navigate to the project directory
3. Run the bot:
   ```bash
   python bot.py
   ```
4. You should see a message indicating the bot has logged in successfully

### Verifying the Bot is Working
1. The bot should appear online in your Discord server
2. Try using the `/help` command in any channel
3. You should see a list of available commands

## Game Commands

- `/startgame` - Start a new game
- `/join` - Join the current game
- `/begin` - Begin the game after players have joined
- `/move <destination>` - Make a move to a new location
- `/map` - Display the current game map
- `/status` - Check your current status
- `/moves` - Show possible moves from your location
- `/endgame` - End the current game
- `/help` - Show all commands and game rules

## Game Rules

1. One player is Mr. X, others are Detectives
2. Mr. X moves secretly, revealing their location every 5 rounds
3. Detectives must catch Mr. X before the game ends
4. Each player has limited tickets for different transport types:
   - Taxi: 12 tickets
   - Bus: 8 tickets
   - Metro: 4 tickets
   - Mr. X also has 5 black tickets
5. Mr. X wins if they:
   - Survive all rounds
   - Trap a detective with no valid moves
6. Detectives win if they catch Mr. X

## Development

### Dependencies
- discord.py>=2.3.2
- python-dotenv>=1.0.0
- Pillow>=10.0.0

### Code Organization
- `game.py` handles all game logic and state management
- `bot.py` manages Discord interactions and commands
- `live_map.py` handles map visualization and node connections

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

[Add your license information here] 
