from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import select

from app.db.session import SessionLocal, engine
from app.models import Base, Tariff
from app.api.routes import router


TARIFFS = [
    ("basic", 990_000),
    ("standard", 1_990_000),
    ("premium", 2_990_000),
]


async def seed_tariffs():
    async with SessionLocal() as session:
        for title, price in TARIFFS:
            exists = await session.scalar(select(Tariff).where(Tariff.title == title))
            if not exists:
                session.add(Tariff(title=title, price=price))
        await session.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await seed_tariffs()
    yield
    await engine.dispose()


app = FastAPI(title="Kvitto Payment API", lifespan=lifespan)
app.include_router(router)
