import os
import google.generativeai as genai
import pymongo
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from dotenv import load_dotenv
import datetime

# Load environment variables from .env file
load_dotenv()

# MongoDB setup
client = pymongo.MongoClient(os.getenv("MONGO_URI"))
db = client['chatbot_db']  # Database name
users_collection = db['users']  # Users collection
chats_collection = db['chats']  # Chats collection
files_collection = db['files']  # Files collection

# Telegram Bot Token
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GENIE_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GENIE_API_KEY)
model = genai.GenerativeModel("gemini-pro")


# Function to check if user exists in the database
def user_registered(chat_id):
    return users_collection.find_one({"chat_id": chat_id}) is not None

# Function to save user details to the database
def save_user_to_db(first_name, username, chat_id):
    users_collection.insert_one({
        "first_name": first_name,
        "username": username,
        "chat_id": chat_id,
        "phone_number": None  # Initial value, to be updated later
    })

# Function to save chat history to the database
def save_chat_history(user_message, response, chat_id):
    # Extracting the response text only
    bot_response_text = response.text if hasattr(response, "text") else str(response)

    # Define chat history document
    chat_document = {
        "user_message": user_message,
        "bot_response": bot_response_text,  # Store only text, not the entire object
        "chat_id": chat_id,
        "timestamp": datetime.datetime.now()
    }

    # Insert into MongoDB
    chats_collection.insert_one(chat_document)


# Function to save file metadata to the database
def save_file_metadata(file_path, description, chat_id):
    files_collection.insert_one({
        "file_path": file_path,
        "description": description,
        "chat_id": chat_id,
        "timestamp": datetime.now()
    })

# Command to start the bot and register user
async def start(update: Update, context):
    user = update.message.from_user
    chat_id = update.message.chat_id

    # Check if user is already registered
    if not user_registered(chat_id):
        save_user_to_db(user.first_name, user.username, chat_id)

        # Ask for phone number
        keyboard = [[KeyboardButton("Share phone number", request_contact=True)]]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        await update.message.reply_text("Welcome! Please share your phone number.", reply_markup=reply_markup)
    else:
        await update.message.reply_text("You are already registered!")

# Function to handle phone number sharing
async def handle_contact(update: Update, context):
    user = update.message.from_user
    chat_id = update.message.chat_id
    phone_number = update.message.contact.phone_number

    # Update phone number in the database
    users_collection.update_one(
        {"chat_id": chat_id},
        {"$set": {"phone_number": phone_number}}
    )

    await update.message.reply_text(f"Thank you, {user.first_name}! Your phone number has been registered.")

# Function to handle chat (Gemini-powered response)
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text  # Get the user's message
    
    # Assuming 'response' is coming from an AI model (e.g., OpenAI API)
    response = model.generate_content(user_message)  # Replace this with your actual API call

    # Convert response to string (extract text)
    response_text = str(response.text) if hasattr(response, "text") else str(response)

    await update.message.reply_text(response_text)  # Send the text response


# Function to handle media (image/file analysis)
async def handle_media(update, context):
    attachments = update.message.effective_attachment  # Get the attachment(s)

    if not isinstance(attachments, tuple):  # Convert to tuple if single file
        attachments = (attachments,)

    for file_attachment in attachments:
        file = await file_attachment.get_file()  # Get the file from Telegram
        file_path = await file.download_to_drive()  # Download file properly
        await update.message.reply_text(f"File downloaded to: {file_path}")




# Function to perform a web search
async def web_search(update: Update, context):
    query = " ".join(context.args)  # Get search query from user's message

    # Perform a web search (you could integrate an API like Google or Bing)
    search_results = search_web(query)

    # Send search results to the user
    await update.message.reply_text(f"Top results for {query}:\n\n" + "\n".join(search_results))

# Mock web search function (replace with actual API call)
def search_web(query):
    # Replace this with a real web search (like Google or Bing API)
    return [
        "Result 1: Some search result URL",
        "Result 2: Another search result URL",
        "Result 3: Third search result URL"
    ]

# Main function to set up the bot
async def main():
    # Create Application instance
    application = Application.builder().token(BOT_TOKEN).build()

    # Add handlers for various commands
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("websearch", web_search))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    application.add_handler(MessageHandler(filters.PHOTO, handle_media))
    application.add_handler(MessageHandler(filters.CONTACT, handle_contact))

    # Run the bot
    await application.run_polling()

# To handle an already running event loop in environments like Jupyter or interactive Python sessions:
if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()  # Allow nesting of event loops (for interactive environments like Jupyter)

    import asyncio
    asyncio.run(main())
