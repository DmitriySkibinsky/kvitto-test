import hashlib
import hmac
import json

import pytest


# -------------------------
# Payments
# -------------------------

@pytest.mark.asyncio
async def test_get_tariffs(client):
    response = await client.get("/tariffs")

    assert response.status_code == 200

    tariffs = response.json()

    assert len(tariffs) == 3
    assert tariffs[0]["title"] == "basic"
    assert tariffs[0]["price"] == 990_000
    assert tariffs[1]["title"] == "standard"
    assert tariffs[1]["price"] == 1_990_000
    assert tariffs[2]["title"] == "premium"
    assert tariffs[2]["price"] == 2_990_000


@pytest.mark.asyncio
async def test_create_payment_without_promo(client):
    response = await client.post(
        "/payments",
        json={
            "tariff_id": 2,
            "email": "a@example.com",
            "method": "card",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["status"] == "pending"
    assert data["tariff_id"] == 2
    assert data["amount"] == 1_990_000
    assert data["discount"] == 0
    assert data["method"] == "card"
    assert data["installment_months"] is None
    assert data["schedule"] is None
    assert data["email"] == "a@example.com"


@pytest.mark.asyncio
async def test_payment_amount_with_promo(client):
    response = await client.post(
        "/payments",
        json={
            "tariff_id": 2,
            "email": "a@example.com",
            "method": "card",
            "promo_code": "KVITTO10",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["amount"] == 1_791_000
    assert data["discount"] == 199_000


@pytest.mark.asyncio
async def test_promo_code_is_case_insensitive(client):
    response = await client.post(
        "/payments",
        json={
            "tariff_id": 2,
            "email": "a@example.com",
            "method": "card",
            "promo_code": "kViTtO10",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["amount"] == 1_791_000
    assert data["discount"] == 199_000


@pytest.mark.asyncio
async def test_unknown_promo_returns_422(client):
    response = await client.post(
        "/payments",
        json={
            "tariff_id": 1,
            "email": "a@example.com",
            "method": "card",
            "promo_code": "NOPE",
        },
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_nonexistent_tariff_returns_404(client):
    response = await client.post(
        "/payments",
        json={
            "tariff_id": 999,
            "email": "a@example.com",
            "method": "card",
        },
    )

    assert response.status_code == 404


# -------------------------
# Installment
# -------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("months", [3, 6, 12])
async def test_installment_schedule_length_and_sum(client, months):
    response = await client.post(
        "/payments",
        json={
            "tariff_id": 2,
            "email": "a@example.com",
            "method": "installment",
            "installment_months": months,
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["installment_months"] == months
    assert len(data["schedule"]) == months
    assert sum(data["schedule"]) == data["amount"]


@pytest.mark.asyncio
async def test_installment_remainder_goes_to_first_payment(client):
    response = await client.post(
        "/payments",
        json={
            "tariff_id": 2,
            "email": "a@example.com",
            "method": "installment",
            "installment_months": 3,
        },
    )

    assert response.status_code == 201

    schedule = response.json()["schedule"]

    assert schedule == [663_334, 663_333, 663_333]


@pytest.mark.asyncio
async def test_installment_requires_months(client):
    response = await client.post(
        "/payments",
        json={
            "tariff_id": 2,
            "email": "a@example.com",
            "method": "installment",
        },
    )

    assert response.status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize("months", [1, 2, 4, 5, 13])
async def test_invalid_installment_months_returns_422(client, months):
    response = await client.post(
        "/payments",
        json={
            "tariff_id": 2,
            "email": "a@example.com",
            "method": "installment",
            "installment_months": months,
        },
    )

    assert response.status_code == 422


# -------------------------
# Idempotency
# -------------------------

@pytest.mark.asyncio
async def test_idempotency_returns_same_payment(client):
    payload = {
        "tariff_id": 1,
        "email": "a@example.com",
        "method": "card",
    }

    first = await client.post(
        "/payments",
        json=payload,
        headers={"Idempotency-Key": "abc"},
    )

    second = await client.post(
        "/payments",
        json=payload,
        headers={"Idempotency-Key": "abc"},
    )

    assert first.status_code == 201
    assert second.status_code == 200

    assert second.json()["id"] == first.json()["id"]


@pytest.mark.asyncio
async def test_different_idempotency_keys_create_different_payments(client):
    payload = {
        "tariff_id": 1,
        "email": "a@example.com",
        "method": "card",
    }

    first = await client.post(
        "/payments",
        json=payload,
        headers={"Idempotency-Key": "key-1"},
    )

    second = await client.post(
        "/payments",
        json=payload,
        headers={"Idempotency-Key": "key-2"},
    )

    assert first.status_code == 201
    assert second.status_code == 201

    assert first.json()["id"] != second.json()["id"]


# -------------------------
# Payment by ID
# -------------------------

@pytest.mark.asyncio
async def test_get_payment_by_id(client):
    created = await client.post(
        "/payments",
        json={
            "tariff_id": 1,
            "email": "a@example.com",
            "method": "card",
        },
    )

    payment_id = created.json()["id"]

    response = await client.get(f"/payments/{payment_id}")

    assert response.status_code == 200
    assert response.json()["id"] == payment_id


@pytest.mark.asyncio
async def test_missing_payment_returns_404(client):
    response = await client.get("/payments/99999")

    assert response.status_code == 404


# -------------------------
# Webhook helpers
# -------------------------

async def signed_webhook(client, payload):
    body = json.dumps(
        payload,
        separators=(",", ":"),
    ).encode()

    signature = hmac.new(
        b"test-secret",
        body,
        hashlib.sha256,
    ).hexdigest()

    return await client.post(
        "/webhooks/bank",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Signature": signature,
        },
    )


# -------------------------
# Status transitions
# -------------------------

@pytest.mark.asyncio
async def test_pending_to_succeeded(client):
    created = await client.post(
        "/payments",
        json={
            "tariff_id": 1,
            "email": "a@example.com",
            "method": "card",
        },
    )

    payment_id = created.json()["id"]

    response = await signed_webhook(
        client,
        {
            "payment_id": payment_id,
            "status": "succeeded",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"result": "ok"}

    payment = await client.get(f"/payments/{payment_id}")

    assert payment.json()["status"] == "succeeded"


@pytest.mark.asyncio
async def test_pending_to_failed(client):
    created = await client.post(
        "/payments",
        json={
            "tariff_id": 1,
            "email": "a@example.com",
            "method": "card",
        },
    )

    payment_id = created.json()["id"]

    response = await signed_webhook(
        client,
        {
            "payment_id": payment_id,
            "status": "failed",
        },
    )

    assert response.status_code == 200

    payment = await client.get(f"/payments/{payment_id}")

    assert payment.json()["status"] == "failed"


@pytest.mark.asyncio
async def test_succeeded_to_refunded(client):
    created = await client.post(
        "/payments",
        json={
            "tariff_id": 1,
            "email": "a@example.com",
            "method": "card",
        },
    )

    payment_id = created.json()["id"]

    await signed_webhook(
        client,
        {
            "payment_id": payment_id,
            "status": "succeeded",
        },
    )

    response = await signed_webhook(
        client,
        {
            "payment_id": payment_id,
            "status": "refunded",
        },
    )

    assert response.status_code == 200

    payment = await client.get(f"/payments/{payment_id}")

    assert payment.json()["status"] == "refunded"


@pytest.mark.asyncio
async def test_invalid_status_transition_returns_409_and_does_not_change(
    client,
):
    created = await client.post(
        "/payments",
        json={
            "tariff_id": 1,
            "email": "a@example.com",
            "method": "card",
        },
    )

    payment_id = created.json()["id"]

    await signed_webhook(
        client,
        {
            "payment_id": payment_id,
            "status": "succeeded",
        },
    )

    response = await signed_webhook(
        client,
        {
            "payment_id": payment_id,
            "status": "failed",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "invalid_transition"

    payment = await client.get(f"/payments/{payment_id}")

    assert payment.json()["status"] == "succeeded"


@pytest.mark.asyncio
async def test_failed_payment_cannot_become_succeeded(client):
    created = await client.post(
        "/payments",
        json={
            "tariff_id": 1,
            "email": "a@example.com",
            "method": "card",
        },
    )

    payment_id = created.json()["id"]

    await signed_webhook(
        client,
        {
            "payment_id": payment_id,
            "status": "failed",
        },
    )

    response = await signed_webhook(
        client,
        {
            "payment_id": payment_id,
            "status": "succeeded",
        },
    )

    assert response.status_code == 409

    payment = await client.get(f"/payments/{payment_id}")

    assert payment.json()["status"] == "failed"


@pytest.mark.asyncio
async def test_refunded_payment_cannot_change_status(client):
    created = await client.post(
        "/payments",
        json={
            "tariff_id": 1,
            "email": "a@example.com",
            "method": "card",
        },
    )

    payment_id = created.json()["id"]

    await signed_webhook(
        client,
        {
            "payment_id": payment_id,
            "status": "succeeded",
        },
    )

    await signed_webhook(
        client,
        {
            "payment_id": payment_id,
            "status": "refunded",
        },
    )

    response = await signed_webhook(
        client,
        {
            "payment_id": payment_id,
            "status": "failed",
        },
    )

    assert response.status_code == 409

    payment = await client.get(f"/payments/{payment_id}")

    assert payment.json()["status"] == "refunded"


@pytest.mark.asyncio
async def test_webhook_for_missing_payment_returns_404(client):
    response = await signed_webhook(
        client,
        {
            "payment_id": 99999,
            "status": "succeeded",
        },
    )

    assert response.status_code == 404


# -------------------------
# HMAC
# -------------------------

@pytest.mark.asyncio
async def test_webhook_with_invalid_signature_returns_401(client):
    body = json.dumps(
        {
            "payment_id": 1,
            "status": "succeeded",
        },
        separators=(",", ":"),
    ).encode()

    response = await client.post(
        "/webhooks/bank",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Signature": "wrong-signature",
        },
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_webhook_without_signature_returns_401(client):
    response = await client.post(
        "/webhooks/bank",
        json={
            "payment_id": 1,
            "status": "succeeded",
        },
    )

    assert response.status_code == 401