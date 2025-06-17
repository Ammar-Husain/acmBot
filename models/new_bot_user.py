class NewBotUser:
    def __init__(self, id):
        self.id = id

    def as_dict(self):
        return {"_id": self.id, "quizzes": [], "teams": [], "sets": []}
