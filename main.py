import json
import os
import re
from telegram import Update, Bot
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors.rpcerrorlist import SessionPasswordNeededError

# Function to prompt for configuration
def prompt_for_config():
    config = {}
    config['api_id'] = input("Enter your API ID: ")
    config['api_hash'] = input("Enter your API Hash: ")
    config['session_string'] = input("Enter your Session Token: ")
    config['target_channel'] = input("Enter your Target Channel: ")
    config['bot_token'] = input("Enter your Bot Token: ")
    return config

# Check if config.json exists, if not, prompt for input
config_file_path = 'config.json'

if os.path.exists(config_file_path):
    with open(config_file_path, 'r') as f:
        config = json.load(f)
else:
    config = prompt_for_config()
    with open(config_file_path, 'w') as f:
        json.dump(config, f, indent=2)

api_id = config['api_id']
api_hash = config['api_hash']
session_string = config['session_string']
target_channel = config['target_channel']
bot_token = config['bot_token']

# Initialize the Telegram bot
updater = Updater(bot_token, use_context=True)
bot = Bot(bot_token)
dispatcher = updater.dispatcher

# Load or initialize user list
users_file = 'users.json'
if os.path.exists(users_file):
    with open(users_file, 'r') as f:
        users = json.load(f)
else:
    users = []

# /start command handler
def start(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    username = update.message.from_user.username or update.message.from_user.first_name

    if not any(user['chat_id'] == chat_id for user in users):
        users.append({'chat_id': chat_id, 'username': username})
        with open(users_file, 'w') as f:
            json.dump(users, f, indent=2)

    update.message.reply_text(f"Welcome, {username}! You are now registered to use the bot.")

# /getusers command handler
def get_users(update: Update, context: CallbackContext):
    user_list = '\n'.join([f"- {user['username']}" for user in users])
    update.message.reply_text(f"Total users: {len(users)}\n\n{user_list}")

# /get <bin> <channel> [limit] command handler
def get_cc(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    input_args = context.args

    if len(input_args) < 2:
        update.message.reply_text("Please provide BIN and channel name like this: /get <bin> <channel> [limit]")
        return

    bin_number = input_args[0]
    channel_name = input_args[1]
    limit = int(input_args[2]) if len(input_args) > 2 else 2

    update.message.reply_text(f"Fetching {limit} CCs with BIN {bin_number} from channel: {channel_name}")

    try:
        # Initialize the Telegram client
        client = TelegramClient(StringSession(session_string), api_id, api_hash)
        client.start()

        async def scrape_cc():
            # Fetch the channel and messages
            channel = await client.get_entity(channel_name)
            messages = await client.get_messages(channel, limit=1000)

            # Regex for finding credit card numbers with the provided BIN
            regex = re.compile(rf"\b{bin_number}\d{{10,13}}\b")
            extracted_ccs = []

            for message in messages:
                if message.message:
                    matches = regex.findall(message.message)
                    if matches:
                        extracted_ccs.extend(matches)
                        if len(extracted_ccs) >= limit:
                            break

            # Save results to a file
            output_file = f"scraped_{bin_number}.txt"
            with open(output_file, 'w') as f:
                f.write('\n'.join(extracted_ccs))

            # Send result back to the user
            bot.send_message(chat_id, f"Finished fetching CCs. Extracted {len(extracted_ccs)} CCs with BIN {bin_number}. Saved to {output_file}.")

            # Send the result to the target channel if configured
            if target_channel:
                bot.send_message(target_channel, f"Extracted {len(extracted_ccs)} CCs with BIN {bin_number}:\n\n" + '\n'.join(extracted_ccs))

        client.loop.run_until_complete(scrape_cc())

    except Exception as e:
        update.message.reply_text(f"Error occurred during scraping: {str(e)}")

# Register command handlers
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("getusers", get_users))
dispatcher.add_handler(CommandHandler("get", get_cc, pass_args=True))

# Start the bot
updater.start_polling()
updater.idle()
