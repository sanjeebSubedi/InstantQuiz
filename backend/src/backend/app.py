from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import router as quizzes_router
from backend.core.config import config
from backend.storage import db


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(quizzes_router)


@app.get("/")
def read_root():
    return {"Hello": "World"}