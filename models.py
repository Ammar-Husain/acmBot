from typing import Union

import nanoid

ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"

from pyrogram import enums
from pyrogram.types import Message as TelegramMessage


class NewBotUser:
    def __init__(self, id):
        self.id = id

    def as_dict(self):
        return {
            "_id": self.id,
            "quiz_on_create": "",
            "quizzes": [],
        }


class QuizQuestionOption:
    def __init__(self, id, message: TelegramMessage):
        self.id = id
        self.text = message.text
        self.entities = message.entities

    def as_dict(self):
        return {"id": self.id, "text": self.text, "entities": self.entities}


class QuizQuestion:
    def __init__(self, message: TelegramMessage):
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
            self.options.append(
                {"text": option.text, "is_correct": False, "entities": option.entities}
            )
        self.options[poll.correct_option_id]["is_correct"] = True
        self.explanation: Union[str, None] = poll.explanation
        self.question_entities = poll.question_entities

    def as_dict(self):
        return {
            "question": self.question,
            "options": self.options,
            "explanation": self.explanation,
            "question_entities": self.question_entities,
        }


class Quiz:
    def __init__(
        self, title: str, description: str = "", questions: list[QuizQuestion] = []
    ):
        self.id = nanoid.generate(alphabet=ALPHABET, size=8)
        self.title = title
        self.description = description
        self.questions = questions

    def as_dict(self):
        questions = [question.as_dict() for question in self.questions]
        return {
            "_id": self.id,
            "title": self.title,
            "description": self.description,
            "questions": questions,
        }

    def add_question(self, question: QuizQuestion):
        if not isinstance(question, QuizQuestion):
            raise ValueError(
                f"question passed to add_question must be of type QuizQuestion, {type(question)} given instead"
            )

        self.questions.append(question)


class QuizPreview:
    def __init__(self, quiz: Quiz, id):
        self._id = id
        self.title = quiz.title
        self.description = quiz.description
        self.questions_count = len(quiz.questions)

    def as_dict(self):
        return {
            "_id": self._id,
            "title": self.title,
            "description": self.description,
            "questions_count": self.questions_count,
        }
