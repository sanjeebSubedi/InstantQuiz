from pydantic import BaseModel, Field, field_validator


class QuizCreateRequest(BaseModel):
    topic: str = Field(min_length=1, description="Topic to generate a quiz for")

    @field_validator("topic")
    @classmethod
    def _strip_topic(cls, value):
        return value.strip()


class Question(BaseModel):
    section_index: int
    question: str
    options: list[str]
    correct_answer: str
    source_url: str


class QuizCreateResponse(BaseModel):
    job_id: str
    status: str


class QuizJobResponse(BaseModel):
    job_id: str
    topic: str
    status: str
    questions: list[Question] | None = None
    error: str | None = None