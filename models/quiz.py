import nanoid

ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"

from .quiz_question import QuizQuestion


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
