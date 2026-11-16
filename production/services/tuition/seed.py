import asyncio
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert

from common import Session
from tuition.models import Invoice, Student


async def seed():
    async with Session.begin() as session:
        names = ("Nguyễn Văn An", "Trần Thanh Bình", "Lê Minh Châu", "Phạm Ngọc Dung")
        for number, name in enumerate(names, 1):
            student_id = UUID(f"20000000-0000-0000-0000-{number:012d}")
            await session.execute(insert(Student).values(id=student_id, mssv=f"5220000{number}", full_name=name).on_conflict_do_nothing())
            if number <= 3:
                await session.execute(insert(Invoice).values(id=UUID(f"10000000-0000-0000-0000-{number:012d}"), student_id=student_id, amount=6000000, status="PAID" if number == 3 else "UNPAID").on_conflict_do_nothing())


if __name__ == "__main__":
    asyncio.run(seed())
