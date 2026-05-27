from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, JSON


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    hashed_password: str


class Operator(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)
    platform: str              # myaffiliates | cellxpert | superpartners | affilka
    url: str
    credentials: dict = Field(default={}, sa_column=Column(JSON))
    active: bool = Field(default=True)
