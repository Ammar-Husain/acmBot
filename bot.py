import os
from base64 import b64decode

from pyrogram import Client, filters
from pyrogram.types import (
    BotCommand,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from methods import competitions, mongo, questions, quizzes, teams
from models import NewBotUser

buttons_counters = {}


async def main():
    is_prod = os.getenv("PRODUCTION")
    if not is_prod:
        import dotenv

        dotenv.load_dotenv()

    API_ID = os.getenv("API_ID")
    API_HASH = os.getenv("API_HASH")
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    DB_URI = os.getenv("DB_URI")

    app = Client(name="acmb", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
    await app.start()
    print("Bot started")

    db_client = mongo.connect_to_mongo(DB_URI)
    print("DataBase connected")

    await app.set_bot_commands(
        [
            BotCommand("start", "start the bot"),
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

    # quizzes related actions
    @app.on_message(filters.private & filters.command("create_quiz"))
    async def handle_create_quiz(app, message):
        await quizzes.create_quiz(message, db_client)

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
        print("Called")
        await quizzes.test_quiz(message, db_client)

    # questions related actions
    @app.on_message(filters.private & filters.regex(r"^/edit_quiz_questions_(\w+)$"))
    async def handle_edit_quiz_questions(app, message):
        await questions.edit_quiz_questions(message, db_client)

    @app.on_message(filters.private & filters.regex(r"^/edit_question_([0-9]*)_(\w+)$"))
    async def handle_edit_question(app, message):
        await questions.edit_question(message, db_client)

    @app.on_message(filters.private & filters.regex(r"^/add_questions_(\w+)$"))
    async def handle_add_questions(app, message):
        await questions.add_questions(message, db_client)

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

    def encoded(_, __, update):
        try:
            print(update.text)
            text = update.text.replace("@Awasi_CMbot", "").strip()
            if text and len(text) % 4 == 0:
                command = b64decode(text.encode()).decode()
                if "," in command:
                    return True
        except:
            pass

        return False

    encoded_filter = filters.create(encoded)

    @app.on_message(filters.group & encoded_filter)
    async def handle_encoded_group_message(app, message):
        parts = (
            b64decode(message.text.replace("Awasi_CMbot", "").strip().encode())
            .decode()
            .split(",")
        )
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

    @app.on_callback_query()
    async def hanlde_callback_query(client, callback_query: CallbackQuery):
        button_id = str(callback_query.inline_message_id)
        user = callback_query.from_user
        if callback_query.data == "ready":
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

    await shutdown_event.wait()
    await app.stop()


if __name__ == "__main__":
    import asyncio
    import signal

    shutdown_event = asyncio.Event()
    handle_sigterm = lambda _, __: shutdown_event.set

    signal.signal(signal.SIGTERM, handle_sigterm)
    signal.signal(signal.SIGINT, handle_sigterm)

    asyncio.get_event_loop().run_until_complete(main())
