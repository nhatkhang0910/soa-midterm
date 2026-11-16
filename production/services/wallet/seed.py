import asyncio
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert

from common import Session
from wallet.models import Wallet


async def seed():
    async with Session.begin() as session:
        for number in (1, 2):
            await session.execute(insert(Wallet).values(user_id=UUID(int=number), balance=10000000, reserved=0).on_conflict_do_nothing(index_elements=[Wallet.user_id]))


if __name__ == "__main__":
    asyncio.run(seed())
