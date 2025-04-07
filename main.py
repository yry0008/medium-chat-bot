import os
import logging
import redis
import openai
from telebot import TeleBot, types
from telebot.util import content_type_media
from dotenv import load_dotenv

import re
import base64
import json

if os.path.exists(".env"):
    load_dotenv()
# Configuration information
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")  # Custom endpoint
OPENAI_DEFAULT_MODEL = os.getenv("OPENAI_DEFAULT_MODEL", "gpt-3.5-turbo")
OPENAI_VISION_MODEL = os.getenv("OPENAI_VISION_MODEL", "gpt-4o")  # Vision model

HISTORY_DAYS = int(os.getenv("HISTORY_DAYS", 7))  # Number of days to save chat history
HISTORY_MAX_MESSAGES = int(os.getenv("HISTORY_MAX_MESSAGES", 10))  # Maximum number of messages per request

SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT", "You are a helpful assistant.")
MAX_COMPLETION_TOKENS = int(os.getenv("MAX_COMPLETION_TOKENS", 256))  # Maximum response length

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = os.getenv("REDIS_PORT", 6379)
REDIS_USERNAME = os.getenv("REDIS_USERNAME", None)
# Check if it is null
if REDIS_USERNAME == "":
    REDIS_USERNAME = None
# Check if it is null
if REDIS_USERNAME == "null":
    REDIS_USERNAME = None
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)
# Check if it is null
if REDIS_PASSWORD == "":
    REDIS_PASSWORD = None
# Check if it is null
if REDIS_PASSWORD == "null":
    REDIS_PASSWORD = None
REDIS_DB = os.getenv("REDIS_DB", 0)

# Initialize components
openai.api_key = OPENAI_API_KEY
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, username=REDIS_USERNAME, password=REDIS_PASSWORD)
bot = TeleBot(TELEGRAM_TOKEN)

# Logging configuration
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# Initialize OpenAI client
openai_client = openai.OpenAI(
    base_url=OPENAI_API_BASE,
    api_key=OPENAI_API_KEY
)

def get_chat_history(chat_id: str, message_id: str) -> list:
    """Retrieve chat history"""
    history = redis_client.get(f"chat:{chat_id}.{message_id}")
    return eval(history.decode()) if history else [{"role": "system", "content": SYSTEM_PROMPT}]

def save_chat_history(chat_id: str, message_id: str, history: list):
    """Save chat history"""
    redis_client.setex(f"chat:{chat_id}.{message_id}", 3600*24*HISTORY_DAYS, str(history))

def generate_response_stream(messages: list):
    """Generate response stream"""
    stream = openai_client.chat.completions.create(
        model=OPENAI_DEFAULT_MODEL,
        messages=messages,
        stream=True,
        max_completion_tokens=MAX_COMPLETION_TOKENS
    )
    
    full_response = []
    for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                full_response.append(content)
    return ''.join(full_response)

def generate_response_stream_photo(messages: list):
    """Generate response stream for photo"""
    stream = openai_client.chat.completions.create(
        model=OPENAI_VISION_MODEL,
        messages=messages,
        stream=True,
        max_completion_tokens=MAX_COMPLETION_TOKENS
    )
    
    full_response = []
    for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                full_response.append(content)
    return ''.join(full_response)
    

def escape_markdown(text):
    """Escape Markdown special characters"""
    # First, replace literal '\n' with actual newline characters
    text = text.replace('\\n', '\n')

    # Escape Markdown special characters except for newline characters
    markdown_chars = r'[\*_\[\]()~`>#\+\-=|{}\.!]'
    escaped_text = re.sub(markdown_chars, lambda m: '\\' + m.group(0), text)

    return escaped_text

@bot.message_handler(commands=['start'])
def handle_start(message: types.Message):
    """Handle /start command"""
    bot.reply_to(message, "Hello! I am your assistant. How can I help you today?")

@bot.message_handler(commands=['help'])
def handle_help(message: types.Message):
    """Handle /help command"""
    reply_text = "You can send me text messages or photos. I will respond to your queries. If you want to continue a conversation, just reply to the message send by me and I will continue the conversation. You can also mention me in group chats to get my attention."
    
    if message.chat.id < 0:
        reply_text += "\n\nYou can also use the following commands in this group:\n"
        reply_text += "/addfriend - Add friend request that allow friends find you in this group.\n"
        reply_text += "/deletefriend - Delete your friend request\n"
        reply_text += "/searchfriend - Search for a friend\n"
    bot.reply_to(message, reply_text)

@bot.message_handler(commands=['addfriend'])
def handle_addfriend(message: types.Message):
    """Handle /addfriend command"""
    if message.chat.id > 0:
        bot.reply_to(message, "This command is not available in private chats.")
        return
    # find if there is already a friend request
    friend_request = redis_client.lrange(f"addfriend.{message.chat.id}", 0, -1)
    if friend_request:
        for friend in friend_request:
            if message.from_user.id == int(friend):
                bot.reply_to(message, "You have already sent a friend request.")
                return
    redis_client.rpush(f"addfriend.{message.chat.id}", f"{message.from_user.id}")
    reply_text = "Your friend request has been sent."
    bot.reply_to(message, reply_text)

@bot.message_handler(commands=['deletefriend'])
def handle_deletefriend(message: types.Message):
    """Handle /deletefriend command"""
    if message.chat.id > 0:
        bot.reply_to(message, "This command is not available in private chats.")
        return
    # find if there is already a friend request
    friend_request = redis_client.lrange(f"addfriend.{message.chat.id}", 0, -1)
    if friend_request:
        for friend in friend_request:
            if message.from_user.id == int(friend):
                redis_client.lrem(f"addfriend.{message.chat.id}", 1, f"{message.from_user.id}")
                bot.reply_to(message, "Your friend request has been deleted.")
                return
    reply_text = "You have not sent a friend request."
    bot.reply_to(message, reply_text)

@bot.message_handler(commands=['searchfriend'])
def handle_searchfriend(message: types.Message):
    """Handle /searchfriend command"""
    if message.chat.id > 0:
        bot.reply_to(message, "This command is not available in private chats.")
        return
    
    friend_request = redis_client.lrange(f"addfriend.{message.chat.id}", 0, -1)
    if friend_request:
        friend_request = [int(friend) for friend in friend_request]
        if message.from_user.id in friend_request:
            friend_request.remove(message.from_user.id)
        if len(friend_request) == 0:
            bot.reply_to(message, "No friends found.")
            return
        # using GPT to select a friend
        prompt = "You are a friend selector. I will give you a list of friends' IDs. Please randomly select one of them and return the ID. The list of friends' IDs is in json format. You can only reply the ID of the selected friend, do not add any other text. "
        friend_request_json = json.dumps(friend_request)
        messages = [
            {"role":"system", "content": prompt},
            {"role":"user", "content": friend_request_json}
        ]
        response_text = generate_response_stream(messages)
        # check if the response is a number
        if response_text.isdigit():
            friend_id = int(response_text)
            # get the friend information
            friend_info = bot.get_chat(friend_id)
            friend_first_name = friend_info.first_name if friend_info.first_name else ""
            friend_last_name = friend_info.last_name if friend_info.last_name else ""
            friend_name = friend_first_name + " " + friend_last_name
            user_text = f"[{friend_name}](tg://user?id={friend_id})"
            reply_text = f"There is a friend for you: {user_text}"
            # send a message to the friend
            bot.reply_to(message, reply_text, parse_mode="MarkdownV2")
        else:
            reply_text = "No friends found."

    else:
        reply_text = "No friends found."
        bot.reply_to(message, reply_text)

@bot.message_handler(content_types=['text'], chat_types=['private'])
def handle_message(message: types.Message):
    """Handle text messages"""
    user_id = message.from_user.id
    chat_id = f"telegram_{user_id}"
    
    try:
        # Send initial message
        markup = types.ForceReply(selective=False)
        full_response = ""

        reply_message = message.reply_to_message
        if reply_message:
            # If it's a reply message, get the original message ID
            reply_message_id = reply_message.message_id
        else:
            # Otherwise, use the current message ID
            reply_message_id = ""        
        # Stream response
        
        history = get_chat_history(chat_id, reply_message_id)
        history.append({"role": "user", "content": message.text})
        full_response = generate_response_stream(history)
        
        # Update final message
        new_message = bot.reply_to(
            message,
            escape_markdown(full_response),
            parse_mode="MarkdownV2",
            disable_web_page_preview=True,
            reply_markup=markup
        )
        new_message_id = new_message.message_id
        # Save chat history
        history.append({"role": "assistant", "content": full_response})
        save_chat_history(chat_id, new_message_id, history)

    
    except Exception as e:
        logging.error(f"Failed to process message: {e}")
        bot.reply_to(
            message,
            text="⚠️ Request failed, please try again later"
        )

@bot.message_handler(content_types=['photo'], chat_types=['private'])
def handle_photo(message: types.Message):
    """Handle photo messages"""
    user_id = message.from_user.id
    chat_id = f"telegram_{user_id}"
    
    try:
        # Send initial message
        markup = types.ForceReply(selective=False)
        full_response = ""

        reply_message = message.reply_to_message
        if reply_message:
            # If it's a reply message, get the original message ID
            reply_message_id = reply_message.message_id
        else:
            # Otherwise, use the current message ID
            reply_message_id = ""        
        # Stream response
        
        history = get_chat_history(chat_id, reply_message_id)
        # Retain original history, use an independent message list
        new_message_list = history.copy()
        # Get photo file ID
        file_id = message.photo[-1].file_id
        # Get photo file information
        file_info = bot.get_file(file_id)
        # Download photo file
        file_path = file_info.file_path
        file = bot.download_file(file_path)
        # Convert photo file to base64 encoding
        file = base64.b64encode(file).decode('utf-8')
        # Get message caption
        new_message_list.append({"role": "user", "content": [{"type": "text", "text": message.caption}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{file}"}}]})
        full_response = generate_response_stream_photo(new_message_list)
        
        # Update final message
        new_message = bot.reply_to(
            message,
            escape_markdown(full_response),
            parse_mode="MarkdownV2",
            disable_web_page_preview=True,
            reply_markup=markup
        )
        new_message_id = new_message.message_id
        # Save chat history
        history.append({"role": "user", "content": "Sent a picture and add the caption below, " + message.caption})
        history.append({"role": "assistant", "content": full_response})
        save_chat_history(chat_id, new_message_id, history)

    
    except Exception as e:
        logging.error(f"Failed to process message: {e}")
        bot.reply_to(
            message,
            text="⚠️ Request failed, please try again later"
        )

@bot.message_handler(content_types=['text'], chat_types=['group', 'supergroup'])
def handle_group_message(message: types.Message):
    """Handle text messages in group chats"""
    user_id = message.chat.id
    chat_id = f"telegram_{user_id}"

    try:
        # Send initial message
        markup = types.ForceReply(selective=False)
        full_response = ""

        reply_message = message.reply_to_message
        if reply_message:
            if reply_message.from_user.id != bot.get_me().id:
                # If it's not a reply to the bot's message, return
                return
            # If it's a reply message, get the original message ID
            reply_message_id = reply_message.message_id
        else:
            # Check if the bot is mentioned
            if not message.entities:
                return
            is_mentioned = False
            for entity in message.entities:
                if entity.type == 'mention':
                    # If the bot is mentioned, mark it
                    # Extract the mentioned username from the message
                    mentioned_user = message.text[entity.offset:entity.offset + entity.length]
                    if mentioned_user == f"@{bot.get_me().username}":
                        is_mentioned = True
                    break
            if not is_mentioned:
                return
            reply_message_id = ""
        
        history = get_chat_history(chat_id, reply_message_id)
        history.append({"role": "user", "content": message.text})
        full_response = generate_response_stream(history)
        
        # Update final message
        new_message = bot.reply_to(
            message,
            escape_markdown(full_response),
            parse_mode="MarkdownV2",
            disable_web_page_preview=True,
            reply_markup=markup
        )
        new_message_id = new_message.message_id
        # Save chat history
        history.append({"role": "assistant", "content": full_response})
        save_chat_history(chat_id, new_message_id, history)

    
    except Exception as e:
        logging.error(f"Failed to process message: {e}")
        bot.reply_to(
            message,
            text="⚠️ Request failed, please try again later"
        )

@bot.message_handler(content_types=['photo'], chat_types=['group', 'supergroup'])
def handle_photo_group(message: types.Message):
    """Handle photo messages in group chats"""
    user_id = message.chat.id
    chat_id = f"telegram_{user_id}"
    
    try:
        # Send initial message
        markup = types.ForceReply(selective=False)
        full_response = ""

        reply_message = message.reply_to_message
        if reply_message:
            if reply_message.from_user.id != bot.get_me().id:
                # If it's not a reply to the bot's message, return
                return
            # If it's a reply message, get the original message ID
            reply_message_id = reply_message.message_id
        else:
            # Check if the bot is mentioned
            if not message.caption_entities:
                return
            is_mentioned = False
            for entity in message.caption_entities:
                if entity.type == 'mention':
                    # If the bot is mentioned, mark it
                    # Extract the mentioned username from the message
                    mentioned_user = message.caption[entity.offset:entity.offset + entity.length]
                    if mentioned_user == f"@{bot.get_me().username}":
                        is_mentioned = True
                    break
            if not is_mentioned:
                return
            reply_message_id = ""
        
        history = get_chat_history(chat_id, reply_message_id)
        # Retain original history, use an independent message list
        new_message_list = history.copy()
        # Get photo file ID
        file_id = message.photo[-1].file_id
        # Get photo file information
        file_info = bot.get_file(file_id)
        # Download photo file
        file_path = file_info.file_path
        file = bot.download_file(file_path)
        # Convert photo file to base64 encoding
        file = base64.b64encode(file).decode('utf-8')
        # Get message caption
        new_message_list.append({"role": "user", "content": [{"type": "text", "text": message.caption}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{file}"}}]})
        full_response = generate_response_stream_photo(new_message_list)
        
        # Update final message
        new_message = bot.reply_to(
            message,
            escape_markdown(full_response),
            parse_mode="MarkdownV2",
            disable_web_page_preview=True,
            reply_markup=markup
        )
        new_message_id = new_message.message_id
        # Save chat history
        history.append({"role": "user", "content": "Sent a picture and add the caption below, " + message.caption})
        history.append({"role": "assistant", "content": full_response})
        save_chat_history(chat_id, new_message_id, history)

    
    except Exception as e:
        logging.error(f"Failed to process message: {e}")
        bot.reply_to(
            message,
            text="⚠️ Request failed, please try again later"
        )
        


if __name__ == "__main__":
    bot.infinity_polling()
