import discord
from discord.ext import commands
import json
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Create an instance of the bot with the command prefix '!'
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Path to store the item prices
PRICE_FILE = "item_prices.json"

# Load prices from the file if it exists
def load_prices():
    if os.path.exists(PRICE_FILE):
        with open(PRICE_FILE, "r") as f:
            return json.load(f)
    return {}

# Save prices to the file
def save_prices():
    with open(PRICE_FILE, "w") as f:
        json.dump(item_prices, f, indent=4)

# Dictionary to store items and their prices
item_prices = load_prices()

@bot.event
async def on_ready():
    print(f'Bot is ready. Logged in as {bot.user}')
    try:
        await bot.tree.sync()
        print("Slash commands synced.")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

# Prefix command to add items and their prices (supports letters, symbols)
@bot.command()
async def add(ctx, item: str, *, price: str):
    item_prices[item.lower().strip()] = price  # Use lowercase and trim whitespace
    save_prices()  # Save the updated prices
    await ctx.send(f"Added {item} with price {price}.")

# Prefix command to retrieve the price of an item
@bot.command()
async def value(ctx, *, item: str):
    # Strip quotes if they are present
    item = item.lower().strip().strip('"').strip("'")
    
    if item in item_prices:
        await ctx.send(f"The price of {item} is {item_prices[item]}.")
    else:
        await ctx.send(f"Sorry, I don't have the price for {item}.")

# Get the bot token from the environment variables
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# Run the bot
bot.run(TOKEN)
