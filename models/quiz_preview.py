from .quiz import Quiz


class QuizPreview:
    def __init__(self, quiz: Quiz):
        self._id = quiz.id
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
