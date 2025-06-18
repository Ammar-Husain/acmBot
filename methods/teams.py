import nanoid
from pyrogram import filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import ChannelInvalid, ChannelPrivate, UserNotParticipant
from pyrogram.types import KeyboardButton, ReplyKeyboardMarkup, RequestPeerTypeChat

from methods.common import check_bot_status_in_chat, users_only
from models.quiz import ALPHABET


@users_only
async def add_teams(app, message, db_client):
    user = message.from_user
    await message.reply(
        "Alright!, Let's add some teams.\n",
        "Ensure the bot is added to all teams groups and has access to messages.",
    )
    chat_criteria = RequestPeerTypeChat(is_bot_participant=True)
    request_group_button = KeyboardButton(
        text="Choose group", request_chat=chat_criteria
    )
    request_group_keyboard = ReplyKeyboardMarkup(
        [[request_group_button]], one_time_keyboard=True, resize_keyboard=True
    )
    i = 1
    teams = []
    while True:
        await message.reply(
            "Use the button to choose the Group of the new team or save and exit with /done\n"
            "To discared the added teams and exit send /cancel",
            reply_markup=request_group_keyboard,
        )

        group_message = await user.listen()
        if group_message.text == "/done":
            if not teams:
                await group_message.reply(
                    "No teams have been added, if you want to cancel send /cancel"
                )
                continue

            break
        if group_message.text == "/cancel":
            return await group_message.reply("Cancelled", quote=True)
        if not group_message.chats_shared:
            continue

        group = group_message.chats_shared.chats[0]
        bot_status = await check_bot_status_in_chat(app, group.chat_id)
        if bot_status != "Admin \U00002713":
            await group_message.reply("Make the Bot admin in this group first.")
            continue

        await message.reply(
            "What do you want this team to be called? (the name will be used in the competations)"
        )
        team_name_message = await user.listen(filters.text)
        team_name = team_name_message.text
        if team_name == "/cancel":
            return await team_name_message.reply("Cancelld", quote=True)

        teams.append(
            {"_id": group.chat_id, "group_name": group.name, "team_name": team_name}
        )
        print(f"New group id is {group.chat_id}")
        await team_name_message.reply(
            f"Team {team_name} has been added!\t"
            "You can now add another team, to save and exit send /done"
        )
        i += 1

    for team in teams:
        if db_client.acmbDB.users.find_one({"_id": user.id, "teams._id": team["_id"]}):
            filter = {"_id": user.id, "teams._id": team["_id"]}
            update = {
                "$set": {
                    "teams.$.group_name": team["group_name"],
                    "teams.$.team_name": team["team_name"],
                },
            }
            db_client.acmbDB.users.update_one(filter, update)
        else:
            update = {"$push": {"teams": team}}
            db_client.acmbDB.users.update_one(
                {"_id": user.id},
                update,
            )

    await group_message.reply("Your teams have been Added succefully")


@users_only
async def my_teams(app, message, db_client):
    user = message.from_user
    user_teams = db_client.acmbDB.users.find_one({"_id": user.id}, {"teams": 1})[
        "teams"
    ]
    if not user_teams:
        await message.reply("You don't have teams yet, add some with /add_teams")
        return
    teams_preview = "<b>YOUR TEAMS</b>:\n /add_teams\n\n"

    for i, team in enumerate(user_teams):
        status = await check_bot_status_in_chat(app, team["_id"])
        teams_preview += (
            f"{i+1}. <b>{team['team_name']}</b>:\n"
            f"group name: {team['group_name']}\n"
            f"Bot Staus: {status}\n"
            f"/delete_team_{i+1}\n\n"
        )

    await message.reply(teams_preview, quote=True)


@users_only
async def delete_team(message, db_client):
    team_order = message.text.split("delete_team_")[1]
    if not team_order.isnumeric():
        return await message.reply("Invalid command, team number is not a number")
    user = message.from_user
    team_order = int(team_order)
    user_teams = db_client.acmbDB.users.find_one({"_id": user.id}, {"teams": 1})[
        "teams"
    ]
    if team_order > len(user_teams):
        return await message.reply("Team doesn't exist.", quote=True)

    team = user_teams[team_order - 1]
    await message.reply(
        f"Are you sure you want to delete <b>{team['team_name']}</b> team?\n"
        "Send /yes to confirm or /no or anything else to cancel"
    )
    confirmation_message = await user.listen(filters.text)

    if not confirmation_message.text == "/yes":
        return await message.reply("Cancelled", quote=True)

    update = {"$pull": {"teams": {"_id": team["_id"]}}}
    db_client.acmbDB.users.update_one(
        {"_id": user.id, "teams._id": team["_id"]}, update
    )
    await message.reply(f"Team <b>{team['team_name']}</b> has been removed.")


@users_only
async def create_set(app, message, db_client):
    user = message.from_user
    user_teams = db_client.acmbDB.users.find_one({"_id": user.id}, {"teams": 1})[
        "teams"
    ]

    if not user_teams:
        return await message.reply(
            "To create a set, you must have teams first, add some with /add_teams"
        )

    await message.reply("What do you want to call the set?\n" "Send /cancel to cancel")

    name_message = await user.listen(filters.text)
    if name_message.text == "/cancel":
        return await name_message.reply("Cancelled", quote=True)
    set_name = name_message.text

    teams_preview = (
        "Note: If you can't see some teams here, this is because the bot is not an admin in the team group,"
        " make it an admin and the team will show up here\n\n"
        "Your Teams:\n"
    )

    admin_status = "Admin \U00002713"
    valid_teams = [
        team
        for team in user_teams
        if await check_bot_status_in_chat(app, team["_id"]) == admin_status
    ]
    for i, team in enumerate(valid_teams):
        teams_preview += f"{i+1}. <b>{team['team_name']}</b>:\n"

    await name_message.reply(
        "Send a message that just contains the numbers of the teams to add to the set, "
        "sperated by commas (e.g 2,4,6).\n"
        "Use the numbers in the next message\n"
        "to cancel send /cancel"
    )
    await name_message.reply(teams_preview)

    while True:
        indexes_message = await user.listen(filters.text)
        if indexes_message.text == "/cancel":
            return await indexes_message.reply("Cancelled", quote=True)

        parts = indexes_message.text.split(",")
        if [p for p in parts if not p.strip().isnumeric()]:
            await indexes_message.reply(
                "Invalid Format, the message must only contain the numbers of teams seperated by commas, no more no less",
                quote=True,
            )
            continue

        indexes = [int(p.strip()) - 1 for p in parts]
        print(f"valid teams length: {len(valid_teams)}, indexes: {indexes}")
        if [i for i in indexes if i >= len(valid_teams) or i < 0]:
            await indexes_message.reply("Please choose numbers from the list only")
            continue

        if [i for i in indexes if indexes.count(i) > 1]:
            await indexes_message.reply(
                "You have repeated a team number, you probably meant another team, so try again"
            )
            continue

        set_teams_names = [valid_teams[i]["team_name"] for i in indexes]

        await indexes_message.reply(
            f"{set_name} will contain the following teams: {set_teams_names}\n"
            "/confirm \t\t /cancel",
            quote=True,
        )
        confirmation_message = await user.listen(filters.text)
        if not confirmation_message.text == "/confirm":
            await confirmation_message.reply(
                "Try sending the numbers again or /cancel the set"
            )
            continue

        teams_set = {
            "_id": nanoid.generate(size=5, alphabet=ALPHABET),
            "name": set_name,
            "teams_ids": [valid_teams[i]["_id"] for i in indexes],
        }

        db_client.acmbDB.users.update_one(
            {"_id": user.id}, {"$push": {"sets": teams_set}}
        )
        await message.reply(
            f"the set <b>{name_message.text}</b> has been created succefully."
        )
        break


@users_only
async def my_sets(message, db_client, for_comp=False):
    user = message.from_user
    user_data = db_client.acmbDB.users.find_one(
        {"_id": user.id}, {"sets": 1, "teams": 1}
    )
    user_sets = user_data["sets"]
    if not user_sets:
        return await message.reply(
            "You don't have any sets right now, create some with /create_set"
        )

    user_teams = user_data["teams"]
    await message.reply("<b>YOUR SETS</b>:\n")
    for i, _set in enumerate(user_sets):
        set_teams = ", ".join(
            [
                team["team_name"]
                for team in user_teams
                if team["_id"] in _set["teams_ids"]
            ]
        )
        await message.reply(
            f"{i+1}. <b>{_set["name"]}</b>:\n"
            f'{f"/set_{i+1}\n" if for_comp else ""}'
            f"teams: {set_teams}.\n"
            f'{f"/delete_set_{i+1}" if not for_comp else ""}'
        )


@users_only
async def delete_set(message, db_client):
    user = message.from_user
    set_id = int(message.text.split("delete_set_")[1])
    user_sets = db_client.acmbDB.users.find_one({"_id": user.id}, {"sets": 1})["sets"]
    if not user_sets:
        return await message.reply("You don't have sets to delete.")
    if set_id > len(user_sets):
        return await message.reply("Set not found")

    _set = user_sets[set_id - 1]
    await message.reply(
        f"Are you sure you want to delete set <b>{_set['name']}</b>?\n" "/yes \t /no"
    )

    confirmation_message = await user.listen(filters.text)
    if confirmation_message.text != "/yes":
        return await confirmation_message.reply("Cancelled", quote=True)

    update = {"$pull": {"sets": {"_id": _set["_id"]}}}
    db_client.acmbDB.users.update_one({"_id": user.id}, update)
    await confirmation_message.reply(f"Set <b>{_set['name']}</b> deleted succefully.")
