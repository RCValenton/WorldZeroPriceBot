import discord
from discord.ext import commands
import json
import os
import pandas as pd
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Create an instance of the bot with the command prefix '!'
intents = discord.Intents.default()
intents.message_content = True  # This will allow the bot to read messages and attachments
intents.messages = True
intents.guilds = True
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

# Create a dictionary to store users waiting for uploads
pending_uploads = {}

@bot.event
async def on_ready():
    print(f'Bot is ready. Logged in as {bot.user}')
    try:
        await bot.tree.sync()
        print("Slash commands synced.")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

# Command to ask for file upload
@bot.command()
async def upload(ctx):
    # Set the user as pending for an upload
    pending_uploads[ctx.author.id] = True
    await ctx.send("Please upload a .txt or .csv file with item prices.")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return  # Ignore messages from the bot itself

    # Check if the user is expected to upload a file
    if message.author.id in pending_uploads and pending_uploads[message.author.id]:
        if message.attachments:
            attachment = message.attachments[0]

            # Handle .txt file
            if attachment.filename.endswith('.txt'):
                file_content = await attachment.read()  # Read the file content
                content = file_content.decode('utf-8')  # Decode it from bytes to a string

                # Process the file content (expected format: "Item = Price")
                lines = content.split('\n')
                for line in lines:
                    if '=' in line:
                        item, price = line.split('=')
                        item = item.strip().lower()  # Clean item name
                        price = price.strip()  # Clean price
                        item_prices[item] = price

                save_prices()  # Save the updated prices
                await message.channel.send("The value list has been updated.")

            # Handle .csv file
            elif attachment.filename.endswith('.csv'):
                # Save the file in the current directory (where the bot is running)
                file_path = attachment.filename
                await attachment.save(file_path)

                # Read the CSV using pandas
                try:
                    df = pd.read_csv(file_path)
                    for index, row in df.iterrows():
                        item = row['Item'].strip().lower()  # Clean item name
                        price = row['Price'].strip()  # Clean price
                        item_prices[item] = price

                    save_prices()  # Save the updated prices
                    await message.channel.send("The value list has been updated.")
                except Exception as e:
                    await message.channel.send(f"Error processing the CSV file: {e}")

                # Delete the file after processing
                try:
                    os.remove(file_path)  # Deletes the file after saving
                except OSError as e:
                    await message.channel.send(f"Error deleting the file: {e}")
            else:
                await message.channel.send("Please upload a valid .txt or .csv file.")
        else:
            await message.channel.send("No file attached. Please upload a .txt or .csv file with item prices.")
        
        # Mark the user as no longer waiting for an upload
        pending_uploads[message.author.id] = False

    await bot.process_commands(message)

# Prefix command to add items and their prices (supports letters, symbols)
@bot.command()
async def add(ctx, item: str, *, price: str):
    item_prices[item.lower().strip()] = price  # Use lowercase and trim whitespace
    save_prices()  # Save the updated prices
    await ctx.send(f"Added {item} with price {price}.")

# Prefix command to retrieve all matching items and their prices
@bot.command()
async def value(ctx, *, item: str):
    # Normalize the input by stripping quotes and converting to lowercase
    item = item.lower().strip().strip('"').strip("'")

    # Search for all matching items containing the input
    matching_items = {k: v for k, v in item_prices.items() if item in k.lower()}

    if matching_items:
        # Format the response with all matching items and their prices
        response = "\n".join([f"{k}: {v}" for k, v in matching_items.items()])
        await ctx.send(f"Here are all the items containing '{item}':\n{response}")
    else:
        await ctx.send(f"Sorry, no items found containing '{item}'.")

# Get the bot token from the environment variables
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# Run the bot
bot.run(TOKEN)
