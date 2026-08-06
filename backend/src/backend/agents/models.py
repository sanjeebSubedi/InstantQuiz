from pydantic import BaseModel


class QuizOutline(BaseModel):
    section_breadcrumb: str
    question_count: int
    difficulty: str
    reason: str


class QuestionsResponse(BaseModel):
    section_index: int
    question: str
    options: list[str]
    correct_answer: str
    explanation: str
