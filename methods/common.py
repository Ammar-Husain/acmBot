import os

if not os.getenv("PRODUCTION"):
    import dotenv

    MEDIA_CHAT = dotenv.dotenv_values()["MEDIA_CHAT"]
else:
    MEDIA_CHAT = os.getenv("MEDIA_CHAT")

from pymongo import MongoClient
from pyrogram.types import Message


def users_only(func):
    async def wrapper(*args, **kwargs):
        message = None
        db_client = None
        for arg in args:
            if isinstance(arg, Message):
                message = arg
            elif isinstance(arg, MongoClient):
                db_client = arg
        if message and db_client:
            user = db_client.acmbDB.users.find_one({"_id": message.from_user.id})
            if not user:
                return await message.reply("send /start first")

        return await func(*args, **kwargs)

    return wrapper


def user_is_quiz_owner(user_id, quiz_id, db_client):
    is_owner = db_client.acmbDB.users.find_one({"_id": user_id, "quizzes._id": quiz_id})
    return bool(is_owner)


from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import (
    ChannelIdInvalid,
    ChannelInvalid,
    ChannelPrivate,
    ChatIdInvalid,
    UserNotParticipant,
)


async def check_bot_status_in_chat(app, chat_id):
    status = "Not a member \U000026A0"
    try:
        bot_as_group_member = await app.get_chat_member(chat_id, "me")
        if bot_as_group_member.status == ChatMemberStatus.ADMINISTRATOR:
            status = "Admin \U00002713"
        else:
            status = "User \U000026A0 (<b>must be an Admin!</b>)"

    except ChannelPrivate:
        pass

    except (ChannelIdInvalid, ChannelInvalid, ChatIdInvalid):
        if str(chat_id).startswith("-100"):
            return await check_bot_status_in_chat(app, chat_id + 1000000000000)

    except UserNotParticipant:
        status = "Link broken delete this team and re add it please"

    return status
