import re

from pyrogram import enums, filters

from methods.common import MEDIA_CHAT, user_is_quiz_owner, users_only
from models import QuizQuestion


def allow_external(_, __, update):
    return (
        not "media" in update.text
        and not "explanation" in update.text
        and not "delete_question"
    )


allow_external_filter = filters.create(allow_external)


@users_only
async def edit_quiz_questions(message, db_client):
    quiz_id = message.text.split("edit_quiz_questions_")[1]
    quiz = db_client.acmbDB.quizzes.find_one({"_id": quiz_id})
    if not quiz:
        await message.reply("Quiz not found, May be it is deleted?")
        return

    user = message.from_user
    if not user_is_quiz_owner(user.id, quiz_id, db_client):
        return await message.reply("Only quiz owner can do this")

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
            f"/edit_question_{i+1}_{quiz_id}\n/delete_question_{i+1}_{quiz_id}\n\n"
        )

    await message.reply(questions_panel, quote=True)


@users_only
async def edit_question(message, db_client):
    parts = message.text.split("_")
    question_id, quiz_id = int(parts[2]), parts[3]

    quiz = db_client.acmbDB.quizzes.find_one({"_id": quiz_id})
    if not quiz:
        return await message.reply("Quiz not found, may be it is deleted?", qoute=True)

    user = message.from_user
    if not user_is_quiz_owner(user.id, quiz_id, db_client):
        return await message.reply("Only quiz owner can do this")

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
        f"/delete_question_{question_id}_{quiz_id}\n\n"
        f"/add_options_{question_id}_{quiz_id}\n\n"
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

    question_panel += (
        f"Correct option: {correct_option_id + 1}\t/change_correct_option\n\n"
    )

    explanation = question["explanation"]
    if explanation:
        question_panel += (
            f"Explanation: {explanation}\n/edit_explanation_{question_id}_{quiz_id}\n\n"
        )
    else:
        question_panel += f"Explanation: No Explanation\n/edit_explanation_{question_id}_{quiz_id}\n\n"

    media = question["media"]
    if media:
        media_text = [
            f"/media_{j} \n /delete_media_{i+1}_{question_id}_{quiz_id}\n"
            for i, j in enumerate(media)
        ]
        question_panel += f"Media:\n{"\n".join(media_text)}\n"
    else:
        question_panel += "Media: No Media\n"

    if len(media) < 3:
        question_panel += f"/add_media_{question_id}_{quiz_id}"

    await message.reply(question_panel, quote=True)
    await message.reply("Go back with /back, exit with /exit")

    while True:
        try:
            user_command = await user.listen(filters.text & allow_external_filter)
        except:
            return

        if user_command.text == "/back":
            user_command.text = f"/edit_quiz_questions_{quiz_id}"
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
            updated_option = await user.listen(filters.text)
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

            confirmation_message = await user.listen(filters.text)
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
                corr_op_message = await user.listen(filters.text)
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


@users_only
async def edit_question_explanation(message, db_client):
    user = message.from_user
    await user.stop_listening()
    parts = message.text.split("_")
    question_id, quiz_id = int(parts[2]), parts[3]
    quiz = db_client.acmbDB.quizzes.find_one({"_id": quiz_id})

    if not quiz:
        return await message.reply("Quiz not found")

    if not user_is_quiz_owner(user.id, quiz_id, db_client):
        return await message.reply("Only quiz owner can do this")

    if question_id > len(quiz["questions"]):
        return await message.reply(
            f"Question not found, quiz only contain {len(quiz['questions'])} questions"
        )

    await message.reply("Send new explanation\nsend /cancel to cancel")
    exp_message = await user.listen(filters.text)
    if exp_message.text == "/cancel":
        return await exp_message.reply("Cancelled", quote=True)

    exp = exp_message.text
    update = {"$set": {f"questions.{question_id-1}.explanation": exp}}
    db_client.acmbDB.quizzes.update_one({"_id": quiz_id}, update)

    await exp_message.reply("Explanation updated succefully.")
    exp_message.text = f"edit_question_{question_id}_{quiz_id}"
    await edit_question(exp_message, db_client)


@users_only
async def add_options(message, db_client):
    parts = message.text.split("_")
    question_id, quiz_id = int(parts[2]), parts[3]
    quiz = db_client.acmbDB.quizzes.find_one({"_id": quiz_id})

    if not quiz:
        await message.reply("Quiz not found, may be it is deleted?", quote=True)
        return

    user = message.from_user
    if not user_is_quiz_owner(user.id, quiz_id, db_client):
        return await message.reply("Only quiz owner can do this")

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
        option_message = await user.listen(filters.text)
        if option_message.text == "/exit":
            option_message.text = f"/edit_question_{question_id}_{quiz_id}"
            return await edit_question(option_message, db_client)

        new_option = {
            "text": option_message.text,
            "is_correct": False,
        }

        update = {"$push": {f"questions.{question_id-1}.options": new_option}}
        db_client.acmbDB.quizzes.update_one({"_id": quiz_id}, update)

        await option_message.reply(
            "option added\nsend /add_another_option to add another option, /exit or anything else to exit"
        )

        another = await user.listen(filters.text)
        if another.text == "/add_another_option":
            await another.reply("Send the option text, /exit to exit")
        else:
            another.text = f"/edit_question_{question_id}_{quiz_id}"
            await edit_question(another, db_client)
            return


@users_only
async def delete_question(message, db_client):
    parts = message.text.split("_")
    question_id, quiz_id = int(parts[2]), parts[3]
    quiz = db_client.acmbDB.quizzes.find_one({"_id": quiz_id})
    if not quiz:
        await message.reply("Quiz not found, may be it is deleted?", quote=True)
        return

    user = message.from_user
    if not user_is_quiz_owner(user.id, quiz_id, db_client):
        return await message.reply("Only quiz owner can do this")

    questions = quiz["questions"]
    questions_count = len(questions)
    if question_id > questions_count:
        return await message.reply(
            f"Question not found quiz {quiz['title']} contain only {questions_count}"
        )
    await user.stop_listening()
    question = questions[question_id - 1]
    await message.reply(
        f"Are you sure you want to delete question number {question_id} of quiz <b>{quiz['title']}</b> "
        f"that says `{question['question']}`?\n"
        "to confirm send /yes to cancel send /cancel or anythin else"
    )
    confirmation_message = await user.listen(filters.text)
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


@users_only
async def add_questions(message, db_client):
    quiz_id = message.text.split("add_questions_")[1]
    quiz = db_client.acmbDB.quizzes.find_one({"_id": quiz_id})
    if not quiz:
        return await message.reply("Quiz not found, may be it is deleted?")

    user = message.from_user

    if not user_is_quiz_owner(user.id, quiz_id, db_client):
        return await message.reply("Only quiz owner can do this")

    await message.reply(
        "You can start sending your quiz questions as polls (must be in <b>quiz mode</b>).\n"
        "You can send up to 3 photos to be send before the question\n"
        "When you are done send /done",
        quote=True,
    )
    photos_messages_ids = []
    while True:
        question_message = await user.listen()
        if question_message.photo:
            if len(photos_messages_ids) == 3:
                await question_message.reply(
                    "maximum 3 images per question, /unsave to be able to add."
                )
                continue
            photo_message = await question_message.forward(MEDIA_CHAT)
            photos_messages_ids.append(photo_message.id)
            await question_message.reply(
                "This photo has been saved for the next quiz\n"
                "if you send it accedentily you can /unsave it",
                quote=True,
            )
            continue

        if question_message.text == "/unsave":
            if photos_messages_ids:
                photos_messages_ids.pop(-1)
                await question_message.reply(
                    "The last photo has been removed, you can continue", quote=True
                )
                continue
            else:
                await question_message.reply(
                    "There is no photos to be unsaved, you can continue", quote=True
                )
                continue

        if question_message.text == "/done":
            question_message.text = f"/edit_quiz_questions_{quiz_id}"
            return await edit_quiz_questions(question_message, db_client)

        poll = question_message.poll

        if not poll:
            await question_message.reply(
                "You must send the question as a poll to add it to the quiz.\n"
                "If you are done send /done",
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
            question = QuizQuestion(question_message, media=photos_messages_ids)
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
        else:
            photos_messages_ids = []

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


@users_only
async def get_media(app, message):
    user = message.from_user
    image_message_id = int(message.text.split("_")[1])
    try:
        image_message = await app.get_messages(MEDIA_CHAT, image_message_id)
        image_owner_id = image_message.forward_origin.sender_user.id
    except Exception as e:
        return await message.reply("Media doesn't exist")

    if not user.id == image_owner_id:
        return await message.reply("This photo is not yours.")

    await image_message.copy(user.id)


@users_only
async def add_media(message, db_client):
    parts = message.text.split("_")
    question_id, quiz_id = int(parts[2]), parts[3]

    quiz = db_client.acmbDB.quizzes.find_one({"_id": quiz_id})
    if not quiz:
        return await message.reply("Quiz not found")

    user = message.from_user
    await user.stop_listening()

    if not user_is_quiz_owner(user.id, quiz_id, db_client):
        return await message.reply("Only quiz owner can do this")

    questions = quiz["questions"]
    if question_id > len(questions):
        return await message.reply(
            f"Question not found, quiz contain only {len(questions)} questions"
        )

    media = questions[question_id - 1]["media"]
    if len(media) >= 3:
        return await message.reply("Maximum 3 images per question, delete sum")

    new_media = []
    await message.reply("You can send a photo or send /cancel to cancel")
    while True:
        photo_message = await user.listen()

        if photo_message.text == "/cancel":
            return await photo_message.reply("Cancelled")
        if photo_message.text == "/done":
            break
        if not photo_message.photo:
            await photo_message.reply("send a photo, /done or /cancel only")
            continue

        if photo_message.forward_origin:
            await photo_message.reply(
                "please send the photo directly or hide sender name if you want to frowarded it from another chat."
            )
            continue

        saved_photo = await photo_message.forward(MEDIA_CHAT)
        new_media.append(saved_photo.id)
        if len(new_media) + len(media) < 3:
            await photo_message.reply(
                "You can send a new photo or send /done to save or /cancel to discard"
            )
        else:
            break

    if not new_media:
        return await message.reply("Ok.")

    for id in new_media:
        update = {"$push": {f"questions.{question_id-1}.media": id}}
        db_client.acmbDB.quizzes.update_one({"_id": quiz_id}, update)

    if len(new_media) == 1:
        await photo_message.reply("1 Photo added succefully", quote=True)
    else:
        await photo_message.reply(
            f"{len(new_media)} Photos added succefully", quote=True
        )

    photo_message.text = f"/edit_question_{question_id}_{quiz_id}"
    await edit_question(photo_message, db_client)


@users_only
async def delete_media(app, message, db_client):
    parts = message.text.split("_")
    (
        image_index,
        question_id,
        quiz_id,
    ) = (
        int(parts[2]),
        int(parts[3]),
        parts[4],
    )
    quiz = db_client.acmbDB.quizzes.find_one({"_id": quiz_id})
    if not quiz:
        return await message.reply("Quiz not found, may be it is deleted?", qoute=True)

    user = message.from_user
    if not user_is_quiz_owner(user.id, quiz_id, db_client):
        return await message.reply("Only quiz owner can do this")

    quiz_questions = quiz["questions"]
    if len(quiz_questions) < question_id:
        return await message.reply(
            f"Queston not found, Quiz {quiz['title']} contains {len(quiz_questions)} questions"
        )

    media = quiz_questions[question_id - 1]["media"]
    if image_index > len(media):
        return await message.reply("Media Not Found")

    await user.stop_listening()
    confirm = await user.ask(
        "Are you sure you want to delete this image?\n" "/yes\t/no"
    )
    if confirm.text != "/yes":
        return await confirm.reply("Cancelled")

    media_id = media.pop(image_index - 1)

    update = {"$set": {f"questions.{question_id-1}.media": media}}
    db_client.acmbDB.quizzes.update_one({"_id": quiz_id}, update)

    try:
        media_in_db = await app.get_messages(MEDIA_CHAT, media_id)
        await media_in_db.copy(
            MEDIA_CHAT,
            caption=f"{user.username}: {user.first_name} {user.last_name}: {user.id}",
        )
        await media_in_db.delete()
    except:
        pass

    await confirm.reply("Image deleted succefully", quote=True)
    confirm.text = f"/edit_question_{question_id}_{quiz_id}"
    await edit_question(confirm, db_client)
