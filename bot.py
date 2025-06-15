import os

from pyrogram import Client, filters
from pyrogram.types import BotCommand, Message

from methods import mongo, questions, quizzes
from models import NewBotUser


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
            BotCommand("start_competition", "start a competition in a group"),
        ]
    )

    @app.on_message(filters.command("start"))
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
    @app.on_message(filters.command("create_quiz"))
    async def handle_create_quiz(app, message):
        await quizzes.create_quiz(message, db_client)

    @app.on_message(filters.command("my_quizzes"))
    async def handle_my_quizzes(app, message: Message):
        await quizzes.my_quizzes(message, db_client)

    @app.on_message(filters.regex(r"^/delete_quiz_(\w+)$"))
    async def handle_delete_quiz(app, message):
        await quizzes.delete_quiz(message, db_client)

    @app.on_message(filters.regex(r"^/edit_title_(\w+)$"))
    async def handle_edit_title(app, message):
        await quizzes.edit_title(message, db_client)

    @app.on_message(filters.regex(r"^/edit_description_(\w+)$"))
    async def handle_edit_description(app, message):
        await quizzes.edit_description(message, db_client)

    @app.on_message(filters.regex(r"^/edit_quiz_questions_(\w+)$"))
    async def handle_edit_quiz_questions(app, message):
        await questions.edit_quiz_questions(message, db_client)

    # questions related actions

    @app.on_message(filters.regex(r"^/edit_question_([0-9]*)_(\w+)$"))
    async def handle_edit_question(app, message):
        await questions.edit_question(message, db_client)

    @app.on_message(filters.regex(r"^/add_questions_(\w+)$"))
    async def handle_add_questions(app, message):
        await questions.add_questions(message, db_client)

    @app.on_message(filters.regex(r"^/delete_question_([0-9]*)_(\w+)$"))
    async def handle_delete_question(app, message):
        await questions.delete_question(message, db_client)

    @app.on_message(filters.regex("^add_options_([0-9]+)_(/w+)$"))
    async def handle_add_options(app, message):
        await questions.add_options(message, db_client)

    await shutdown_event.wait()
    await app.stop()


if __name__ == "__main__":
    import asyncio
    import signal

    shutdown_event = asyncio.Event()
    handle_sigterm = lambda _, __: asyncio.get_event_loop().call_soon_threadsafe(
        shutdown_event.set
    )

    signal.signal(signal.SIGTERM, handle_sigterm)
    signal.signal(signal.SIGINT, handle_sigterm)

    asyncio.get_event_loop().run_until_complete(main())
