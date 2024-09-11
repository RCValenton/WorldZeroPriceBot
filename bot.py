import discord
from discord.ext import commands
import json
import os
import pandas as pd
from dotenv import load_dotenv

# Load environment variables from .env file (contains the bot token)
load_dotenv()

# Initialize bot with specific intents
intents = discord.Intents.default()
intents.message_content = True  # Enable reading message content
intents.messages = True
intents.guilds = True

# Create bot instance with command prefix '!'
bot = commands.Bot(command_prefix="!", intents=intents)

# Disable default help command to create a custom one
bot.remove_command('help')

# Path to store item prices data
PRICE_FILE = "item_prices.json"

# Load prices from a JSON file, if it exists
def load_prices():
    if os.path.exists(PRICE_FILE):
        with open(PRICE_FILE, "r") as f:
            return json.load(f)
    return {}

# Save updated prices to the JSON file
def save_prices():
    with open(PRICE_FILE, "w") as f:
        json.dump(item_prices, f, indent=4)

# Initialize item prices dictionary
item_prices = load_prices()

# Dictionary to keep track of users waiting to upload files
pending_uploads = {}

# Event when the bot is ready and logged in
@bot.event
async def on_ready():
    print(f'Bot is online! Logged in as {bot.user}')
    try:
        await bot.tree.sync()  # Sync any slash commands
        print("Slash commands synced.")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

# Command to prompt users to upload a file
@bot.command(description="Upload a .txt or .csv file with item prices")
async def upload(ctx):
    pending_uploads[ctx.author.id] = True
    await ctx.send("Please upload a .txt or .csv file with item prices.")

# Event to handle messages, including file uploads
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if message.author.id in pending_uploads and pending_uploads[message.author.id]:
        if message.attachments:
            attachment = message.attachments[0]

            # Handle .txt file uploads
            if attachment.filename.endswith('.txt'):
                file_content = await attachment.read()
                content = file_content.decode('utf-8')

                # Parse and store item=price pairs
                for line in content.split('\n'):
                    if '=' in line:
                        item, price = map(str.strip, line.split('='))
                        item_prices[item.lower()] = price

                save_prices()
                await message.channel.send("The item price list has been updated.")

            # Handle .csv file uploads
            elif attachment.filename.endswith('.csv'):
                file_path = attachment.filename
                await attachment.save(file_path)

                # Read and process CSV file
                try:
                    df = pd.read_csv(file_path)
                    for _, row in df.iterrows():
                        item = row['Item'].strip().lower()
                        price = row['Price'].strip()
                        item_prices[item] = price

                    save_prices()
                    await message.channel.send("The item price list has been updated.")
                except Exception as e:
                    await message.channel.send(f"Error processing the CSV file: {e}")
                finally:
                    os.remove(file_path)  # Clean up the uploaded file

            else:
                await message.channel.send("Please upload a valid .txt or .csv file.")
        else:
            await message.channel.send("No file attached. Please upload a valid file.")

        pending_uploads[message.author.id] = False

    await bot.process_commands(message)

# Command to add an item and its price to the database
@bot.command(description="Add an item and its price to the database")
async def add(ctx, item: str, *, price: str):
    item_prices[item.lower().strip()] = price
    save_prices()
    await ctx.send(f"Added {item} with price {price}.")

# Command to retrieve prices of items matching a search string
@bot.command(description="Retrieve the prices of items that match your input")
async def value(ctx, *, item: str):
    item = item.lower().strip().strip('"').strip("'")
    matching_items = {k: v for k, v in item_prices.items() if item in k}

    if matching_items:
        response = "\n".join([f"{k}: {v}" for k, v in matching_items.items()])
        await ctx.send(f"Here are the items matching '{item}':\n{response}")
    else:
        await ctx.send(f"No items found containing '{item}'.")

# Custom help command that lists all available commands
@bot.command(name="help", description="Display available commands")
async def help_command(ctx):
    embed = discord.Embed(title="Bot Commands", description="List of available commands", color=discord.Color.blue())
    for command in bot.commands:
        embed.add_field(name=f"!{command.name}", value=command.description, inline=False)

    await ctx.send(embed=embed)

# Start the bot using the token from environment variables
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
bot.run(TOKEN)
