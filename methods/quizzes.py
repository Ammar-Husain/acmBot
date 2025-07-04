import os

from pyrogram import enums, filters
from pyrogram.types import PollOption

from methods.common import get_media_chat, user_is_quiz_owner, users_only
from models import Quiz, QuizPreview, QuizQuestion

if not os.getenv("PRODUCTION"):
    import dotenv

    ADMINS_LIST = dotenv.dotenv_values()["ADMINS_IDS"].split(",")
else:
    ADMINS_LIST = os.getenv("ADMINS_IDS", "").split(",")


@users_only
async def create_quiz(app, message, db_client):
    await message.reply(
        "Let's Create a new Quiz together!, send your new quizz title (the title will appear in the competations), or /cancel_quiz to cancel.",
        quote=True,
    )
    user = message.from_user
    while True:
        title_message = await user.listen(filters.private & filters.text)
        print(title_message.text)
        if title_message.text == "/cancel_quiz":
            await title_message.reply("Cancelled.", quote=True)
            return
        elif title_message.text.startswith("/"):
            await title_message.reply(
                "Send question tilte or cancel with /cancel", quote=True
            )
            continue
        break

    title = title_message.text
    await title_message.reply(f"Your new quiz title is <b>{title}</b> !", quote=True)

    await title_message.reply(
        "Send a description for your quiz (will appear in the competations) or skip by sending /skip or cancel by /cancel_quiz",
        quote=True,
    )
    description_message = await user.listen(filters.private & filters.text)
    if description_message.text == "/cancel_quiz":
        await title_message.reply(f"<b>{title}</b> Cancelled.", quote=True)
        return

    description = (
        description_message.text if description_message.text != "/skip" else ""
    )

    await title_message.reply(
        "You can start sending your quiz questions as polls (must be in <b>quiz mode</b>).\n"
        "You can send up to 3 images before the poll to be sended before the question later\n"
        "When you are done use /save_quiz to save the quiz or /cancel_quiz to cancel it.",
        quote=True,
    )
    quiz = Quiz(title=title, description=description, questions=[])
    photos_messages_ids = []
    media_chat = await get_media_chat(app)
    while True:
        question_message = await user.listen(filters.private)
        if question_message.photo:
            if len(photos_messages_ids) == 3:
                await question_message.reply(
                    "maximum 3 images per question, /unsave to be able to add."
                )
                continue

            photo_message = await question_message.copy(
                media_chat.id, caption=str(user.id)
            )
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

        if question_message.text == "/save_quiz":
            db_client.acmbDB.quizzes.insert_one(quiz.as_dict())
            quiz_preview = QuizPreview(quiz)
            update = {"$push": {"quizzes": quiz_preview.as_dict()}}
            db_client.acmbDB.users.update_one({"_id": user.id}, update)
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
            await question_message.reply(question_message.poll, quote=True)
            continue
        else:
            photos_messages_ids = []

        quiz.add_question(question)
        await question_message.reply(
            "Question Added, you can send another question, /save_quiz or /cancel_quiz",
            quote=True,
        )


@users_only
async def my_quizzes(message, db_client):
    user = db_client.acmbDB.users.find_one(
        {"_id": message.from_user.id}, {"quizzes": 1}
    )
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
            f"Number of questions: {questions_count}\n"
            f"Edit questions: /edit_quiz_questions_{id}\n\n"
            f"Test qustions: /test_quiz_{id}\n\n"
            f"Export quiz link: /link_quiz_{id}\n\n"
            f"Delete: /delete_quiz_{id}"
        )


@users_only
async def delete_quiz(message, db_client):
    quiz_id = message.text.split("delete_quiz_")[1]
    quiz = db_client.acmbDB.quizzes.find_one({"_id": quiz_id})
    if not quiz:
        await message.reply("Quiz not found, May be it is already deleted.", quote=True)
        return

    user = message.from_user
    if not user_is_quiz_owner(user.id, quiz_id, db_client):
        return await message.reply("Only quiz owner can do this")

    title = quiz["title"]
    await message.reply(
        f"Are you sure you want to delete quiz <b>{title}</b>?\n"
        "to confirm send /yes to cancel send /cancel or anything else.",
        quote=True,
    )
    confirmation_message = await user.listen(filters.private & filters.text)

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


@users_only
async def edit_title(message, db_client):
    user = message.from_user
    quiz_id = message.text.split("edit_title_")[1]
    title = db_client.acmbDB.quizzes.find_one({"_id": quiz_id})["title"]
    await message.reply(
        f"changing the title of <b>`{title}`</b> quiz, send the new title, or /cancel to cancel"
    )

    user = message.from_user
    if not user_is_quiz_owner(user.id, quiz_id, db_client):
        return await message.reply("Only quiz owner can do this")

    title_message = await user.listen(filters.private & filters.text)
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


@users_only
async def edit_description(message, db_client):
    user = message.from_user
    quiz_id = message.text.split("edit_description_")[1]
    quiz = db_client.acmbDB.quizzes.find_one({"_id": quiz_id})

    if not quiz:
        await message.reply("Quiz not found, may be it is deleted?", quote=True)
        return

    user = message.from_user
    if not user_is_quiz_owner(user.id, quiz_id, db_client):
        return await message.reply("Only quiz owner can do this")

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

    description_message = await user.listen(filters.private & filters.text)

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


@users_only
async def test_quiz(app, message, db_client):
    quiz_id = message.text.split("test_quiz_")[1]
    quiz = db_client.acmbDB.quizzes.find_one({"_id": quiz_id})
    if not quiz:
        return await message.reply("Quiz not found, may be it is deleted?")
    user = message.from_user
    if not user_is_quiz_owner(user.id, quiz_id, db_client):
        print(str(user.id))
        print(ADMINS_LIST)
        if not str(user.id) in ADMINS_LIST:
            return await message.reply("Only quiz owner can do this")

    questions = quiz["questions"]
    if not questions:
        await message.reply(
            f"This quiz is empty!, add some questions to it by /add_questions_{quiz_id}",
            quote=True,
        )
    media_chat = await get_media_chat(app)
    for question in questions:
        if question["media"]:
            for image_id in question["media"]:
                image_message = await app.get_messages(media_chat.id, image_id)
                await image_message.copy(message.chat.id, caption="")

        options = [PollOption(option["text"]) for option in question["options"]]
        correct_option_id = [
            i for i, option in enumerate(question["options"]) if option["is_correct"]
        ][0]
        quiz_type = enums.PollType.QUIZ
        await message.reply_poll(
            question["question"],
            options=options,
            type=quiz_type,
            correct_option_id=correct_option_id,
            explanation=question["explanation"],
        )


async def link_quiz(message):
    link = message.text.replace("link_", "")
    await message.reply(f"Your Quiz link is {link}")
