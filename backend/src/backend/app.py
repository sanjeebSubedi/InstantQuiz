from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.api.routes import router as quizzes_router
from backend.storage import db


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(lifespan=lifespan)

app.include_router(quizzes_router)


@app.get("/")
def read_root():
    return {"Hello": "World"}