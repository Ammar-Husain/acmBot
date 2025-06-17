from typing import Union

from pyrogram import enums


class QuizQuestion:
    def __init__(self, message, media=[]):
        poll = message.poll
        if not poll:
            raise TypeError("Message passed to QuizQuestion must contain a poll")

        if not poll.type == enums.PollType.QUIZ:
            raise TypeError(
                "The poll in the message passed to QuizQuestion must be of a quiz type"
            )

        if poll.correct_option_id is None:
            raise ValueError(
                "In order for the bot to get access to the correct option of the poll, the poll must either:\n"
                "1. Be sent in the bot chat (not forwared).\n"
                "2. Be closed (voted or expired).\n"
                "Tell the user to solve it or retype it."
            )

        self.question: str = poll.question
        self.options: list[dict] = []
        for option in enumerate(poll.options):
            option = option[1]
            self.options.append({"text": option.text, "is_correct": False})
        self.options[poll.correct_option_id]["is_correct"] = True
        self.explanation: Union[str, None] = poll.explanation
        self.media = media

    def as_dict(self):
        return {
            "question": self.question,
            "options": self.options,
            "explanation": self.explanation,
            "media": self.media,
        }
