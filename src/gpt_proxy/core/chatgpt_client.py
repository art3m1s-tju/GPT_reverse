"""ChatGPT backend API client using conversation endpoint.

Based on reverse-engineered ChatGPT web API from chat2api project.
https://github.com/lanqian528/chat2api
"""

import hashlib
import json
import random
import re
import time
import uuid
from typing import AsyncIterator
from logging import getLogger
from datetime import datetime, timezone, timedelta

from curl_cffi.requests import AsyncSession
import pybase64

from gpt_proxy.config import settings

logger = getLogger(__name__)

# Cache for DPL and scripts
_cached_dpl: str = ""
_cached_scripts: list[str] = []
_cached_time: int = 0

# Model mapping from OpenAI API names to ChatGPT internal names
MODEL_MAP = {
    "gpt-3.5-turbo": "text-davinci-002-render-sha",
    "gpt-3.5-turbo-0125": "text-davinci-002-render-sha",
    "gpt-4": "gpt-4",
    "gpt-4-turbo": "gpt-4-turbo",
    "gpt-4o": "gpt-4o",
    "gpt-4o-mini": "gpt-4o-mini",
    "gpt-4o-canmore": "gpt-4o-canmore",
    "gpt-4.5o": "gpt-4.5o",
    "o1": "o1",
    "o1-mini": "o1-mini",
    "o1-preview": "o1-preview",
    "o1-pro": "o1-pro",
    "o3-mini": "o3-mini",
    "o3-mini-high": "o3-mini-high",
    "o3-mini-medium": "o3-mini-medium",
    "o3-mini-low": "o3-mini-low",
    "auto": "auto",
}


class ChatGPTClient:
    """ChatGPT backend API client using conversation endpoint."""

    CHATGPT_BASE_URL = "https://chatgpt.com"
    BACKEND_API = f"{CHATGPT_BASE_URL}/backend-api"

    def __init__(
        self,
        access_token: str,
        proxy_url: str | None = None,
        impersonate: str = "chrome131",
    ):
        self.access_token = access_token
        self.proxy_url = proxy_url
        self.impersonate = impersonate
        self._session: AsyncSession | None = None
        self._chat_token: str = "gAAAAAB"
        self._proof_token: str | None = None
        self._arkose_token: str | None = None
        self._turnstile_token: str | None = None
        self._device_id: str = str(uuid.uuid4())

    async def _get_session(self) -> AsyncSession:
        """Get or create curl_cffi session."""
        if self._session is None:
            proxies = None
            if self.proxy_url:
                proxies = {"http": self.proxy_url, "https": self.proxy_url}
            self._session = AsyncSession(
                proxies=proxies,
                impersonate=self.impersonate,
                timeout=120,
                verify=True,
            )
        return self._session

    async def _fetch_dpl(self) -> bool:
        """Fetch DPL (data-build) parameter from ChatGPT homepage.

        This is required for POW verification.
        """
        global _cached_dpl, _cached_scripts, _cached_time

        # Use cached value if fresh (< 15 minutes)
        if int(time.time()) - _cached_time < 15 * 60 and _cached_dpl:
            return True

        if settings.conversation_only:
            return True

        session = await self._get_session()
        headers = self._get_base_headers()
        # Remove auth header for homepage request
        headers.pop("authorization", None)

        try:
            response = await session.get(
                self.CHATGPT_BASE_URL,
                headers=headers,
                timeout=10,
            )
            response.raise_for_status()

            html = response.text

            # Extract script URLs
            _cached_scripts = re.findall(r'<script[^>]+src="([^"]+)"', html)

            # Extract DPL from script URL or data-build attribute
            for script in _cached_scripts:
                match = re.search(r"c/([^/]+)/_", script)
                if match:
                    _cached_dpl = match.group(1)
                    break

            # Fallback: look for data-build in HTML
            if not _cached_dpl:
                match = re.search(r'data-build="([^"]+)"', html)
                if match:
                    _cached_dpl = match.group(1)

            if _cached_dpl:
                _cached_time = int(time.time())
                logger.info(f"Got DPL: {_cached_dpl}")
                return True
            else:
                logger.warning("Failed to extract DPL from homepage")
                return False

        except Exception as e:
            logger.error(f"Error fetching DPL: {e}")
            return False

    def _get_base_headers(self) -> dict:
        """Get base headers for ChatGPT API requests."""
        return {
            "accept": "*/*",
            "accept-encoding": "gzip, deflate, br, zstd",
            "accept-language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
            "content-type": "application/json",
            "oai-device-id": self._device_id,
            "oai-language": "zh-CN",
            "origin": self.CHATGPT_BASE_URL,
            "priority": "u=1, i",
            "referer": f"{self.CHATGPT_BASE_URL}/",
            "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"macOS"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "authorization": f"Bearer {self.access_token}",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        }

    async def get_chat_requirements(self) -> dict:
        """Get chat requirements token from ChatGPT sentinel endpoint.

        Returns:
            dict with token and other requirements
        """
        # Skip sentinel if conversation_only mode
        if settings.conversation_only:
            logger.info("Skipping sentinel verification (conversation_only mode)")
            return {}

        # First fetch DPL from homepage
        await self._fetch_dpl()

        session = await self._get_session()
        url = f"{self.BACKEND_API}/sentinel/chat-requirements"

        headers = self._get_base_headers()

        # Generate requirements token (simplified, may need POW for some accounts)
        config = self._get_pow_config()
        requirements_token = self._get_requirements_token(config)

        try:
            response = await session.post(
                url,
                headers=headers,
                json={"p": requirements_token},
                timeout=10,
            )

            if response.status_code == 200:
                data = response.json()
                self._chat_token = data.get("token", "gAAAAAB")

                # Check persona (account type)
                persona = data.get("persona", "")
                logger.info(f"ChatGPT persona: {persona}")

                # Check for Arkose requirement (required for free accounts)
                arkose = data.get("arkose", {})
                if arkose.get("required"):
                    arkose_dx = arkose.get("dx", "")
                    if settings.arkose_token_url:
                        self._arkose_token = await self._get_arkose_token(arkose_dx, persona)
                    else:
                        logger.warning("Arkose token required but no service URL configured")
                        logger.warning("Free accounts need Arkose verification. Set ARKOSE_TOKEN_URL or use a Plus account")

                # Check for Turnstile requirement
                turnstile = data.get("turnstile", {})
                if turnstile.get("required"):
                    logger.warning("Turnstile (CAPTCHA) required - may need manual intervention")

                # Check for POW requirement
                proofofwork = data.get("proofofwork", {})
                if proofofwork.get("required"):
                    diff = proofofwork.get("difficulty", 0)
                    seed = proofofwork.get("seed", "")
                    # Ensure diff is int
                    if isinstance(diff, str):
                        try:
                            diff = int(diff, 16) if diff.startswith("0x") else int(diff)
                        except ValueError:
                            diff = 0

                    # POW difficulty 0 means ChatGPT is very suspicious
                    if diff < settings.pow_difficulty:
                        logger.warning(f"POW difficulty {diff} too high (threshold: {settings.pow_difficulty})")
                        logger.warning("This usually means ChatGPT detected suspicious activity")
                        logger.warning("Try: 1) Use a clean proxy, 2) Wait a few minutes, 3) Use a Plus account")
                    else:
                        self._proof_token = await self._solve_pow(seed, diff, config)

                return data
            else:
                logger.warning(f"Chat requirements failed: {response.status_code}")
                return {}
        except Exception as e:
            logger.error(f"Error getting chat requirements: {e}")
            return {}

    def _get_pow_config(self) -> list:
        """Get proof-of-work config."""
        global _cached_dpl, _cached_scripts

        # Get current time in Eastern timezone
        now = datetime.now(timezone(timedelta(hours=-5)))
        time_str = now.strftime("%a %b %d %Y %H:%M:%S") + " GMT-0500 (Eastern Standard Time)"

        cores = [8, 16, 24, 32]
        return [
            random.choice([1920 + 1080, 2560 + 1440, 1920 + 1200, 2560 + 1600]),
            time_str,
            4294705152,
            0,
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            random.choice(_cached_scripts) if _cached_scripts else "",
            _cached_dpl,
            "en-US",
            "en-US,es-US,en,es",
            0,
            "webdriver-false",
            "location",
            "window",
            time.perf_counter() * 1000,
            str(uuid.uuid4()),
            "",
            random.choice(cores),
            time.time() * 1000 - (time.perf_counter() * 1000),
        ]

    def _get_requirements_token(self, config: list) -> str:
        """Generate requirements token."""
        answer, _ = self._generate_answer(format(random.random()), "0fffff", config)
        return "gAAAAAC" + answer

    async def _get_arkose_token(self, blob: str, persona: str) -> str:
        """Get Arkose token from external service.

        Args:
            blob: The Arkose challenge blob
            persona: Account type (chatgpt-freeaccount, chatgpt-paid, etc.)

        Returns:
            Arkose token string
        """
        if not settings.arkose_token_url:
            return ""

        # Determine method based on account type
        method = "chat35" if persona == "chatgpt-freeaccount" else "chat4"

        session = await self._get_session()
        try:
            response = await session.post(
                settings.arkose_token_url,
                json={"blob": blob, "method": method},
                timeout=15,
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("solved", True):
                    token = data.get("token", "")
                    logger.info(f"Got Arkose token: {token[:20]}...")
                    return token

            logger.warning(f"Arkose service failed: {response.status_code}")
            return ""

        except Exception as e:
            logger.error(f"Error getting Arkose token: {e}")
            return ""

    async def _solve_pow(self, seed: str, difficulty: int, config: list) -> str:
        """Solve proof-of-work challenge.

        Args:
            seed: The seed from server
            difficulty: Difficulty level (lower = harder)
            config: POW config

        Returns:
            Proof token
        """
        # Skip if difficulty too high
        if difficulty < 2:
            logger.warning(f"POW difficulty too high: {difficulty}")
            return ""

        diff_hex = format(difficulty, "06x")
        answer, solved = self._generate_answer(seed, diff_hex, config)

        if solved:
            return "gAAAAAB" + answer
        return ""

    def _generate_answer(self, seed: str, diff: str, config: list) -> tuple[str, bool]:
        """Generate POW answer.

        Args:
            seed: Challenge seed
            diff: Difficulty in hex
            config: POW config

        Returns:
            (answer, solved) tuple
        """
        diff_len = len(diff)
        seed_encoded = seed.encode()

        static_part1 = (
            json.dumps(config[:3], separators=(",", ":"), ensure_ascii=False)[:-1] + ","
        ).encode()
        static_part2 = (
            "," + json.dumps(config[4:9], separators=(",", ":"), ensure_ascii=False)[1:-1] + ","
        ).encode()
        static_part3 = (
            "," + json.dumps(config[10:], separators=(",", ":"), ensure_ascii=False)[1:]
        ).encode()

        target_diff = bytes.fromhex(diff)

        for i in range(500000):
            dynamic_i = str(i).encode()
            dynamic_j = str(i >> 1).encode()
            final_bytes = static_part1 + dynamic_i + static_part2 + dynamic_j + static_part3
            base_encode = pybase64.b64encode(final_bytes)
            hash_value = hashlib.sha3_512(seed_encoded + base_encode).digest()

            if hash_value[:diff_len] <= target_diff:
                return base_encode.decode(), True

        return "wQ8Lk5FbGpA2NcR9dShT6gYjU7VxZ4D" + pybase64.b64encode(f'"{seed}"'.encode()).decode(), False

    def _convert_messages_to_chatgpt(self, messages: list[dict]) -> list[dict]:
        """Convert OpenAI messages format to ChatGPT conversation format.

        Args:
            messages: OpenAI format messages [{"role": "user", "content": "..."}]

        Returns:
            ChatGPT format messages
        """
        chat_messages = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            # Handle string content
            if isinstance(content, str):
                parts = [content]
                content_type = "text"
            # Handle list content (multimodal)
            elif isinstance(content, list):
                parts = []
                for item in content:
                    if item.get("type") == "text":
                        parts.append(item.get("text", ""))
                    elif item.get("type") == "image_url":
                        # For now, just note the image - would need upload for full support
                        parts.append(f"[Image: {item.get('image_url', {}).get('url', '')}]")
                content_type = "multimodal_text" if len(parts) > 1 else "text"
            else:
                parts = [str(content)]
                content_type = "text"

            chat_msg = {
                "id": str(uuid.uuid4()),
                "author": {"role": role},
                "content": {"content_type": content_type, "parts": parts},
                "metadata": {},
            }
            chat_messages.append(chat_msg)

        return chat_messages

    def _map_model(self, model: str) -> str:
        """Map OpenAI model name to ChatGPT internal model name."""
        return MODEL_MAP.get(model, model)

    async def chat_completions(
        self,
        model: str,
        messages: list[dict],
        stream: bool = False,
        conversation_id: str | None = None,
        parent_message_id: str | None = None,
        **kwargs,
    ) -> AsyncIterator[bytes] | dict:
        """Send chat completion request to ChatGPT conversation endpoint.

        Args:
            model: Model name (will be mapped to ChatGPT internal name)
            messages: OpenAI format messages
            stream: Whether to stream response
            conversation_id: Existing conversation ID (for continuing chats)
            parent_message_id: Parent message ID (for continuing chats)
            **kwargs: Additional parameters (max_tokens, temperature, etc.)

        Returns:
            AsyncIterator for streaming or dict for non-streaming
        """
        session = await self._get_session()
        url = f"{self.BACKEND_API}/conversation"

        # Get chat requirements
        await self.get_chat_requirements()

        # Build headers
        headers = self._get_base_headers()
        headers["accept"] = "text/event-stream"

        # Add sentinel headers only if not in conversation_only mode
        if not settings.conversation_only:
            headers["openai-sentinel-chat-requirements-token"] = self._chat_token

            if self._proof_token:
                headers["openai-sentinel-proof-token"] = self._proof_token
            if self._arkose_token:
                headers["openai-sentinel-arkose-token"] = self._arkose_token
            if self._turnstile_token:
                headers["openai-sentinel-turnstile-token"] = self._turnstile_token

        # Convert messages
        chat_messages = self._convert_messages_to_chatgpt(messages)

        # Map model
        internal_model = self._map_model(model)

        # Build request body
        request_body = {
            "action": "next",
            "client_contextual_info": {
                "is_dark_mode": False,
                "time_since_loaded": random.randint(50, 500),
                "page_height": random.randint(500, 1000),
                "page_width": random.randint(1000, 2000),
                "pixel_ratio": 1.5,
                "screen_height": random.randint(800, 1200),
                "screen_width": random.randint(1200, 2200),
            },
            "conversation_mode": {"kind": "primary_assistant"},
            "conversation_origin": None,
            "force_paragen": False,
            "force_paragen_model_slug": "",
            "force_rate_limit": False,
            "force_use_sse": True,
            "history_and_training_disabled": True,
            "messages": chat_messages,
            "model": internal_model,
            "paragen_cot_summary_display_override": "allow",
            "paragen_stream_type_override": None,
            "parent_message_id": parent_message_id or str(uuid.uuid4()),
            "reset_rate_limits": False,
            "suggestions": [],
            "supported_encodings": [],
            "system_hints": [],
            "timezone": "America/Los_Angeles",
            "timezone_offset_min": -480,
            "variant_purpose": "comparison_implicit",
            "websocket_request_id": str(uuid.uuid4()),
        }

        if conversation_id:
            request_body["conversation_id"] = conversation_id

        logger.info(f"Sending conversation request with model: {internal_model}")

        try:
            # Always use streaming for ChatGPT API
            response = await session.post(
                url,
                headers=headers,
                json=request_body,
                timeout=120,
                stream=True,  # Always stream for ChatGPT API
            )

            if response.status_code != 200:
                error_text = response.text[:500]
                logger.error(f"ChatGPT API error: {response.status_code} - {error_text}")

                # Check for specific error types
                if "Unusual activity" in error_text:
                    raise Exception(
                        "ChatGPT detected unusual activity. Try:\n"
                        "1. Use a different IP/proxy\n"
                        "2. Set CONVERSATION_ONLY=true (may still fail)\n"
                        "3. Wait a few minutes and retry"
                    )
                raise Exception(f"ChatGPT API error: {response.status_code}")

            if stream:
                return self._stream_response(response, model)
            else:
                return await self._collect_response(response, model)

        except Exception as e:
            logger.error(f"Error in chat_completions: {e}")
            raise

    async def _stream_response(self, response, model: str) -> AsyncIterator[bytes]:
        """Stream ChatGPT response and convert to OpenAI format."""
        chat_id = f"chatcmpl-{''.join(random.choices('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=29))}"
        created_time = int(time.time())

        # Send initial chunk with role
        initial_chunk = {
            "id": chat_id,
            "object": "chat.completion.chunk",
            "created": created_time,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {"role": "assistant", "content": ""},
                    "logprobs": None,
                    "finish_reason": None,
                }
            ],
        }
        yield f"data: {json.dumps(initial_chunk)}\n\n".encode()

        content_parts = []
        finish_reason = None

        async for line in response.aiter_lines():
            if not line or not line.startswith("data: "):
                continue

            if line == "data: [DONE]":
                break

            try:
                data = json.loads(line[6:])
                message = data.get("message", {})

                if not message:
                    continue

                role = message.get("author", {}).get("role")
                if role in ("user", "system"):
                    continue

                status = message.get("status")
                content = message.get("content", {})
                content_type = content.get("content_type", "")

                if content_type == "text":
                    parts = content.get("parts", [])
                    if parts:
                        new_text = parts[0]
                        if len(new_text) > len("".join(content_parts)):
                            delta_text = new_text[len("".join(content_parts)):]
                            content_parts.append(delta_text)

                            chunk = {
                                "id": chat_id,
                                "object": "chat.completion.chunk",
                                "created": created_time,
                                "model": model,
                                "choices": [
                                    {
                                        "index": 0,
                                        "delta": {"content": delta_text},
                                        "logprobs": None,
                                        "finish_reason": None,
                                    }
                                ],
                            }
                            yield f"data: {json.dumps(chunk)}\n\n".encode()

                if status == "finished_successfully":
                    finish_reason = "stop"

            except json.JSONDecodeError:
                continue

        # Send final chunk
        final_chunk = {
            "id": chat_id,
            "object": "chat.completion.chunk",
            "created": created_time,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {},
                    "logprobs": None,
                    "finish_reason": finish_reason,
                }
            ],
        }
        yield f"data: {json.dumps(final_chunk)}\n\n".encode()
        yield b"data: [DONE]\n\n"

    async def _collect_response(self, response, model: str) -> dict:
        """Collect streaming response and return as single dict."""
        chat_id = f"chatcmpl-{''.join(random.choices('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=29))}"
        created_time = int(time.time())

        all_content = []
        finish_reason = None

        async for line in response.aiter_lines():
            if not line or not line.startswith("data: "):
                continue

            if line == "data: [DONE]":
                break

            try:
                data = json.loads(line[6:])
                message = data.get("message", {})

                if not message:
                    continue

                role = message.get("author", {}).get("role")
                if role in ("user", "system"):
                    continue

                status = message.get("status")
                content = message.get("content", {})

                if content.get("content_type") == "text":
                    parts = content.get("parts", [])
                    if parts:
                        all_content = parts

                if status == "finished_successfully":
                    finish_reason = "stop"

            except json.JSONDecodeError:
                continue

        full_content = "".join(all_content)

        return {
            "id": chat_id,
            "object": "chat.completion",
            "created": created_time,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": full_content,
                    },
                    "logprobs": None,
                    "finish_reason": finish_reason or "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            },
        }

    async def close(self):
        """Close the session."""
        if self._session:
            await self._session.close()
            self._session = None
