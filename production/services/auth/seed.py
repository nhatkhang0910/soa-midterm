import asyncio
import os
from pwdlib import PasswordHash
from sqlalchemy.dialects.postgresql import insert
from common import Session, engine
from auth.models import User


async def seed():
    hashed = PasswordHash.recommended().hash(os.environ["DEMO_PASSWORD"])
    async with Session.begin() as session:
        for number, username, name, phone in [(1, "an", "Nguyễn Văn An", "0901234567"), (2, "binh", "Trần Thanh Bình", "0902345678")]:
            await session.execute(insert(User).values(
                id=f"00000000-0000-0000-0000-{number:012d}", username=username,
                password_hash=hashed, full_name=name, phone=phone,
                email=os.getenv(f"DEMO_EMAIL_{username.upper()}", f"{username}@example.test"),
            ).on_conflict_do_nothing(index_elements=[User.id]))
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
