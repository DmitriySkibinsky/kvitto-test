import json

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Payment, Tariff
from app.schemas.payment import PaymentCreate

PROMO_CODE = "KVITTO10"


def make_schedule(amount: int, months: int) -> list[int]:
    base, remainder = divmod(amount, months)
    return [base + (1 if i < remainder else 0) for i in range(months)]


async def create_payment(
    session: AsyncSession, data: PaymentCreate, idempotency_key: str | None
) -> tuple[Payment, bool]:
    if idempotency_key:
        existing = await session.scalar(
            select(Payment).where(Payment.idempotency_key == idempotency_key)
        )
        if existing:
            return existing, True

    tariff = await session.get(Tariff, data.tariff_id)
    if not tariff:
        raise HTTPException(status_code=404, detail="Tariff not found")

    discount = 0
    if data.promo_code is not None:
        if data.promo_code.upper() != PROMO_CODE:
            raise HTTPException(status_code=422, detail="Unknown promo code")
        discount = tariff.price * 10 // 100

    amount = tariff.price - discount
    schedule = None
    if data.method == "installment":
        schedule = make_schedule(amount, data.installment_months)

    payment = Payment(
        status="pending",
        tariff_id=tariff.id,
        amount=amount,
        discount=discount,
        method=data.method,
        installment_months=data.installment_months,
        schedule=json.dumps(schedule) if schedule else None,
        email=str(data.email),
        idempotency_key=idempotency_key,
    )
    session.add(payment)
    await session.commit()
    await session.refresh(payment)
    return payment, False
