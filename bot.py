import os
import re

from pyrogram import Client, enums, filters
from pyrogram.types import BotCommand, Message

from models import NewBotUser, Quiz, QuizPreview, QuizQuestion
from mongo import connect_to_mongo


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

    db_client = connect_to_mongo(DB_URI)
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
    async def handle_start(app, message: Message):
        await message.reply(
            f"Hello, {message.from_user.first_name}!, Welcome To Awasi Competitions Manager!\n"
            "Use /help to show Bot manual.",
            quote=True,
        )
        users = db_client.acmbDB.users

        user = users.find_one({"_id": message.from_user.id})
        if not user:
            users.insert_one(NewBotUser(message.from_user.id).as_dict())

    @app.on_message(filters.command("create_quiz"))
    async def handle_create_quiz(app, message):
        await message.reply(
            "Let's Create a new Quiz together!, send your new quizz title, or /cancel_quiz to cancel.",
            quote=True,
        )
        user = message.from_user

        title_message = await user.listen(filters.text)
        if title_message.text == "/cancel_quiz":
            await title_message.reply("Cancelled.", quote=True)
            return
        title = title_message.text
        await title_message.reply(
            f"Your new quiz title is <b>{title}</b> !", quote=True
        )

        await title_message.reply(
            "Send a description for your quiz or skip by sending /skip or cancel by /cancel_quiz",
            quote=True,
        )
        description_message = await user.listen(filters.text)
        if description_message.text == "/cancel_quiz":
            await title_message.reply(f"<b>{title}</b> Cancelled.", quote=True)
            return

        description = (
            description_message.text if description_message.text != "/skip" else ""
        )

        await title_message.reply(
            "You can start sending your quiz questions as polls (must be in <b>quiz mode</b>).\n"
            "When you are done use /save_quiz to save the quiz or /cancel_quiz to cancel it.",
            quote=True,
        )
        quiz = Quiz(title=title, description=description, questions=[])

        while True:
            question_message = await user.listen()

            if question_message.text == "/save_quiz":
                result = db_client.acmbDB.quizzes.insert_one(quiz.as_dict())
                quiz_preview = QuizPreview(quiz, result.inserted_id)
                db_client.acmbDB.users.update_one(
                    {"_id": user.id}, {"$push": {"quizzes": quiz_preview.as_dict()}}
                )
                await question_message.reply(f"Quiz <b>{title}</b> has been saved.")
                break

            elif question_message.text == "/cancel_quiz":
                await question_message.reply(
                    f"Quiz <b>{title}</b> has been cancelled", quote=True
                )
                break

            poll = question_message.poll

            if not poll:
                await question_message.reply(
                    "You must send the question as a poll to add it to the quiz.\n"
                    "To save the quiz or cancel it use /save_quiz or /cancel_quiz",
                    quote=True,
                )
                continue

            elif not poll.type == enums.PollType.QUIZ:
                await question_message.reply(
                    "The Poll must be of type quiz (choose quiz mode in poll creation panel).",
                    quote=True,
                )
                continue

            try:
                question = QuizQuestion(question_message)
            except ValueError:
                await question_message.reply(
                    "for the bot to get access to the solution of a forwarded quiz it must be closed.\n"
                    "if you are the creater of the poll, close it.\n"
                    "if you can't close it, create a new quiz in @QuizBot, forward all your quizzes to it, "
                    "save the quiz, take the quiz (just answer randomly), then forward the polls to me (this way they become closed)\n"
                    "You can also recreate them directly here if you want.",
                    quote=True,
                )
                await question_message.reply(question_message.poll, quote=True)
                continue

            quiz.add_question(question)
            await question_message.reply(
                "Question Added, you can send another question, /save_quiz or /cancel_quiz",
                quote=True,
            )

    @app.on_message(filters.command("my_quizzes"))
    async def handle_my_quizzes(app, message: Message):
        user = db_client.acmbDB.users.find_one({"_id": message.from_user.id})
        if not user:
            return await message.reply("send /start first")
        review_text = (
            "Your Quizzes:\n"
            if user["quizzes"]
            else "You don't have any quizzes, create some with /create_quiz !"
        )
        await message.reply(review_text, quote=True)
        for i, quiz in enumerate(user["quizzes"]):
            title, id, description, questions_count = (
                quiz["title"],
                quiz["_id"],
                quiz["description"],
                quiz["questions_count"],
            )
            await message.reply(
                f"{i+1}. <u><b>{title}</b><u>\t /edit_title_{id}\n\n"
                f"Description: {description or "No Description"}\t /edit_description_{id}\n\n"
                f"Number of questions: {questions_count}\t /edit_quiz_questions_{id}\n\n"
                f"/delete_quiz_{id}"
            )

    @app.on_message(filters.regex(r"^/delete_quiz_(\w+)$"))
    async def handle_delete_quiz(app, message):
        quiz_id = message.text.split("delete_quiz_")[1]
        quiz = db_client.acmbDB.quizzes.find_one({"_id": quiz_id})
        if not quiz:
            await message.reply(
                "Quiz not found, May be it is already deleted.", quote=True
            )
            return

        title = quiz["title"]
        await message.reply(
            f"Are you sure you want to delete quiz <b>{title}<b>? to confirm send /yes to cancel send /cancel or anything else.",
            quote=True,
        )
        confirmation_message = await message.from_user.listen()

        if not confirmation_message.text == "/yes":
            await confirmation_message.reply("Quiz Deletion Cancelled.", quote=True)
            return

        db_client.acmbDB.quizzes.delete_one({"_id": quiz_id})
        db_client.acmbDB.users.update_one(
            {"_id": message.from_user.id},
            {"$pull": {"quizzes": {"_id": quiz_id}}},
        )
        await confirmation_message.reply(
            f"Quiz <b>{title}</b> has been deleted succefully", quote=True
        )

    @app.on_message(filters.regex(r"^/edit_title_(\w+)$"))
    async def handle_edit_title(app, message):
        user = message.from_user
        quiz_id = message.text.split("edit_title_")[1]
        title = db_client.acmbDB.quizzes.find_one({"_id": quiz_id})["title"]
        await message.reply(
            f"changing the title of <b>`{title}`</b> quiz, send the new title, or /cancel to cancel"
        )
        title_message = await user.listen(filters.text)
        new_title = title_message.text
        if new_title == "/cancel":
            await title_message.reply("Changing title cancelld.", quote=True)
            return
        db_client.acmbDB.users.update_one(
            {"_id": user.id, "quizzes._id": quiz_id},
            {"$set": {"quizzes.$.title": new_title}},
        )
        db_client.acmbDB.quizzes.update_one(
            {"_id": quiz_id}, {"$set": {"title": new_title}}
        )
        await title_message.reply(
            f"Quiz title has been changed from {title} to <b>{new_title}</b> succefully."
        )

    @app.on_message(filters.regex(r"^/edit_description_(\w+)$"))
    async def handle_edit_description(app, message):
        user = message.from_user
        quiz_id = message.text.split("edit_description_")[1]
        quiz = db_client.acmbDB.quizzes.find_one({"_id": quiz_id})

        if not quiz:
            await message.reply("Quiz not found, may be it is deleted?", quote=True)
            return

        description = quiz["description"]
        title = quiz["title"]

        if description:
            await message.reply(
                f"Changing the description of <b>{title}</b> quiz.\n"
                f"Old description is `{description}`.\n"
                "Send the new description, or send /no_description to remove it.\n"
                "Send /cancel to cancel",
                quote=True,
            )

        else:
            await message.reply(
                f"Settig description for <b>{title}</b> quiz\n"
                "Send the description or send /cancel to cancel"
            )

        description_message = await user.listen(filters.text)

        if description_message.text == "/cancel":
            await message.reply("Editig description Cancelled.", quote=True)
            return

        new_description = (
            description_message.text
            if not description_message.text == "/no_description"
            else ""
        )

        db_client.acmbDB.users.update_one(
            {"_id": user.id, "quizzes._id": quiz_id},
            {"$set": {"quizzes.$.description": new_description}},
        )
        db_client.acmbDB.quizzes.update_one(
            {"_id": quiz_id}, {"$set": {"description": new_description}}
        )

        if new_description:
            await description_message.reply(
                f'Quiz {title} description has been changed from "{description}" to "{new_description}" succefully.',
                quote=True,
            )
        else:
            await description_message.reply(
                f"Quiz <b>{title}</b> description has been removed.", quote=True
            )

    @app.on_message(filters.regex(r"^/edit_quiz_questions_(\w+)$"))
    async def handle_edit_quiz_questions(app, message):
        print("Called")
        quiz_id = message.text.split("edit_quiz_questions_")[1]
        quiz = db_client.acmbDB.quizzes.find_one({"_id": quiz_id})
        if not quiz:
            await message.reply("Quiz not found, May be it is deleted?")
            return

        title = quiz["title"]
        questions = quiz["questions"]
        questions_panel = (
            f"<b>{title}</b>:\n"
            f"Number of questions: {len(questions)}\n"
            f"/add_questions_{quiz_id}\n"
        )

        for i, question in enumerate(questions):
            questions_panel += (
                f"{i+1}. {question['question']}\n"
                f"/edit_question_{i+1}_{quiz_id}\t/delete_question_{i+1}_{quiz_id}\n"
            )

        await message.reply(questions_panel, quote=True)

    @app.on_message(filters.regex(r"^/edit_question_([0-9]*)_(\w+)$"))
    async def handle_edit_question(app, message):
        parts = message.text.split("_")
        question_id, quiz_id = int(parts[2]), parts[3]

        quiz = db_client.acmbDB.quizzes.find_one({"_id": quiz_id})
        if not quiz:
            return await message.reply(
                "Quiz not found, may be it is deleted?", qoute=True
            )

        quiz_questions = quiz["questions"]
        if len(quiz_questions) < question_id:
            return await message.reply(
                f"Quiz {quiz['title']} contains {len(quiz_questions)} questions, "
                f"you requested to edit question number {question_id} which doesn't exist"
            )

        question = quiz_questions[question_id - 1]
        options = question["options"]
        question_panel = (
            f"<b>{quiz['title']}</b>:\n"
            f"{question_id}. {question['question']}\n"
            f"/add_options_{question_id}_{quiz_id}\t/delete_question_{question_id}_{quiz_id}\n"
        )

        correct_options_ids = []

        for i, option in enumerate(options):
            question_panel += (
                f"{i+1}.  {option['text']}\n"
                f"/edit_option_{i+1}\t/delete_option_{i+1}\n"
            )
            if option["is_correct"]:
                correct_options_ids.append(i)

        if not correct_options_ids:
            return await message.reply("Error: This Question has no correct option")
        if len(correct_options_ids) > 1:
            return await message.reply(
                "Error: This Question has more than one correct option"
            )

        correct_option_id = correct_options_ids[0]

        question_panel += (
            f"Correct option: {correct_option_id + 1}\t/change_correct_option"
        )

        await message.reply(question_panel, quote=True)
        await message.reply("Go back with /back, exit with /exit")

        while True:
            user_command = await message.from_user.listen(filters.text)

            if user_command.text == "/back":
                message.text = f"/edit_quiz_questions_{quiz_id}"
                return await handle_edit_quiz_questions(app, message)

            elif user_command.text == "/exit":
                await user_command.reply("Exited.", quote=True)
                return

            elif user_command.text == f"/add_options_{question_id}_{quiz_id}":
                await handle_add_options(app, user_command)

            elif user_command.text.startswith("/edit_option_"):
                option_id = user_command.text.split("_")[2]
                if not option_id.isnumeric():
                    await user_command.reply(
                        "the command is invalid, please just click on the options don't type them yourself"
                    )
                    continue

                option_id = int(option_id)
                if option_id > len(options):
                    await user_command.reply(
                        f"There is no option {option_id}, question {question_id} only has {len(quiz_questions)} questions."
                    )
                    continue

                option_text = question["options"][int(option_id) - 1]["text"]
                await user_command.reply(
                    f"Send new value for the option `{option_text}`", quote=True
                )
                updated_option = await user_command.from_user.listen(filters.text)
                update = {
                    "$set": {
                        f"questions.{question_id-1}.options.{option_id-1}.text": updated_option.text
                    }
                }
                result = db_client.acmbDB.quizzes.update_one({"_id": quiz_id}, update)
                await user_command.reply(
                    f"matched: {result.matched_count}\nmodified: {result.modified_count}"
                )
                await user_command.reply(
                    f"Option {option_id} has been edited succefully.", quote=True
                )

            elif user_command.text.startswith("/delete_option_"):
                option_id = user_command.text.split("_")[2]
                if not option_id.isnumeric():
                    await user_command.reply(
                        "the command is invalid, please just click on the options don't type them yourself"
                    )
                    continue

                option_id = int(option_id)
                if option_id > len(options):
                    await user_command.reply(
                        f"There is no option {option_id}, question {question_id} only has {len(quiz_questions)} questions."
                    )
                    continue

                if option_id - 1 == correct_option_id:
                    await user_command.reply(
                        f"You can't delete option {option_id} because it is the correct option!\n"
                        "to change that send /change_correct_option"
                    )
                    continue

                option_text = question["options"][int(option_id) - 1]["text"]
                await user_command.reply(
                    f"Are You sure you want to delete option {option_id}: {option_text}?\n"
                    "send /yes to confirm, /cancel or anything else to cancel",
                    quote=True,
                )

                confirmation_message = await user_command.from_user.listen(filters.text)
                if confirmation_message.text != "/yes":
                    await confirmation_message.reply("Option delteion cancelled")
                    continue

                null_update = {
                    "$unset": {f"questions.{question_id-1}.options.{option_id-1}": 1}
                }
                db_client.acmbDB.quizzes.update_one({"_id": quiz_id}, null_update)

                pull_update = {"$pull": {f"questions.{question_id-1}.options": None}}

                result = db_client.acmbDB.quizzes.update_one(
                    {"_id": quiz_id}, pull_update
                )

                await confirmation_message.reply(
                    f"Option {option_id} deleted succefully."
                )
                await confirmation_message.reply(
                    f"matched: {result.matched_count}\nmodified: {result.modified_count}"
                )

            elif user_command.text == "/change_correct_option":
                while True:
                    await user_command.reply(
                        "Choose the Correct option:\n"
                        f'{"\n".join([f"/option_{i}" for i in range(1, len(options)+1)])}\n'
                        "send /cancel to cancel"
                    )
                    corr_op_message = await user_command.from_user.listen(filters.text)
                    corr_option = corr_op_message.text
                    valid_option = re.match(r"^/option_([1-9])$", corr_option)
                    if valid_option:
                        new_corr_option_id = int(valid_option.groups()[0])

                        unset_old_update = {
                            "$set": {
                                f"questions.{question_id - 1}.options.{correct_option_id}.is_correct": False
                            }
                        }
                        db_client.acmbDB.quizzes.update_one(
                            {"_id": quiz_id}, unset_old_update
                        )

                        set_new_update = {
                            "$set": {
                                f"questions.{question_id-1}.options.{new_corr_option_id-1}.is_correct": True
                            }
                        }
                        db_client.acmbDB.quizzes.update_one(
                            {"_id": quiz_id}, set_new_update
                        )
                        await message.reply(
                            f"option {new_corr_option_id} is the correct option now"
                        )
                        break

                    elif corr_option == "/cancel":
                        await corr_op_message.reply("Ok", quote=True)
                        break

                    await corr_op_message.reply(
                        "Invalid option, please choose from the list, "
                        "to cancel send /cancel",
                        quote=True,
                    )

            else:
                await user_command.reply(
                    "You are editing a question here, to exit question editing send /exit"
                )
                continue

            print("check")
            await handle_edit_question(app, message)
            return

    @app.on_message(filters.regex("^add_options_([0-9]+)_(/w+)$"))
    async def handle_add_options(app, message):
        print("Called")
        parts = message.text.split("_")
        question_id, quiz_id = int(parts[2]), parts[3]
        quiz = db_client.acmbDB.quizzes.find_one({"_id": quiz_id})

        if not quiz:
            await message.reply("Quiz not found, may be it is deleted?", quote=True)
            return

        questions = quiz["questions"]

        if question_id > len(questions):
            await message.reply(
                f"Quiz {quiz['title']} contains {len(questions)} questions, "
                f"there is no question number {question_id}, mat be it is deleted?",
                quote=True,
            )
            return

        await message.reply(
            f"Adding Options to question {question_id} of <b>{quiz['title']}</b>\n"
            "Send option text to be added, send /exit to exit",
            quote=True,
        )

        while True:
            option_message = await message.from_user.listen(filters.text)
            if option_message.text == "/exit":
                option_message.text = f"/edit_question_{question_id}_{quiz_id}"
                return await handle_edit_question(app, option_message)

            new_option = {
                "text": option_message.text,
                "is_correct": False,
                # "entities": option_message.entities,
            }

            update = {"$push": {f"questions.{question_id-1}.options": new_option}}
            result = db_client.acmbDB.quizzes.update_one({"_id": quiz_id}, update)
            await message.reply(
                f"matched: {result.matched_count}\nmodified:{result.modified_count}"
            )

            await option_message.reply(
                "option added\nsend /add_another_option to add another option, /exit or anything else to exit"
            )

            another = await option_message.from_user.listen(filters.text)
            if another.text == "/add_another_option":
                await another.reply("Send the option text, /exit to exit")
            else:
                another.text = f"/edit_question_{question_id}_{quiz_id}"
                await handle_edit_question(app, another)
                return

    @app.on_message(filters.regex(r"^/delete_question_([0-9]*)_(\w+)$"))
    async def handle_delete_questoin(app, message):
        parts = message.text.split("_")
        question_id, quiz_id = int(parts[2]), parts[3]
        quiz = db_client.acmbDB.quizzes.find_one({"_id": quiz_id})
        if not quiz:
            await message.reply("Quiz not found, may be it is deleted?", quote=True)
            return

        questions = quiz["questions"]
        questions_count = len(questions)
        if question_id > questions_count:
            await message.reply(
                f"Quiz {quiz['title']} contain only {questions_count}, no question is number {question_id}"
            )

        question = questions[question_id - 1]
        await message.reply(
            f"Are you sure you want to delete question number {question_id} of quiz <b>{quiz['title']}</b> "
            f"that says `{question['question']}`?\n"
            "to confirm send /yes to cancel send /cancel or anythin else"
        )
        confirmation_message = await message.from_user.listen(filters.text)
        if confirmation_message.text != "/yes":
            await confirmation_message.reply("Cancelled")
        else:
            null_update = {"$unset": {f"questions.{question_id-1}": 1}}
            db_client.acmbDB.quizzes.update_one({"_id": quiz_id}, null_update)

            pull_update = {"$pull": {f"questions": None}}
            db_client.acmbDB.quizzes.update_one({"_id": quiz_id}, pull_update)

            review_update = {"$inc": {"quizzes.$.questions_count": -1}}
            db_client.acmbDB.users.update_one(
                {"_id": message.from_user.id, "quizzes._id": quiz_id}, review_update
            )

            await confirmation_message.reply(
                f"question {question_id} deleted succefully"
            )
            confirmation_message.text = f"/edit_quiz_questions_{quiz_id}"
            await handle_edit_quiz_questions(app, confirmation_message)

    @app.on_message(filters.regex(r"^/add_questions_(\w+)$"))
    async def handle_add_questions(app, message):
        quiz_id = message.text.split("add_questions_")[1]
        quiz = db_client.acmbDB.quizzes.find_one({"_id": quiz_id})
        if not quiz:
            return await message.reply("Quiz not found, may be it is deleted?")

        user = message.from_user

        await message.reply(
            "You can start sending your quiz questions as polls (must be in <b>quiz mode</b>).\n"
            "When you are done send /done",
            quote=True,
        )
        while True:
            question_message = await user.listen()

            if question_message.text == "/done":
                question_message.text = f"/edit_quiz_questions_{quiz_id}"
                return await handle_edit_quiz_questions(app, question_message)

            poll = question_message.poll

            if not poll:
                await question_message.reply(
                    "You must send the question as a poll to add it to the quiz.\n"
                    "To save the quiz or cancel it use /save_quiz or /cancel_quiz",
                    quote=True,
                )
                continue

            elif not poll.type == enums.PollType.QUIZ:
                await question_message.reply(
                    "The Poll must be of type quiz (choose quiz mode in poll creation panel).",
                    quote=True,
                )
                continue

            try:
                question = QuizQuestion(question_message)
            except ValueError:
                await question_message.reply(
                    "for the bot to get access to the solution of a forwarded quiz it must be closed.\n"
                    "if you are the creater of the poll, close it.\n"
                    "if you can't close it, create a new quiz in @QuizBot, forward all your quizzes to it, "
                    "save the quiz, take the quiz (just answer randomly), then forward the polls to me (this way they become closed)\n"
                    "You can also recreate them directly here if you want.",
                    quote=True,
                )
                continue

            quizzes_update = {"$push": {"questions": question.as_dict()}}
            db_client.acmbDB.quizzes.update_one({"_id": quiz_id}, quizzes_update)

            review_update = {"$inc": {"quizzes.$.questions_count": 1}}
            db_client.acmbDB.users.update_one(
                {"_id": user.id, "quizzes._id": quiz_id}, review_update
            )

            await question_message.reply(
                "Question Added, you can send another question or send /done when you are done.",
                quote=True,
            )

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
