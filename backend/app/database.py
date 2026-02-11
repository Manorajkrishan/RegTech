from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from datetime import datetime

from .config import settings

engine = create_async_engine(settings.db_url, echo=settings.debug)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()


class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    invoice_id = Column(String(50), nullable=True)
    supplier = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    amount_gbp = Column(Float, nullable=False)
    quantity = Column(Float, nullable=True)
    unit = Column(String(50), nullable=True)
    category = Column(String(100), nullable=True)
    emissions_kg_co2e = Column(Float, nullable=True)
    scope = Column(String(20), nullable=True)
    date = Column(String(20), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Report(Base):
    __tablename__ = "reports"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    scope1_kg = Column(Float, default=0)
    scope2_kg = Column(Float, default=0)
    scope3_kg = Column(Float, default=0)
    total_kg = Column(Float, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
