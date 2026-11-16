from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column
from common import Base


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    full_name: Mapped[str] = mapped_column(String(160))
    phone: Mapped[str] = mapped_column(String(24))
    email: Mapped[str] = mapped_column(String(254))
