# GPT Reverse Proxy

**Use ChatGPT without API keys!** Login with your ChatGPT account session token.

## Why This Project?

- **No API keys needed** - Use your existing ChatGPT account
- **Free to use** - No need to pay for API access
- **Same models** - Access GPT-4, GPT-3.5, etc. through your subscription
- **Simple setup** - Just copy a cookie from your browser

## Quick Start

### 1. Install

```bash
pip install -e .
```

### 2. Get Session Token

1. Go to [chat.openai.com](https://chat.openai.com) and login
2. Press `F12` to open DevTools
3. Go to **Application** > **Cookies** > **chat.openai.com**
4. Find `__Secure-next-auth.session-token` cookie
5. Copy its value

Or run this in browser console:
```javascript
document.cookie.split('; ').find(c => c.startsWith('__Secure-next-auth.session-token='))?.split('=')[1]
```

### 3. Start Proxy

```bash
gpt-proxy serve
```

### 4. Login

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"session_token": "your-token-here"}'
```

Response:
```json
{
  "session_id": "abc123...",
  "user_email": "your@email.com",
  "expires_at": "2024-...",
  "message": "Login successful. Use session_id as Bearer token in API requests."
}
```

### 5. Use API

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer <session_id>" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

## Python Client

```python
import httpx

# Login
login_resp = httpx.post(
    "http://localhost:8000/auth/login",
    json={"session_token": "your-token"}
)
session_id = login_resp.json()["session_id"]

# Chat
client = httpx.Client(
    base_url="http://localhost:8000/v1",
    headers={"Authorization": f"Bearer {session_id}"}
)

response = client.post(
    "/chat/completions",
    json={
        "model": "gpt-4",
        "messages": [{"role": "user", "content": "Hello!"}]
    }
)
print(response.json())
```

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /auth/login` | Login with session token |
| `GET /auth/help` | How to get session token |
| `GET /auth/sessions` | List active sessions |
| `POST /auth/logout` | Logout session |
| `POST /v1/chat/completions` | Chat completions |
| `GET /v1/models` | List models |

## CLI Commands

```bash
# Start server
gpt-proxy serve --port 8000

# Show how to get token
gpt-proxy help-token

# Show version
gpt-proxy version
```

## Docker

```bash
docker build -t gpt-proxy -f docker/Dockerfile .
docker run -p 8000:8000 gpt-proxy
```

## Notes

- **Session tokens expire** - Get a fresh token if you get 401 errors
- **Rate limits apply** - Same limits as your ChatGPT web access
- **Subscription required** - GPT-4 requires ChatGPT Plus subscription
- **Unofficial API** - This uses ChatGPT's backend API, not the official OpenAI API

## License

MIT