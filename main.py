import msgs
from dotenv import load_dotenv
import os

load_dotenv(".env")

from pyrogram import Client, filters, enums
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ForceReply,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from db import create_user, user_exists, update_user_column, get_users_columns

from uploader import upload_file
import rvc
import json

links = ["@aiticle", "@nedaaiofficial"]

bot = Client(
    "sessions/nedaai",
    api_id=os.getenv("API_ID"),
    api_hash=os.getenv("API_HASH"),
    bot_token=os.getenv("TOKEN"),
)


async def is_joined(app, user_id):
    not_joined = []
    for channel in links:
        try:
            await app.get_chat_member(channel, user_id)
        except:
            not_joined.append(channel)
    return not_joined


@bot.on_message((filters.regex("/start") | filters.regex("/Start")) & filters.private)
async def start_text(client, message):
    not_joined_channels = await is_joined(bot, message.from_user.id)
    chat_id = message.chat.id
    username = message.from_user.username

    # Check if user has joined required channels
    if not_joined_channels:
        buttons = []
        for channel in not_joined_channels:
            buttons.append(
                [
                    InlineKeyboardButton(
                        text=f"{channel}",
                        url=f"https://t.me/{channel.replace('@', '')}",
                    )
                ]
            )

        reply_markup = InlineKeyboardMarkup(buttons)
        await message.reply(msgs.join_channels, reply_markup=reply_markup)

    else:
        # Check if user exists; if not, create one
        if not user_exists(chat_id):
            create_user(chat_id, username)

            # Check if user is invited, if yes add reward credits to inviter
            if len(message.text.split(" ")) == 2:
                invited_by = message.text.split(" ")[1]
                update_user_column(invited_by, "refs", 1, True)
                update_user_column(invited_by, "credits", msgs.invitation_gift, True)

        await message.reply(msgs.start)


@bot.on_message(filters.private & (filters.voice | filters.audio))
async def get_voice_or_audio(client, message):
    t_id = message.chat.id
    media = message.voice or message.audio
    duration = media.duration

    if media and not message.from_user.is_bot:
        # save file
        file_id = media.file_id
        file = await client.download_media(file_id, file_name=f"files/{t_id}/voice.ogg")

        # upload file to pixiee
        file_url = upload_file(file, f"{file_id}.ogg")

        # add the audio to database
        update_user_column(t_id, "audio", file_url)

        # add the audio duration to database
        update_user_column(t_id, "duration", duration)

        # generate the available models as buttons from models.json
        buttons = create_reply_markup(generate_model_list("models.json"))
        await message.reply(
            msgs.voice_select, reply_markup=buttons, parse_mode=enums.ParseMode.HTML
        )


@bot.on_callback_query()
async def callbacks(client, callback_query):
    message = callback_query.message
    data = callback_query.data
    chat_id = callback_query.from_user.id

    if data.startswith("cat_"):
        await callback_query.answer(msgs.select_category)
        return

    await message.delete()

    # seleted the voice models
    if data.startswith("voice_"):
        model_name = data.replace("voice_", "")
        update_user_column(chat_id, "model_name", model_name)

        buttons = create_reply_markup(msgs.pitch_btns)
        await message.reply(msgs.pitch_select, reply_markup=buttons)

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

        await message.reply(f"{msgs.banner_msg}\n\n{invite_link}")

        await message.reply(
            msgs.invite_help.format(refs=refs, invite_link=invite_link, credits=credits)
        )

    elif data == "credits":
        # Get user's current credits
        user_data = get_users_columns(chat_id, "credits")
        if user_data is None:
            return

        credits = user_data["credits"]

        await message.reply(msgs.credits_message.format(credits=credits))

    elif data == "help":
        await message.reply(msgs.help_msg)

    elif data == "convert_voice":
        await message.reply(msgs.convert_msg)

    # TODO : Add any generation to generations table
    elif data.startswith("pitch_"):
        # check if user has enough credits
        user = get_users_columns(chat_id, ["duration", "credits"])
        credits = user["credits"]
        duration = user["duration"]

        if credits < duration:
            await message.reply(msgs.no_credits)
            return

        # update user credits
        update_user_column(chat_id, "credits", credits - duration)

        # get pitch
        pitch = int(data.replace("pitch_", ""))

        # get model from database
        model_name = get_users_columns(chat_id, "model_name")["model_name"]

        # get model data from models.json
        model_data = get_value_from_json("models.json", model_name)
        model_title = model_data["name"]
        model_url = model_data["url"]
        model_0_pitch = model_data["pitch"]
        audio = get_users_columns(chat_id, "audio")["audio"]
        rvc_model = model_data["type"]

        # create rvc conversion to replicate
        rvc.create_rvc_conversion(
            audio,
            model_url,
            chat_id,
            pitch=pitch + model_0_pitch,
            voice_name=model_title,
            rvc_model=rvc_model,
        )

        await message.reply(msgs.proccessing)


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

    await message.reply(f"{msgs.banner_msg}\n\n{invite_link}")

    await message.reply(
        msgs.invite_help.format(refs=refs, invite_link=invite_link, credits=credits)
    )


@bot.on_message(filters.command("credits"))
async def buy_credits_command(client, message):
    chat_id = message.from_user.id

    # Get user's current credits
    user_data = get_users_columns(chat_id, "credits")
    if user_data is None:
        return

    credits = user_data["credits"]

    await message.reply(msgs.credits_message.format(credits=credits))


@bot.on_message(filters.command("menu"))
async def menu_command(client, message):
    buttons = create_reply_markup(msgs.menu_btns)
    await message.reply(msgs.menu_msg, reply_markup=buttons)


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


bot.run()
