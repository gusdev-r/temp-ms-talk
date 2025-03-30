import json


class ProcessFormQuestionService:

    def process_logic(self, form_questions):
        if form_questions:
            print(f"Form questions receive from RBMQ: {json.dumps(form_questions)}")
            return True
        else:
            print("Something went wrong receiving the data from RBMQ")
            return False
