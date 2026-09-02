# Phoenix Interior Hub

## Gemini Chatbot Setup

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Create a Gemini API key in Google AI Studio.

3. Create a local `.env` file in the project root:

```env
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-3.7-flash
CHATBOT_ENABLED=True
CHATBOT_MAX_HISTORY=8
CHATBOT_MAX_MESSAGE_LENGTH=750
```

4. Run migrations:

```bash
python manage.py migrate
```

5. Start the development server:

```bash
python manage.py runserver
```

The browser never calls Gemini directly. Chat messages are posted to Django at `/api/chatbot/message/`, where Phoenix catalogue context is retrieved from the database before Gemini is used.

## Cloudinary Setup

Uploaded product and category images use Cloudinary when `CLOUDINARY_URL` is configured. Static CSS, JavaScript, and bundled assets remain on Django's existing static-files setup.

1. Create a Cloudinary account and open the Cloudinary Console.
2. Copy the API environment variable from the account credentials area.
3. Add it to the local `.env` file without committing the value:

```env
CLOUDINARY_URL=cloudinary://API_KEY:API_SECRET@CLOUD_NAME
```

4. Add the same secret variable in Render under Service -> Environment, along with `DEBUG=False`. Do not put the Cloudinary secret in `render.yaml` or templates.
5. Install dependencies and run migrations if needed:

```bash
pip install -r requirements.txt
python manage.py migrate
```

6. Upload a test product or category image through the Phoenix Admin and open the resulting page. The image URL should begin with `https://res.cloudinary.com/`.

Existing demo images remain available for local development through the explicit DEBUG fallback. Before production deployment, upload any media records that still reference local files and verify their database names are Cloudinary-backed; do not delete the local `media/` directory until that inventory is complete.

## Render Data Persistence

Render services have an ephemeral filesystem. Production must use a managed PostgreSQL database; the application now refuses to start in Render or with `DEBUG=False` when `DATABASE_URL` is missing instead of silently using `db.sqlite3`.

Set these service environment variables in Render:

```env
DATABASE_URL=postgresql://...
SECRET_KEY=use-a-long-random-secret
DEBUG=False
CLOUDINARY_URL=cloudinary://...
EMAIL_HOST=smtp-relay.brevo.com
EMAIL_PORT=587
EMAIL_HOST_USER=...
EMAIL_HOST_PASSWORD=...
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=phoenixinteriorhub@gmail.com
PUBLIC_SITE_URL=https://www.phoenixinteriorhub.com
```

`DATABASE_URL` should be the Internal Database URL for a PostgreSQL database attached to the service. Never commit it or any other secret. `db.sqlite3` is for local development only and is ignored by Git.

Customer password-reset email uses Django SMTP settings in production. Set `EMAIL_HOST`, `EMAIL_HOST_USER`, and `EMAIL_HOST_PASSWORD` to the credentials for the chosen mail provider. `EMAIL_PORT`, `EMAIL_USE_TLS`, `EMAIL_USE_SSL`, `DEFAULT_FROM_EMAIL`, and `PUBLIC_SITE_URL` may be adjusted to match that provider and domain. Local development defaults to Django's console email backend.

Use these Render commands:

```text
Build: pip install -r requirements.txt && python manage.py collectstatic --noinput
Start: gunicorn phoenix_ecommerce.wsgi:application
```

Run migrations once against the configured PostgreSQL database, then verify the selected backend with the read-only diagnostic command:

```bash
python manage.py migrate
python manage.py db_info
```

It should report `Database backend: PostgreSQL`, `SQLite: NO`, and `Connection: OK`. `database_health` is an equivalent command name. Do not run `flush`, delete the database, or put demo seeding in the Render build command. The existing `seed_phoenix_categories` command is idempotent, but use it only as a deliberate one-time catalogue setup operation.
