import asyncio
import os
import re
import signal
from base64 import b64decode
from pprint import pformat

import requests
from pyrogram import Client, enums, filters
from pyrogram.enums import ChatType
from pyrogram.types import (
    BotCommand,
    CallbackQuery,
    ChatMember,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from methods import competitions, mongo, questions, quizzes, teams
from models import NewBotUser

buttons_counters = {}

from flask_server import run_flask


async def main():
    run_flask()
    is_prod = os.getenv("PRODUCTION")
    if not is_prod:
        import dotenv

        dotenv.load_dotenv()

    API_ID = os.getenv("API_ID")
    API_HASH = os.getenv("API_HASH")
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    DB_URI = os.getenv("DB_URI")
    ADMINS_LIST = os.getenv("ADMINS_IDS", "").split(",")

    LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))
    SERVICE_URL = os.getenv("SERVICE_URL")

    app = Client(name="acmb", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
    await app.start()
    print("Bot started")

    db_client = mongo.connect_to_mongo(DB_URI)
    # if not os.getenv("PRODUCTION"):
    #     db_client = db_client.test

    print("DataBase connected")

    await app.set_bot_commands(
        [
            BotCommand("start", "start the bot"),
            BotCommand("help", "Show Instructions"),
            BotCommand("create_quiz", "create new quiz"),
            BotCommand("my_quizzes", "manage your quizzes"),
            BotCommand("add_teams", "add teams"),
            BotCommand("my_teams", "manage your teams"),
            BotCommand("create_set", "create a set of teams"),
            BotCommand("my_sets", "manage your teams sets"),
            BotCommand("start_competition", "start a competition in a group"),
        ]
    )

    @app.on_message(filters.private & filters.command("start"))
    async def handle_start(app, message):
        await message.reply(
            f"Hello, {message.from_user.first_name}!, Welcome To Awasi Competitions Manager!\n"
            "Use /help to show Bot manual.",
            quote=True,
        )
        users = db_client.acmbDB.users

        user = users.find_one({"_id": message.from_user.id})
        if not user:
            users.insert_one(NewBotUser(message.from_user.id).as_dict())

    @app.on_message(filters.private & filters.command("help"))
    async def handle_help(app, message):
        instructions = (
            "<u><b>Bot Usage Manual:</b></u>\n\n"
            "Steps to To Start A Competition:\n\n"
            "1. Create a quiz from /create_quiz or obtain link for a quiz created by another user.\n\n"
            "2. Create you teams from /add_teams\n\n."
            "3. put your teams In a set from /create_set.\n\n"
            "4. Configure your competition from /start_competition and obtain a starting button.\n\n"
            "5. When You are ready press the button and choose the group in which the competition will be held, and let the rest to the Bot!!"
        )
        second = (
            "You can edit (add / edit / delete ) your quizzes/questions/options in /my_quizzes\n\n"
            "You can add and delete your teams and sets in /my_teams / /my_sets"
        )
        await message.reply(instructions)
        await message.reply(second)

    def is_admin(_, __, u):
        admin = bool(u.from_user and str(u.from_user.id) in ADMINS_LIST)
        return admin

    admins_filter = filters.create(is_admin)

    @app.on_message(admins_filter & filters.command("dump_db"))
    async def handle_dump_db(app, message):
        await message.reply(message.from_user.id)
        parts = message.text.split(" ")
        users = db_client.acmbDB.users.find({})
        if len(parts) == 1:
            for user in users:
                try:
                    user_chat = await app.get_chat(user["_id"])
                    await message.reply(
                        f"{user_chat.username}: {user_chat.first_name} {user_chat.last_name or ''}"
                    )
                except:
                    await message.reply(f"Couldn't access {user["_id"]}")

                await message.reply(pformat(user))
            return
        if parts[1] == "quizzes":
            if len(parts) == 3 and parts[2].isnumeric():
                user = [user for user in users if user["_id"] == int(parts[2])]
                if not user:
                    return await message.reply("User not found")
                user = user[0]
                user_quizzes_id = [quiz["_id"] for quiz in user["quizzes"]]
                await message.reply(pformat(user_quizzes_id))
                quizzes = db_client.acmbDB.quizzes.find(
                    {"_id": {"$in": user_quizzes_id}}
                )
                if not quizzes:
                    return await message.reply("User has no quizzes")
                for quizz in quizzes:
                    await message.reply(pformat(quizz, indent=2))

    # quizzes related actions
    @app.on_message(filters.private & filters.command("create_quiz"))
    async def handle_create_quiz(app, message):
        await quizzes.create_quiz(app, message, db_client)

    @app.on_message(filters.private & filters.command("my_quizzes"))
    async def handle_my_quizzes(app, message: Message):
        await quizzes.my_quizzes(message, db_client)

    @app.on_message(filters.private & filters.regex(r"^/delete_quiz_(\w+)$"))
    async def handle_delete_quiz(app, message):
        await quizzes.delete_quiz(message, db_client)

    @app.on_message(filters.private & filters.regex(r"^/edit_title_(\w+)$"))
    async def handle_edit_title(app, message):
        await quizzes.edit_title(message, db_client)

    @app.on_message(filters.private & filters.regex(r"^/edit_description_(\w+)$"))
    async def handle_edit_description(app, message):
        await quizzes.edit_description(message, db_client)

    @app.on_message(filters.private & filters.regex(r"^/test_quiz_(\w+)$"))
    async def handle_show_quiz(app, message):
        await quizzes.test_quiz(app, message, db_client)

    @app.on_message(filters.private & filters.regex(r"^/link_quiz_(\w+)$"))
    async def handle_link_quiz(app, message):
        await quizzes.link_quiz(message)

    # questions related actions
    @app.on_message(filters.private & filters.regex(r"^/edit_quiz_questions_(\w+)$"))
    async def handle_edit_quiz_questions(app, message):
        await questions.edit_quiz_questions(message, db_client)

    @app.on_message(filters.private & filters.regex(r"^/edit_question_([0-9]*)_(\w+)$"))
    async def handle_edit_question(app, message):
        await questions.edit_question(message, db_client)

    @app.on_message(
        filters.private & filters.regex(r"^/edit_explanation_([0-9]*)_(\w+)$")
    )
    async def handle_edit_question_explanation(app, message):
        await questions.edit_question_explanation(message, db_client)

    @app.on_message(filters.private & filters.regex(r"^/add_questions_(\w+)$"))
    async def handle_add_questions(app, message):
        await questions.add_questions(app, message, db_client)

    @app.on_message(filters.private & filters.regex(r"^/add_media_([0-9]*)_(\w+)$"))
    async def handle_add_media(app, message):
        await questions.add_media(app, message, db_client)

    @app.on_message(filters.private & filters.regex(r"^/media_([0-9]*)$"))
    async def handle_get_media(app, message):
        await questions.get_media(app, message)

    @app.on_message(
        filters.private & filters.regex(r"^/delete_media_([1-3])_([0-9*])_(\w+)$")
    )
    async def handle_delete_media(app, message):
        await questions.delete_media(app, message, db_client)

    @app.on_message(
        filters.private & filters.regex(r"^/delete_question_([0-9]*)_(\w+)$")
    )
    async def handle_delete_question(app, message):
        await questions.delete_question(message, db_client)

    @app.on_message(filters.private & filters.regex(r"^/add_options_([0-9]+)_(\w+)$"))
    async def handle_add_options(app, message):
        await questions.add_options(message, db_client)

    # competitions related actions
    @app.on_message(filters.private & filters.command("start_competition"))
    async def handle_start_competion(app, message):
        await competitions.start_competition(app, message, db_client)

    # teams related actions
    @app.on_message(filters.private & filters.command("my_teams"))
    async def my_teams_handler(app, message):
        await teams.my_teams(app, message, db_client)

    @app.on_message(filters.private & filters.command("add_teams"))
    async def handle_setup_teams(app, message):
        await teams.add_teams(app, message, db_client)

    @app.on_message(filters.private & filters.regex(r"^/delete_team_([0-9+])$"))
    async def handle_delete_team(app, message):
        await teams.delete_team(message, db_client)

    @app.on_message(filters.private & filters.command("create_set"))
    async def handle_create_set(app, message):
        await teams.create_set(app, message, db_client)

    @app.on_message(filters.private & filters.command("my_sets"))
    async def handle_my_sets(app, message):
        await teams.my_sets(message, db_client)

    @app.on_message(filters.private & filters.regex(r"^/delete_set_([0-9+])$"))
    async def handle_delete_set(app, message):
        await teams.delete_set(message, db_client)

    def encoded(_, __, u):
        try:
            command = re.findall(r"@\w+\s(.+)", u.text)
            if command and len(command[0]) % 4 == 0:
                decoded = b64decode(command[0].encode()).decode()
                if "," in decoded:
                    return True
        except:
            pass

        return False

    encoded_filter = filters.create(encoded)

    def is_forum(_, __, m):
        return m.chat and m.chat.type == ChatType.FORUM

    forum_filter = filters.create(is_forum)

    @app.on_message((filters.group | forum_filter) & encoded_filter)
    async def handle_encoded_group_message(app, message):
        command = re.findall(r"@\w+\s(.+)", message.text)[0]
        parts = b64decode(command.encode()).decode().split(",")
        if len(parts) == 2:
            quiz_id, question_time = parts[0], parts[1]
            await competitions.begin_solo_competition(
                message, quiz_id, question_time, db_client
            )
        elif len(parts) == 3:
            quiz_id, set_id, question_time = parts[0], parts[1], parts[2]
            await competitions.begin_teams_competition(
                app, message, quiz_id, set_id, question_time, db_client
            )

    async def read_cb(_, __, callback_query):
        return callback_query.data == "ready"

    ready_cb_filter = filters.create(read_cb)

    @app.on_callback_query(ready_cb_filter)
    async def hanlde_callback_query(client, callback_query: CallbackQuery):
        button_id = str(f"{callback_query.message.chat.id}/{callback_query.message.id}")
        print(button_id)
        print(callback_query.message.chat.id)
        user = callback_query.from_user
        if not button_id in buttons_counters:
            buttons_counters[button_id] = []
        if not user.id in buttons_counters[button_id]:
            buttons_counters[button_id].append(user.id)
            await callback_query.answer(f"Nice! {user.first_name}, Keep It Up!")

            start_button = InlineKeyboardButton(
                "Yes, I am ready!", callback_data="ready"
            )
            print(len(buttons_counters[button_id]))
            ready_count_button = InlineKeyboardButton(
                f"{len(buttons_counters[button_id])} are Ready!", callback_data="t"
            )
            keyboard = InlineKeyboardMarkup([[start_button], [ready_count_button]])
            await callback_query.message.edit_reply_markup(keyboard)
        else:
            await callback_query.answer(
                f"Ok we got it!, Hold up the competition will begin soon!!"
            )

    async def continue_comp_cbq(_, app, callback_query):
        return "continue_" in callback_query.data or True

    continue_comp_cbq_filter = filters.create(continue_comp_cbq)

    @app.on_callback_query(continue_comp_cbq_filter)
    async def handle_continue_comp_callback(app, callback_query):
        button_presser = await app.get_chat_member(
            callback_query.message.chat.id, callback_query.from_user.id
        )
        if not button_presser.status in [
            enums.ChatMemberStatus.ADMINISTRATOR,
            enums.ChatMemberStatus.OWNER,
        ]:
            await callback_query.answer("Sorry, Admins Only.")

        paused_compo_id = callback_query.data.replace("continue_", "")
        paused_compo = db_client.acmbDB.paused_compos.find_one({"_id": paused_compo_id})
        if not paused_compo:
            print("Paused compo not found")
            return

        await callback_query.answer("Alright, Continuing...")

        callback_query.message.from_user.id = paused_compo["set_owner_id"]
        teams_results = {
            int(id): result for id, result in paused_compo["teams_results"].items()
        }
        await competitions.begin_teams_competition(
            app,
            callback_query.message,
            paused_compo["quiz_id"],
            paused_compo["set_id"],
            paused_compo["question_time"],
            db_client,
            teams_results,
        )

    async def log(app, text):
        return await app.send_message(LOG_CHANNEL_ID, text)

    async def ping_server():
        if SERVICE_URL:
            res = requests.get(SERVICE_URL)
            return await log(app, res.text)
        else:
            return await log(
                app,
                "Warning: $SERVICE_URL is not set, the service can sleep at anytime.",
            )

    async def keep_up():
        m = await ping_server()
        while True:
            try:
                await asyncio.sleep(60)
                await m.delete()
                m = await ping_server()
            except Exception as e:
                await log(client, str(e))
                pass

    asyncio.create_task(keep_up())
    await shutdown_event.wait()
    await app.stop()


if __name__ == "__main__":
    shutdown_event = asyncio.Event()
    handle_sigterm = lambda _, __: shutdown_event.set()

    signal.signal(signal.SIGTERM, handle_sigterm)
    signal.signal(signal.SIGINT, handle_sigterm)

    asyncio.get_event_loop().run_until_complete(main())
