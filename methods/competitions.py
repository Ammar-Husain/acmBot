import base64
import re
from datetime import datetime, timedelta

import nanoid
from pymongo.mongo_client import asyncio
from pyrogram import filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import (
    Chat,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    PollOption,
)

from methods.common import check_bot_status_in_chat, get_media_chat, users_only
from methods.teams import my_sets


async def is_admin(chat_or_id, user_id, app=None):
    try:
        if app and isinstance(chat_or_id, int):
            user_as_member = await app.get_chat_member(chat_or_id, user_id)
        elif isinstance(chat_or_id, Chat):
            user_as_member = await chat_or_id.get_member(user_id)
        else:
            return False
        print(user_as_member.status)
        return user_as_member.status in [
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
        ]
    except Exception as e:
        print(f"Error: {e}")
        return False


@users_only
async def start_competition(app, message, db_client):
    user = message.from_user
    await message.reply(
        "Do you have the quiz and teams set (for teams competitions) ready?\n"
        "/yes \t /no",
        quote=True,
    )
    ready_message = await user.listen(filters.private & filters.text)
    if ready_message.text != "/yes":
        return await ready_message.reply(
            "prepare the quiz and teams set first", quote=True
        )

    quizzes = db_client.acmbDB.users.find_one({"_id": user.id}, {"quizzes": 1})[
        "quizzes"
    ]
    quizzes_preview = "\n".join(
        [quiz["title"] + f":\t /quiz_{quiz['_id']}" for quiz in quizzes]
    )

    await message.reply(
        "Alright!, send the quiz of the competition\n"
        "Your quizzes:\n"
        f"{quizzes_preview}\n\n"
        "You can use public quizzes of others too.\n"
        "Send /cancel to cancel the competition"
    )

    while True:
        quiz_message = await user.listen(filters.private & filters.text)
        if quiz_message.text == "/cancel":
            return await quiz_message.reply("Cancelld", quote=True)

        parts = quiz_message.text.split("_")
        if len(parts) != 2:
            await quiz_message.reply(
                "Invalid quiz, please choose one of your quizzes or ensure the quiz link is valid.\n"
                "To cancel the competition send /cancel"
            )
            continue

        quiz_id = parts[1]
        quiz = db_client.acmbDB.quizzes.find_one({"_id": quiz_id})
        if not quiz:
            await quiz_message.reply(
                "Quiz not found, may be it is deleted?\tTry again\nsend /cancel to cancel",
                quote=True,
            )
            continue
        else:
            await message.reply(f"quiz <b>{quiz['title']}</b> choosed.")
            break

    while True:
        await message.reply(
            "Send the time available for each question in senconds (minimum: 60, maximum: 300)\n"
            "send /cancel to cancel"
        )
        time_message = await user.listen(filters.private & filters.text)
        time = time_message.text
        if time == "/cancel":
            return await time_message.reply("Cancelld", quote=True)
        elif not (time.isnumeric() and 60 <= int(time) <= 300):
            await time_message.reply("Time must be a number between 60 and 300")
            continue
        else:
            await time_message.reply(f"Each question will last for {time} second.")
            break

    while True:
        await message.reply(
            "Do you want the competition to be in /solo or /teams mode?\n"
            "to cancel send /cancel"
        )
        mode_message = await user.listen(filters.private & filters.text)
        if mode_message.text == "/cancel":
            return await mode_message.reply("Cancelld", quote=True)
        elif mode_message.text == "/solo":
            # await mode_message.reply("Solo mode is selected")
            # return await solo_competition_button(mode_message, quiz_id, time)
            await solo_competition_button(mode_message, quiz_id, time)
        elif mode_message.text == "/teams":
            await mode_message.reply("Teams mode is selected")
            return await teams_competition_button(
                app, mode_message, quiz_id, time, db_client
            )


async def solo_competition_button(message, quiz_id, question_time):
    return await message.reply("Not Implemented yet")
    query = f"{quiz_id},{question_time}"
    encoded_query = base64.b64encode(query.encode()).decode()
    start_button = InlineKeyboardButton(
        "Start Competition", switch_inline_query=encoded_query
    )
    keyboard = InlineKeyboardMarkup([[start_button]])
    await message.reply(
        "<b>Alright ! We are done.</b>\n"
        "When You are ready and every one is ready Press this button please",
        reply_markup=keyboard,
    )


async def teams_competition_button(app, message, quiz_id, question_time, db_client):
    user = message.from_user
    await message.reply(
        "Choose the set of teams those will participate in the competition", quote=True
    )
    await my_sets(message, db_client, for_comp=True)
    set_message = await user.listen(filters.private & filters.text)
    parts = set_message.text.split("set_")
    if not (len(parts) == 2 and parts[1].isnumeric()):
        await set_message.reply("Invalid set, please choose from the options")

    set_order = int(parts[1])
    user_data = db_client.acmbDB.users.find_one(
        {"_id": user.id}, {"sets": 1, "teams": 1}
    )
    user_sets = user_data["sets"]
    if set_order > len(user_sets):
        await set_message.reply("Invalid set, please choose from the options")

    _set = user_sets[set_order - 1]
    user_teams = user_data["teams"]
    invalid_teams = []
    for i, team_id in enumerate(_set["teams_ids"]):
        status = await check_bot_status_in_chat(app, team_id)
        admin_status = "Admin \U00002713"
        if status != admin_status:
            team_name = [
                team["team_name"] for team in user_teams if team["_id"] == team_id
            ]
            if not team_name:
                print("a deleted team is still in it's set")
                update = {"$pull": {"sets.$.teams_ids": team_id}}
                result = db_client.acmbDB.users.update_one(
                    {"_id": user.id, "sets._id": _set["_id"]}, update
                )
                print(
                    f"matched: {result.matched_count}\ndeleted: {result.modified_count}"
                )
                _set["teams_ids"].pop(i)
            else:
                invalid_teams.append({"name": team_name[0], "status": status})

    if invalid_teams:
        invalid_teams_review = "\n".join(
            [
                f"team: <b>{team["name"]}</b>, bot status: {team['status']}"
                for team in invalid_teams
            ]
        )
        await set_message.reply(
            "the Set contain ivnalid team(s) (groups doesn't exist or bot is not admin in their groups)\n\n"
            f"<b>summary</b>:\n{invalid_teams_review}\n\n"
            "/ignore them and start the competition with the valid teams only\n"
            "or /exit and fix them (recommended)"
        )
        choice_message = await user.listen(filters.private & filters.text)
        if choice_message.text != "/ignore":
            return await choice_message.reply("Exited", quote=True)

    query = f"{quiz_id},{_set["_id"]},{question_time}"
    query = base64.b64encode(query.encode()).decode()
    start_button = InlineKeyboardButton("Start Competition", switch_inline_query=query)
    keyboard = InlineKeyboardMarkup([[start_button]])
    await message.reply(
        "Alright ! We are done."
        "When You are ready and every one is ready Press this button please",
        reply_markup=keyboard,
    )


async def begin_solo_competition(message, quiz_id, question_time, db_client):
    user = message.from_user
    return


async def broadcast(app, chat_ids_or_messages, text):
    for id_or_message in chat_ids_or_messages:
        if isinstance(id_or_message, Message):
            await id_or_message.reply(text, quote=False)
        else:
            await app.send_message(id_or_message, text)


async def get_poll_result(app, chat_id, message_id):
    message = await app.get_messages(chat_id, message_id)
    votes = [option.voter_count for option in message.poll.options]
    maximum = max(votes)
    choosen_options_ids = [i for i, vote in enumerate(votes) if vote == maximum]
    return choosen_options_ids


async def begin_teams_competition(
    app, message, quiz_id, set_id, question_time, db_client, teams_results=[]
):
    comp_creator_id = message.from_user.id
    comp_chat = message.chat

    user_data = db_client.acmbDB.users.find_one(
        {"_id": message.from_user.id}, {"teams": 1, "sets": 1}
    )
    if not user_data:
        print(f"user {message.from_user.username} not found")
        return

    if not "sets" in user_data:
        return

    user_sets = user_data["sets"]
    _set = {}
    for i in user_sets:
        if i["_id"] == set_id:
            _set = i
            break
    if not _set:
        print("Set not found")
        return

    quiz = db_client.acmbDB.quizzes.find_one({"_id": quiz_id})
    if not quiz:
        print("quiz not found")
        return

    if not (question_time.isnumeric() and 60 <= int(question_time) <= 300):
        print("Invalid question time")
        return

    valid_groups_ids = [
        g_id for g_id in _set["teams_ids"] if await is_admin(g_id, "me", app=app)
    ]

    user_teams = user_data["teams"]
    valid_teams = [team for team in user_teams if team["_id"] in valid_groups_ids]
    print(valid_teams)

    stoped_at = len(teams_results[valid_teams[0]["_id"]]) if teams_results else 0
    question_time = int(question_time)
    questions = quiz["questions"][stoped_at:]
    q_count = len(quiz["questions"])

    ready_button = InlineKeyboardButton("Yes, I am ready!", callback_data="ready")
    ready_count_button = InlineKeyboardButton("No one is ready yet.", callback_data="t")
    keyboard = InlineKeyboardMarkup([[ready_button], [ready_count_button]])

    quiz_title = quiz["title"] if not teams_results else quiz["title"] + " - Continued"

    welcome_text = (
        "<b>Welcome Everyone!!\n\n</b>"
        "<b>Let's Start the Battle!</b>\n"
        "<b>ARE YOY READY?</b>\n\n"
        f"Our Competition today is on quiz <u><b>{quiz_title}</b></u>!!\n\n"
        "<u><b>Competition Rules</b></u>:\n\n"
        "1. Each question will be sended here as a text and in <b>your teams groups</b> (functoinal divisions) as a poll\n\n."
        f"2. <b>Your are allowed to discuss the question together</b> but you have to vote within the question time limit (In this case {question_time} seconds), <b>after which you can't vote</b>.\n\n"
        "3. The option that get the highest number of votes in your group team is <b>your group choice</b>, if correct your group get a point else <u><b>you lose a point</b></u>.\n\n"
        "4. If voting result was tie between more than one option, you lose the point even if one them was correct\n\n."
        "5. It is <b>prohibitied</b> to answer the question here or discuss here before the question is closed\n\n."
        "6. You can discuss and request more explanations here <u><b>between questions</b></u>\n\n."
    )

    if not teams_results:
        await message.reply(
            welcome_text,
            reply_markup=keyboard,
        )
        await asyncio.sleep(2)

    await message.reply(
        f"<u><b>Quiz Title</b></u>: <b>{quiz_title.title()}</b>.\n\n"
        f"<u><b>Questoins Number: </b></u>: <b>{q_count} Questions</b>.\n\n"
        f"<u><b>Description</b></u>:  <b>{quiz['description'].title()}</b>.\n\n"
        f"<u><b>Time Per Question</b></u>: <b>{question_time} seconds.</b>\n\n"
        "<b>GOOD LUCK!</b>",
        quote=False,
    )

    if teams_results:
        await message.reply(
            f"Last Time we stopped at question {stoped_at}!, now we will continue."
        )

    await asyncio.sleep(3)
    await message.reply(
        "When everyone is ready <b>any admin</b> can send /start_competition to start\n\n"
        "To pause the competition after starting, just send /pause",
        quote=False,
    )

    MAX_QUESTION_LEN = 255
    MAX_OPTION_LEN = 100
    MAX_MESSAGE_LEN = 4096
    SELLY_REPLIES = [
        "Sorry, Commands Are For Admins Only.",
        # "قلنا أدمنز بس معليش.",
        # "قلنا أدمنز بس معليش.",
        # "أدمنز بس دي لي منو 🙂",
        # "الله يهديك.",
        # "لقيتوها شغلة مش؟",
        # "الله يهديك.",
        # "يا محمد كمال عليك الله اتكلم مع الجماعة ديل، ما ممكن ياخي.",
        # "هوي والله أنا بمشي بخلي ليكم المسابقة دي حسي.",
        # "معاي منو؟",
    ]
    letters = [
        "A",
        "B",
        "C",
        "D",
        "E",
        "F",
        "G",
        "H",
        "I",
        "J",
        "K",
        "L",
        "M",
        "N",
        "O",
    ]
    OPTIONS_LETTERS = [f"**{letter})** " for letter in letters]

    while True:
        start_command_message = await comp_chat.listen(
            filters.command("start_competition")
        )
        sender_id = start_command_message.from_user.id
        if not sender_id == comp_creator_id and not await is_admin(
            comp_chat, sender_id
        ):
            await start_command_message.reply(SELLY_REPLIES[0], quote=True)
            if len(SELLY_REPLIES) > 1:
                SELLY_REPLIES.pop(0)
        else:
            break

    await start_command_message.reply("Alright! Starting the competition in:")

    if not teams_results:
        teams_results = dict()
        for team in valid_teams:
            teams_results[team["_id"]] = []

    await asyncio.sleep(1)
    media_chat = await get_media_chat(app)
    for question in questions:
        i = len(teams_results[valid_teams[0]["_id"]])
        await start_command_message.reply("3", quote=False)
        await asyncio.sleep(1)
        await start_command_message.reply("2", quote=False)
        await asyncio.sleep(1)
        await start_command_message.reply("1", quote=False)
        await asyncio.sleep(1)
        await start_command_message.reply("Go!", quote=False)

        # cleaning questoin from numbering i.e [i/j] or i.
        cleaned_question = re.sub(
            r"^\[?\s*\d*\s*/?\s*\d+\s*(\.|-|\)|\])", "", question["question"].strip()
        )

        # numbering if possible
        len_after_numbering = len(cleaned_question) + 9 + len(str(q_count)) * 2
        if len_after_numbering <= MAX_QUESTION_LEN:
            question_text = f"**[{i+1}/{q_count}]**. " + cleaned_question
        elif len_after_numbering - 4 <= MAX_QUESTION_LEN:
            question_text = f"[{i+1}/{q_count}]. " + cleaned_question
        elif len_after_numbering - 7 <= MAX_QUESTION_LEN:
            question_text = f"{i+1}/{q_count}. " + cleaned_question
        elif len(cleaned_question) + len(str(i + 1)) + 1 <= MAX_QUESTION_LEN:
            question_text = f"{i+1} " + cleaned_question
        else:
            question_text = cleaned_question

        # cleaning optoins from numbering
        cleaned_options = [
            re.sub(r"^\w\s{0,2}(\)|\.)", "", option["text"].strip())
            for option in question["options"]
        ]
        # adding numbering if possible
        cleaned_options = [
            (
                OPTIONS_LETTERS[i] + option
                if len(OPTIONS_LETTERS[i] + option) <= MAX_OPTION_LEN
                else option
            )
            for i, option in enumerate(cleaned_options)
        ]

        options = [PollOption(option) for option in cleaned_options]
        correct_option_id = [
            i for i, option in enumerate(question["options"]) if option["is_correct"]
        ][0]
        explanation = question["explanation"]

        close_date = datetime.now() + timedelta(seconds=question_time)
        round_polls = {}
        for team in valid_teams:
            if question["media"]:
                for image_id in question["media"]:
                    photo_message = await app.get_messages(media_chat.id, image_id)
                    await photo_message.copy(team["_id"], caption="")

            poll_message = await app.send_poll(
                team["_id"], question_text, options, close_date=close_date
            )
            await poll_message.reply(f"You have {question_time} seconds to vote!")

            round_polls[team["_id"]] = poll_message.id

        if question["media"]:
            for image_id in question["media"]:
                photo_message = await app.get_messages(media_chat.id, image_id)
                await message.reply_photo(
                    photo_message.photo.file_id, caption="", quote=False
                )

        question_message_text = f"{question_text}\n\n" + "\n\n".join(
            [option.text for option in options]
        )
        question_message = await message.reply(question_message_text, quote=False)
        await question_message.reply(
            "Vote in your groups!\n" f"You have {question_time} seconds!"
        )

        broadcast_groups = valid_groups_ids + [question_message]
        await asyncio.sleep(question_time / 2)
        await broadcast(app, broadcast_groups, f"{question_time // 2} seconds left!")

        await asyncio.sleep(question_time / 4)
        await broadcast(app, broadcast_groups, f"{question_time // 4} seconds left!")

        left_for_3 = (close_date - datetime.now()).seconds - 3
        print(left_for_3)
        await asyncio.sleep(left_for_3)

        await broadcast(app, broadcast_groups, "3 seconds left!")
        await asyncio.sleep(1)
        await broadcast(app, broadcast_groups, "2")
        await asyncio.sleep(1)
        await broadcast(app, broadcast_groups, "1")
        await asyncio.sleep(1)
        await broadcast(app, broadcast_groups, "Hands Up!")

        await asyncio.sleep(1)
        await broadcast(app, valid_groups_ids, "Results are in the group!")
        await asyncio.sleep(3)

        await question_message.reply(
            "<u><b>The Correct Answer is:</b></u>\n\n", quote=False
        )
        await asyncio.sleep(3)
        await question_message.reply("\U0001F941  " * 3, quote=False)
        await asyncio.sleep(3)
        correct_answer_message_text = (
            f"{OPTIONS_LETTERS[correct_option_id]} \U00002705\n\n"
            f"<b>{options[correct_option_id].text}</b>"
        )
        correct_answer_message = await question_message.reply(
            correct_answer_message_text, quote=False
        )
        await asyncio.sleep(1)
        if explanation:
            explanatoin_message_text = "<u><b>EXPLANATION:</b></u>\n\n" f"{explanation}"
            if len(explanatoin_message_text) <= MAX_MESSAGE_LEN:
                await correct_answer_message.reply(explanatoin_message_text)
            else:
                await correct_answer_message.reply("<u><b>EXPLANATION:</b></u>")
                await correct_answer_message.reply(explanation)

        await asyncio.sleep(1)

        results_message_text = f"<u><b>Round {i+1} Results: </b></u>\n\n"

        for team in valid_teams:
            result = await get_poll_result(app, team["_id"], round_polls[team["_id"]])
            if len(result) > 1 or result[0] != correct_option_id:
                teams_results[team["_id"]].append(-1)
            else:
                teams_results[team["_id"]].append(1)

        for team in sorted(
            valid_teams, key=lambda a: teams_results[a["_id"]][-1], reverse=True
        ):
            name = team["team_name"].upper()
            team_results = teams_results[team["_id"]]
            result = "+1" if team_results[-1] == 1 else "-1"
            results_message_text += f"<b>{name}</b>:\t\t <b>{result}</b> \U00002192\U00002192 {sum(team_results)}\n\n"

        results_message = await correct_answer_message.reply(results_message_text)
        await asyncio.sleep(1)

        if q_count - i == 1:
            break

        await results_message.reply(
            "When You are ready for the next question <u>an admin</u> can send /next \U0001F60A.\n\n",
            "You can also /pause the competition and continue anytime later.",
        )

        while True:
            next_command = await results_message.chat.listen(
                filters.command("next") | filters.command("pause")
            )
            sender_id = next_command.from_user.id
            if not sender_id == comp_creator_id and not await is_admin(
                comp_chat, sender_id
            ):
                await next_command.reply(SELLY_REPLIES[0], quote=True)
                if len(SELLY_REPLIES) > 1:
                    SELLY_REPLIES.pop(0)
            else:
                if "next" in next_command.text:
                    break
                else:
                    return await handle_competition_pause(
                        next_command,
                        comp_creator_id,
                        quiz_id,
                        set_id,
                        question_time,
                        teams_results,
                        db_client,
                    )

    sorted_teams = sorted(
        valid_teams, key=lambda a: sum(teams_results[a["_id"]]), reverse=True
    )
    highest_score = sum(teams_results[sorted_teams[0]["_id"]])
    firsts = [
        team["team_name"].upper()
        for team in sorted_teams
        if sum(teams_results[team["_id"]]) == highest_score
    ]

    await message.reply("<b>This Was the Last Question!!</b>", quote=False)
    await asyncio.sleep(3)

    await message.reply("<b>Are You Ready??</b>", quote=False)
    await asyncio.sleep(3)
    await message.reply("<b>RESULTS TIME!!</b>", quote=False)
    await asyncio.sleep(2)
    await message.reply("<b>And the Winning team is.....</b>", quote=False)
    await asyncio.sleep(1)
    await message.reply("\U0001F941", quote=False)
    await asyncio.sleep(2)
    await message.reply("\U0001F941", quote=False)
    await asyncio.sleep(2)
    await message.reply("\U0001F941", quote=False)
    await asyncio.sleep(2)

    if len(firsts) == 1:
        winning_team_message_text = (
            f"<b>{firsts[0]} 🎉 🎉 🎉</b> " "\n\n\n <b>CONGRATULATIONS 🫡</b>"
        )
    else:
        winning_team_message_text = (
            "<b>We Have A Tie!!</b> 🤯\n\n"
            "Congratulations To:\n\n"
            f"{"\n\n".join([ "<b>" + first + ' 🎉 🎉 🎉' + "</b>" for first in firsts])}"
        )

    await message.reply(winning_team_message_text, quote=False)

    await asyncio.sleep(2)

    results_text = "<u><b>END RESULTS</b></u>:\n\n"

    for i, team in enumerate(sorted_teams):
        results_text += f"<b>{i+1}. {team['team_name'].title()}: \t {sum(teams_results[team['_id']])} Points</b>.\n\n"

    end_results_message = await message.reply(results_text, quote=False)
    await asyncio.sleep(2)
    await end_results_message.reply("See You in the next Competition 🖐️")


async def handle_competition_pause(
    message, set_owner_id, quiz_id, set_id, question_time, teams_results, db_client
):
    teams_results = {str(id): results for id, results in teams_results.items()}
    question_time = str(question_time)
    data = {
        "_id": nanoid.generate(size=8),
        "set_owner_id": set_owner_id,
        "quiz_id": quiz_id,
        "set_id": set_id,
        "question_time": question_time,
        "teams_results": teams_results,
    }

    result = db_client.acmbDB.paused_compos.insert_one(data)
    data_id = result.inserted_id
    continue_button = InlineKeyboardButton(
        "Continue Competition", callback_data=f"continue_{data_id}"
    )
    keyboard = InlineKeyboardMarkup([[continue_button]])
    await message.reply(
        "Competition has been Paused, whenever you are ready to continue any admin can press this button.",
        reply_markup=keyboard,
    )
