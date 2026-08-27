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
