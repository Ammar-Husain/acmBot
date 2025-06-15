import re

from pyrogram import enums, filters

from methods.quizzes import edit_quiz_questions
from models import QuizQuestion


async def edit_question(message, db_client):
    parts = message.text.split("_")
    question_id, quiz_id = int(parts[2]), parts[3]

    quiz = db_client.acmbDB.quizzes.find_one({"_id": quiz_id})
    if not quiz:
        return await message.reply("Quiz not found, may be it is deleted?", qoute=True)

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
            f"{i+1}.  {option['text']}\n" f"/edit_option_{i+1}\t/delete_option_{i+1}\n"
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

    question_panel += f"Correct option: {correct_option_id + 1}\t/change_correct_option"

    await message.reply(question_panel, quote=True)
    await message.reply("Go back with /back, exit with /exit")

    while True:
        user_command = await message.from_user.listen(filters.text)

        if user_command.text == "/back":
            message.text = f"/edit_quiz_questions_{quiz_id}"
            return await edit_quiz_questions(message, db_client)

        elif user_command.text == "/exit":
            await user_command.reply("Exited.", quote=True)
            return

        elif user_command.text == f"/add_options_{question_id}_{quiz_id}":
            await add_options(user_command, db_client)

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
            db_client.acmbDB.quizzes.update_one({"_id": quiz_id}, update)
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

            db_client.acmbDB.quizzes.update_one({"_id": quiz_id}, pull_update)

            await confirmation_message.reply(f"Option {option_id} deleted succefully.")

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

        await edit_question(message, db_client)
        return


async def add_options(message, db_client):
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
            return await edit_question(option_message, db_client)

        new_option = {
            "text": option_message.text,
            "is_correct": False,
            # "entities": option_message.entities,
        }

        update = {"$push": {f"questions.{question_id-1}.options": new_option}}
        db_client.acmbDB.quizzes.update_one({"_id": quiz_id}, update)

        await option_message.reply(
            "option added\nsend /add_another_option to add another option, /exit or anything else to exit"
        )

        another = await option_message.from_user.listen(filters.text)
        if another.text == "/add_another_option":
            await another.reply("Send the option text, /exit to exit")
        else:
            another.text = f"/edit_question_{question_id}_{quiz_id}"
            await edit_question(another, db_client)
            return


async def delete_question(message, db_client):
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

        await confirmation_message.reply(f"question {question_id} deleted succefully")
        confirmation_message.text = f"/edit_quiz_questions_{quiz_id}"
        await edit_quiz_questions(confirmation_message, db_client)


async def add_questions(message, db_client):
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
            return await edit_quiz_questions(question_message, db_client)

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
