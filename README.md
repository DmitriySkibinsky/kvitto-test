# Kvitto Payment API

FastAPI-тестовое: платежи онлайн-школы. Суммы хранятся только целым числом копеек.

## Запуск через Docker

```bash
docker compose up --build
```

API: http://localhost:8000
Swagger: http://localhost:8000/docs

Миграции Alembic запускаются автоматически перед стартом приложения.

## Локальный запуск

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

Для локального SQLite миграции используют `alembic.ini`.

## Тесты

```bash
pytest -q
```

## Примеры

```bash
curl http://localhost:8000/tariffs

curl -X POST http://localhost:8000/payments \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: demo-1" \
  -d '{"tariff_id":2,"email":"student@example.com","method":"installment","installment_months":3,"promo_code":"kvitto10"}'

curl http://localhost:8000/payments/1
```

Webhook требует `X-Signature`: HMAC-SHA256 от точного тела запроса с `WEBHOOK_SECRET`.

## Структура

- `app/models` — SQLAlchemy-модели.
- `app/schemas` — Pydantic v2-схемы.
- `app/services` — бизнес-логика суммы и рассрочки.
- `app/api` — HTTP API.
- `alembic` — миграции.
- `tests` — pytest/httpx тесты.
