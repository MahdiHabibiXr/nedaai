import json
import logging
import os

import dotenv

dotenv.load_dotenv(".env")

from pyrogram import Client, enums, filters
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

import msgs
import rvc
from db import (
    create_user,
    create_users_table,
    get_users_columns,
    update_user_column,
    user_exists,
    DB_NAME,
    create_generations_table,
    add_generation,
    add_gender_column_to_users,
)
from uploader import upload_file

links = msgs.channels_list
MODELS_DIR = "sessions/models.json"

bot = Client(
    "sessions/nedaai",
    api_id=os.getenv("API_ID"),
    api_hash=os.getenv("API_HASH"),
    bot_token=os.getenv("TOKEN"),
)

# initialize the tables
create_users_table()
create_generations_table()
add_gender_column_to_users()


async def is_joined(app, user_id):
    not_joined = []
    for channel in links:
        try:
            await app.get_chat_member(channel, user_id)
        except:
            not_joined.append(channel)
    return not_joined


@bot.on_message(filters.user(msgs.admin_id) & filters.document)
async def handle_file(client, message):
    chat_id = message.chat.id
    logging.basicConfig(level=logging.INFO)
    try:
        file = await message.download(f"./{MODELS_DIR}")
        await message.reply(file)
        await message.reply("Json saved successfully")
        logging.basicConfig(level=logging.INFO)
    except Exception as e:
        logging.basicConfig(level=logging.INFO)
        await message.reply(f"Error saving json file: {str(e)}")


@bot.on_message(filters.user(msgs.admin_id) & (filters.reply))
async def handle_reply(client, message):
    chat_id = message.chat.id
    reply = message.reply_to_message

    if reply.voice or reply.audio:
        await message.reply(reply.voice.file_id or reply.audio.file_id)
    elif reply.text:
        await message.reply(reply.text)
    elif reply.document:
        await message.reply(reply.document.file_)
    elif reply.photo:
        await message.reply(reply.photo.file_id)
    elif reply.video:
        await message.reply(reply.video.file_)


@bot.on_message(filters.user(msgs.admin_id) & filters.regex("/admin"))
async def amdin(client, message):
    message.chat.id
    text = message.text
    message.from_user.mention

    if ("/admin_get_credits_") in text:
        user_id = text.replace("/get_credits_", "")
        user_data = get_users_columns(user_id, "credits")
        credits = user_data["credits"]
        await message.reply(credits)

    elif ("/config") in text:
        if not os.path.exists("voice_cloner.db"):
            create_users_table()
        # Create sessions directory if it doesn't exist
        if not os.path.exists("sessions"):
            os.makedirs("sessions")
        await message.reply("Database created successfully")

    elif ("/get_db") in text:
        await client.send_document(message.chat.id, DB_NAME)

    elif ("set_banner_image") in text:
        banner_img_id = text.replace("/admin/set_banner_image", "")
        msgs.banner_img_id = banner_img_id

        await message.reply(msgs.banner_img_id)
        # await client.send_photo(msgs.admin_id, int(banner_img_id))


@bot.on_message((filters.regex("/start") | filters.regex("/Start")) & filters.private)
async def start_text(client, message):
    not_joined_channels = await is_joined(bot, message.from_user.id)
    chat_id = message.chat.id
    message.from_user.mention
    username = message.from_user.username

    # check if user exists
    if not user_exists(chat_id):
        create_user(chat_id, username)
        await message.reply(msgs.gift_msg.format(inital_credits=msgs.initial_gift))

        # Check if user is invited, if yes add reward credits to inviter
        if len(message.text.split(" ")) == 2:
            invited_by = message.text.split(" ")[1]
            update_user_column(invited_by, "refs", 1, True)

            await client.send_message(
                invited_by,
                msgs.invite_successfully.format(
                    user=username,
                    gift_credits=msgs.invitation_gift,
                    admin=msgs.admin_username,
                ),
            )

            update_user_column(invited_by, "credits", msgs.invitation_gift, True)

    # Check if user has joined required channels
    if not_joined_channels:
        buttons = joined_channels_button(not_joined_channels)
        reply_markup = InlineKeyboardMarkup(buttons)
        await message.reply(msgs.join_channels, reply_markup=reply_markup)

    else:
        await message.reply(msgs.start.format(username=username))


@bot.on_message(filters.private & (filters.voice | filters.audio))
async def get_voice_or_audio(client, message):
    t_id = message.chat.id
    media = message.voice or message.audio
    duration = media.duration

    try:
        if media and not message.from_user.is_bot:
            # save file
            file_id = media.file_id
            file = await client.download_media(
                file_id, file_name=f"files/{t_id}/voice.ogg"
            )

            # upload file to pixiee
            file_url = upload_file(file, f"nedaai/{t_id}/{file_id}.ogg")

            # add the audio to database
            update_user_column(t_id, "audio", file_url)

            # add the audio duration to database
            update_user_column(t_id, "duration", duration)

            # ask user the gender
            buttons = create_reply_markup(msgs.gender_btns)
            await message.reply(msgs.gender_select, reply_markup=buttons)

    except Exception as e:
        logging.basicConfig(level=logging.INFO)
        await client.send_message(msgs.admin_id, f"Error: {str(e)}")


@bot.on_callback_query()
async def callbacks(client, callback_query):
    try:
        message = callback_query.message
        data = callback_query.data
        chat_id = callback_query.from_user.id

        return_to_menu = create_reply_markup([msgs.return_to_menu_button])
        username = callback_query.from_user.mention

        if data.startswith("cat_"):
            await callback_query.answer(msgs.select_category)
            return

        await message.delete()

        # selected the voice models
        if data.startswith("voice_"):
            model_name = data.replace("voice_", "")
            update_user_column(chat_id, "model_name", model_name)

            # check the gender of input and selected voice
            model_data = get_value_from_json(MODELS_DIR, model_name)
            model_gender = model_data["gender"]

            user_data = get_users_columns(chat_id, "gender")
            user_gender = user_data["gender"]

            # same gender for user input and selected model
            if user_gender == model_gender:
                buttons = create_reply_markup(msgs.pitch_btns)
                await message.reply(msgs.pitch_select, reply_markup=buttons)

            # different gender for model and input
            else:
                # male to female => 12
                if (user_gender == "male") & (model_gender == "female"):
                    pitch = 12

                # female to male => -12
                elif (user_gender == "female") & (model_gender == "male"):
                    pitch = -12

                await process_pitch_conversion(
                    chat_id, data=None, message=message, pitch_based_on_gender=pitch
                )

        # selected the gender
        elif data.startswith("gender_"):
            gender = data.replace("gender_", "")
            update_user_column(chat_id, "gender", gender)

            # generate the available models as buttons from models.json
            buttons = create_reply_markup(generate_model_list(MODELS_DIR))
            await message.reply(
                msgs.voice_select, reply_markup=buttons, parse_mode=enums.ParseMode.HTML
            )

        elif data == "invite":
            # Get user's current refs count
            user_data = get_users_columns(chat_id, ["refs", "credits"])
            if user_data is None:
                return

            refs = user_data["refs"]
            credits = user_data["credits"]

            # Create unique invite link
            bot_info = await client.get_me()
            invite_link = f"https://t.me/{bot_info.username}?start={chat_id}"
            caption = f"{msgs.banner_msg}\n\n{invite_link}"

            await client.send_photo(chat_id, msgs.banner_img_id, caption=caption)
            await message.reply(
                msgs.invite_help.format(
                    refs=refs,
                    invite_link=invite_link,
                    credits=credits,
                    invitation_gift=msgs.invitation_gift,
                ),
                reply_markup=return_to_menu,
            )

        elif data == "credits":
            # Get user's current credits
            user_data = get_users_columns(chat_id, "credits")
            if user_data is None:
                return

            credits = user_data["credits"]

            await message.reply(
                msgs.credits_message.format(credits=credits, amdin=msgs.admin_username),
                reply_markup=return_to_menu,
            )

        elif data == "help":
            await message.reply(
                msgs.help_msg.format(admin_username=msgs.admin_username),
                reply_markup=return_to_menu,
            )

        elif data == "convert_voice":
            await message.reply(msgs.convert_msg, reply_markup=return_to_menu)

        elif data == "menu":
            buttons = create_reply_markup(msgs.menu_btns)
            await message.reply(msgs.menu_msg, reply_markup=buttons)

        elif data == "joined_channels":
            not_joined_channels = await is_joined(bot, chat_id)

            # Check if user has joined required channels
            if not_joined_channels:
                buttons = joined_channels_button(not_joined_channels)
                reply_markup = InlineKeyboardMarkup(
                    joined_channels_button(not_joined_channels)
                )
                await message.reply(msgs.join_channels, reply_markup=reply_markup)

            else:
                await message.reply(msgs.start.format(username=username))

        elif data.startswith("pitch_"):
            # check if user has enough credits
            await process_pitch_conversion(chat_id, data, message)

    except Exception as e:
        logging.error(f"Error in callback: {str(e)}")
        await client.send_message(msgs.admin_id, f"Error in callback: {str(e)}")


@bot.on_message(filters.command("invite"))
async def invite_command(client, message):
    chat_id = message.from_user.id

    # Get user's current refs count
    user_data = get_users_columns(chat_id, ["refs", "credits"])
    if user_data is None:
        return

    refs = user_data["refs"]
    credits = user_data["credits"]

    # Create unique invite link
    bot_info = await client.get_me()
    invite_link = f"https://t.me/{bot_info.username}?start={chat_id}"
    caption = f"{msgs.banner_msg}\n\n{invite_link}"

    await client.send_photo(chat_id, msgs.banner_img_id, caption=caption)

    return_to_menu = create_reply_markup([msgs.return_to_menu_button])
    await message.reply(
        msgs.invite_help.format(
            refs=refs,
            invite_link=invite_link,
            credits=credits,
            invitation_gift=msgs.invitation_gift,
        ),
        reply_markup=return_to_menu,
    )


@bot.on_message(filters.command("credits"))
async def credits_command(client, message):
    chat_id = message.from_user.id

    # Get user's current credits
    user_data = get_users_columns(chat_id, "credits")
    if user_data is None:
        return

    credits = user_data["credits"]
    return_to_menu = create_reply_markup([msgs.return_to_menu_button])
    await message.reply(
        msgs.credits_message.format(credits=credits, amdin=msgs.admin_username),
        reply_markup=return_to_menu,
    )


@bot.on_message(filters.command("buy_credits"))
async def buy_credits_command(client, message):
    chat_id = message.from_user.id

    # Get user's current credits
    user_data = get_users_columns(chat_id, "credits")
    if user_data is None:
        return

    credits = user_data["credits"]
    return_to_menu = create_reply_markup([msgs.return_to_menu_button])
    await message.reply(
        msgs.buy_credits_message.format(credits=credits, amdin=msgs.admin_username),
        reply_markup=return_to_menu,
    )


@bot.on_message(filters.command("menu"))
async def menu_command(client, message):
    buttons = create_reply_markup(msgs.menu_btns)
    await message.reply(msgs.menu_msg, reply_markup=buttons)


@bot.on_message(filters.command("123"))
async def help123_command(client, message):
    logging.info(f"123")


@bot.on_message(filters.command("help"))
async def help_command(client, message):
    buttons = create_reply_markup([msgs.return_to_menu_button])
    await message.reply(
        msgs.help_msg.format(admin_username=msgs.admin_username), reply_markup=buttons
    )


@bot.on_message(filters.text)
async def unknown_command(client, message):
    await message.reply(msgs.error_message)


def create_reply_markup(button_list):
    # text,type,data,row
    keyboard = []

    for button in button_list:
        label, button_type, data, row_index = button

        # Create an InlineKeyboardButton based on the button type
        if button_type == "callback":
            btn = InlineKeyboardButton(label, callback_data=data)
        elif button_type == "url":
            btn = InlineKeyboardButton(label, url=data)
        elif button_type == "switch_inline_query":
            btn = InlineKeyboardButton(label, switch_inline_query=data)
        elif button_type == "switch_inline_query_current_chat":
            btn = InlineKeyboardButton(label, switch_inline_query_current_chat=data)
        else:
            raise ValueError(f"Unsupported button type: {button_type}")

        # Add the button to the appropriate row
        while len(keyboard) <= row_index:
            keyboard.append([])

        keyboard[row_index].append(btn)

    return InlineKeyboardMarkup(keyboard)


def create_keyboard(button_list, resize_keyboard=True, one_time_keyboard=False):
    """
    Create a reply keyboard with the given list of button labels.

    Args:
        button_list (list): A list of button labels. Can be a flat list or a nested list for rows.
        resize_keyboard (bool): Whether to resize the keyboard (default is True).
        one_time_keyboard (bool): Whether to hide the keyboard after one use (default is False).

    Returns:
        ReplyKeyboardMarkup: A Pyrogram ReplyKeyboardMarkup object.
    """
    # Check if button_list is a nested list (rows provided explicitly)
    if all(isinstance(item, list) for item in button_list):
        keyboard = [[KeyboardButton(label) for label in row] for row in button_list]
    else:
        # Treat it as a flat list (all buttons in one row)
        keyboard = [[KeyboardButton(label) for label in button_list]]

    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=resize_keyboard,
        one_time_keyboard=one_time_keyboard,
    )


def file_name_gen(t_id, file_id):
    directory = f"files/{t_id}"
    if not os.path.exists(directory):
        os.makedirs(directory)

    existing_files = os.listdir(directory)
    file_number = len(existing_files) + 1
    return f"{directory}/{file_number}.ogg"


def add_to_files_json(t_id, file_url):
    if os.path.exists("files.json"):
        with open("files.json", "r") as f:
            files = json.load(f)
    else:
        files = {}

    if str(t_id) in files:
        files[str(t_id)].append(file_url)
    else:
        files[str(t_id)] = [file_url]

    with open("files.json", "w") as f:
        json.dump(files, f, indent=4)


def get_files_by_chat_id(chat_id):
    if os.path.exists("files.json"):
        with open("files.json", "r") as f:
            files = json.load(f)
        return files.get(str(chat_id), [])
    return []


def generate_model_list(json_file):
    """
    Generate a list of models grouped by categories, with category names as headers.

    Args:
        json_file (str): Path to the models.json file.

    Returns:
        list: A list of models grouped by categories with headers.
    """
    with open(json_file, "r", encoding="utf-8") as f:
        models = json.load(f)

    # Group models by category
    categories = {}
    for key, model in models.items():
        category = model.get("category", "Uncategorized")
        if category not in categories:
            categories[category] = []
        categories[category].append((key, model))

    model_list = []
    row_number = 0

    # Define category order
    category_order = ["voice_actor", "character", "actor", "celebritie", "singer"]

    # Add models by category with headers in specified order
    for category in category_order:
        if category not in categories:
            continue

        category_models = categories[category]

        # Add category header as a regular button instead of header type
        model_list.append(
            [
                msgs.category_header.format(
                    category=msgs.categories_lable[category], count=len(category_models)
                ),
                "callback",
                f"cat_{category}",
                row_number,
            ]
        )
        row_number += 1

        # Add models in this category
        for i, (key, model) in enumerate(category_models):
            if i % 2 == 0 and i > 0:
                row_number += 1
            model_list.append([model["name"], "callback", f"voice_{key}", row_number])

        row_number += 1  # Add extra row between categories

    return model_list


def get_value_from_json(file_path, key):
    """
    Retrieve the value of a specific key from a JSON file.

    Args:
        file_path (str): Path to the JSON file.
        key (str): The key whose value you want to retrieve.

    Returns:
        any: The value associated with the key, or None if the key doesn't exist.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            data = json.load(file)
            return data.get(
                key
            )  # Returns the value for the key, or None if it doesn't exist
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found.")
        return None
    except json.JSONDecodeError:
        print("Error: Failed to decode JSON.")
        return None


def joined_channels_button(not_joined_channels):
    buttons = []
    for channel in not_joined_channels:
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"{channel}", url=f"https://t.me/{channel.replace('@', '')}"
                )
            ]
        )
    buttons.append(
        [
            InlineKeyboardButton(
                text=msgs.joined_channels_btn[0],
                callback_data=msgs.joined_channels_btn[2],
            )
        ]
    )
    return buttons


async def process_pitch_conversion(chat_id, data, message, pitch_based_on_gender=None):
    # check if user has enough credits
    user = get_users_columns(chat_id, ["duration", "credits"])
    credits = user["credits"]
    duration = user["duration"]

    if credits < duration:
        await message.reply(msgs.no_credits)
        return

    # update user credits
    new_credits = credits - duration
    update_user_column(chat_id, "credits", new_credits)

    # get pitch | if data has been passed it means it is calling from pitch selection
    if data:
        pitch = int(data.replace("pitch_", ""))

    # it means it has beed detected from gender selection
    elif pitch_based_on_gender is not None:
        pitch = pitch_based_on_gender

    # get model from database
    model_name = get_users_columns(chat_id, "model_name")["model_name"]

    # get model data from models.json
    model_data = get_value_from_json(MODELS_DIR, model_name)
    model_title = model_data["name"]
    model_url = model_data["url"]
    model_0_pitch = model_data["pitch"]
    audio = get_users_columns(chat_id, "audio")["audio"]
    rvc_model = model_data["type"]

    # create rvc conversion to replicate
    prediction = rvc.create_rvc_conversion(
        audio,
        model_url,
        chat_id,
        pitch=pitch + model_0_pitch,
        voice_name=model_title,
        rvc_model=rvc_model,
    )

    # add to generations table
    add_generation(chat_id, audio, model_name, duration, prediction)

    await message.reply(msgs.proccessing_emojie)
    await message.reply(msgs.proccessing.format(credits=new_credits))


logging.basicConfig(level=logging.INFO)
logging.info("bot started")

if __name__ == "__main__":
    bot.run()

logging.info("bot stopped")
