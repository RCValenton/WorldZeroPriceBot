import discord
from discord.ext import commands
import json
import os
import re
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

# Helper function to convert string prices like '100k', '800m' to integer values
def convert_price_to_number(price_str):
    price_str = price_str.lower().replace(',', '').replace('+', '').replace('-', '')  # Normalize and remove commas, +, -
    
    # For ranges like "600m-1b" or "5/10m-", pick the lower end of the range
    if '/' in price_str:
        price_str = price_str.split('/')[0]  # Take the first part as the price
    
    # Match numbers optionally followed by k (thousands), m (millions), or b (billions)
    match = re.match(r'^(\d+(\.\d+)?)([kmb])?$', price_str)
    if match:
        number = float(match.group(1))
        if match.group(3) == 'k':
            return int(number * 1000)
        elif match.group(3) == 'm':
            return int(number * 1000000)
        elif match.group(3) == 'b':  # New handling for billions
            return int(number * 1000000000)
        else:
            return int(number)  # No suffix, just a number
    return None  # Return None if the price format is invalid

# Function to split the response into chunks of up to 2000 characters
def split_message(content, max_length=2000):
    current_chunk = []
    chunks = []
    current_length = 0

    for item in content:
        item_str = f"{item[0]}: {item[1]} | "  # Format each item as "item: price |"
        if current_length + len(item_str) > max_length:
            chunks.append(''.join(current_chunk))
            current_chunk = []
            current_length = 0

        current_chunk.append(item_str)
        current_length += len(item_str)

    # Add the last chunk
    if current_chunk:
        chunks.append(''.join(current_chunk))

    return chunks

# Command to list items within the user's budget
@bot.command(description="List items you can afford based on your gold budget")
async def budget(ctx, *, gold: str):
    user_gold = convert_price_to_number(gold)

    if user_gold is None:
        await ctx.send("Invalid gold amount. Please use formats like '100k', '500m', or '200'.")
        return

    # Filter items that are affordable within the budget
    affordable_items = [
        (item, price) for item, price in item_prices.items()
        if convert_price_to_number(price) is not None and convert_price_to_number(price) <= user_gold
    ]

    if affordable_items:
        # Create the side-by-side response
        chunks = split_message(affordable_items)
        
        # Send each chunk as a separate message
        for chunk in chunks:
            await ctx.send(chunk)
    else:
        await ctx.send(f"No items found within your budget of {gold}.")

# Start the bot using the token from environment variables
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
bot.run(TOKEN)
