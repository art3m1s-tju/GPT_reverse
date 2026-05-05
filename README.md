# GPT Reverse Proxy

A local ChatGPT reverse proxy with API key management, rate limiting, cost tracking, and request logging.

## Features

- **Multi-key Management**: Rotate between multiple OpenAI API keys with various strategies
- **Full API Coverage**: Proxy all OpenAI API endpoints (chat, embeddings, images, audio, etc.)
- **Streaming Support**: Properly handle SSE streaming responses
- **Rate Limiting**: Built-in rate limiting with configurable limits
- **Cost Tracking**: Track token usage and costs per key/model
- **Request Logging**: Structured logging of all requests and responses
- **Response Caching**: Optional caching for identical requests
- **CLI Interface**: Easy-to-use command line interface
- **Docker Ready**: Containerized deployment with Docker Compose

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/art3m1s-tju/GPT_reverse.git
cd GPT_reverse

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env
# Edit .env and add your OpenAI API keys
```

### Running

```bash
# Start the proxy server
python -m gpt_proxy serve

# Or use the CLI
gpt-proxy serve --host 0.0.0.0 --port 8000
```

### Usage

Point your OpenAI client to the proxy:

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="any-key"  # The proxy will use its configured keys
)

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Hello!"}]
)
```

## CLI Commands

```bash
# Start server
gpt-proxy serve

# Manage API keys
gpt-proxy keys list
gpt-proxy keys add sk-xxx
gpt-proxy keys rotate

# View logs
gpt-proxy logs
gpt-proxy logs --follow

# View statistics
gpt-proxy stats --period day

# Show configuration
gpt-proxy config --show
```

## Configuration

Configuration is done via environment variables or `.env` file:

| Variable | Description | Default |
|----------|-------------|---------|
| `APP_HOST` | Server host | `0.0.0.0` |
| `APP_PORT` | Server port | `8000` |
| `OPENAI_API_KEYS` | Comma-separated API keys | Required |
| `OPENAI_KEY_ROTATION_STRATEGY` | Key rotation strategy | `round-robin` |
| `RATE_LIMIT_REQUESTS_PER_MINUTE` | Rate limit | `60` |
| `CACHE_ENABLED` | Enable response caching | `false` |
| `LOG_LEVEL` | Logging level | `INFO` |

## Docker

```bash
# Build image
docker build -t gpt-proxy -f docker/Dockerfile .

# Run container
docker run -p 8000:8000 -e OPENAI_API_KEYS=sk-xxx gpt-proxy

# Or with docker-compose
docker-compose -f docker/docker-compose.yml up
```

## API Endpoints

All OpenAI API endpoints are proxied:

- `POST /v1/chat/completions` - Chat completions
- `POST /v1/embeddings` - Create embeddings
- `POST /v1/images/generations` - Generate images
- `POST /v1/audio/speech` - Text-to-speech
- `POST /v1/audio/transcriptions` - Speech-to-text
- `GET /v1/models` - List models
- `POST /v1/moderations` - Content moderation

## License

MIT
