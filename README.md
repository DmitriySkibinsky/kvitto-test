# Kvitto Payment API

FastAPI-тестовое: платежи онлайн-школы. Суммы хранятся только целым числом копеек.

## Конфигурация

Скопируй пример и при необходимости измени значения:

```bash
cp .env.example .env
```

Переменные в `.env`:

| Переменная | Описание |
|---|---|
| `POSTGRES_DB` | Имя БД Postgres |
| `POSTGRES_USER` | Пользователь Postgres |
| `POSTGRES_PASSWORD` | Пароль Postgres |
| `DATABASE_URL` | URL для SQLAlchemy (asyncpg в Docker) |
| `WEBHOOK_SECRET` | Секрет HMAC для `/webhooks/bank` |
| `APP_PORT` | Порт приложения на хосте (по умолчанию 8000) |

## Запуск через Docker

```bash
docker compose up --build
```

API: http://localhost:8000  
Swagger: http://localhost:8000/docs

Миграции Alembic запускаются автоматически перед стартом приложения.

Если менял пароль/пользователя БД и видишь `password authentication failed` — сбрось том:

```bash
docker compose down -v && docker compose up --build
```

## Локальный запуск

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate
pip install -r requirements.txt
# в .env укажи DATABASE_URL=sqlite+aiosqlite:///./kvitto.db
alembic upgrade head
uvicorn app.main:app --reload
```

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
