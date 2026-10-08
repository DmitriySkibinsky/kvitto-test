import hashlib
import hmac
import json

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_session
from app.models import Payment, Tariff
from app.schemas.payment import BankWebhook, PaymentCreate, PaymentResponse, TariffResponse
from app.services.payments import create_payment

router = APIRouter()
ALLOWED_TRANSITIONS = {
    "pending": {"succeeded", "failed"},
    "succeeded": {"refunded"},
    "failed": set(),
    "refunded": set(),
}


def to_response(payment: Payment) -> PaymentResponse:
    return PaymentResponse(
        id=payment.id,
        status=payment.status,
        tariff_id=payment.tariff_id,
        amount=payment.amount,
        discount=payment.discount,
        method=payment.method,
        installment_months=payment.installment_months,
        schedule=json.loads(payment.schedule) if payment.schedule else None,
        email=payment.email,
        created_at=payment.created_at,
    )


@router.get("/tariffs", response_model=list[TariffResponse])
async def get_tariffs(session: AsyncSession = Depends(get_session)):
    return (await session.scalars(select(Tariff).order_by(Tariff.id))).all()


@router.post("/payments", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def create_payment_endpoint(
    data: PaymentCreate,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    session: AsyncSession = Depends(get_session),
):
    payment, existed = await create_payment(session, data, idempotency_key)
    response.status_code = status.HTTP_200_OK if existed else status.HTTP_201_CREATED
    return to_response(payment)

@router.get("/payments")
async def get_payments(
    email: str | None = Query(default=None),
    status: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
):
    query = select(Payment)

    if email is not None:
        query = query.where(Payment.email == email)

    if status is not None:
        query = query.where(Payment.status == status)

    result = await session.execute(query)
    payments = result.scalars().all()

    return payments


@router.get("/payments/{payment_id}", response_model=PaymentResponse)
async def get_payment(payment_id: int, session: AsyncSession = Depends(get_session)):
    payment = await session.get(Payment, payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    return to_response(payment)


@router.post("/webhooks/bank")
async def bank_webhook(
    data: BankWebhook,
    request: Request,
    x_signature: str | None = Header(default=None, alias="X-Signature"),
    session: AsyncSession = Depends(get_session),
):
    body = await request.body()
    expected = hmac.new(settings.webhook_secret.encode(), body, hashlib.sha256).hexdigest()
    if not x_signature or not hmac.compare_digest(x_signature, expected):
        raise HTTPException(status_code=401, detail="Invalid signature")

    payment = await session.get(Payment, data.payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    if data.status not in ALLOWED_TRANSITIONS[payment.status]:
        raise HTTPException(status_code=409, detail="invalid_transition")

    payment.status = data.status
    await session.commit()
    return {"result": "ok"}
