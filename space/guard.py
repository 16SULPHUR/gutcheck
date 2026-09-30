"""Locks a gutcheck app down for a public demo: three routes, small inputs, per-IP rate limit."""

import json
import os
import re
import time
from collections import defaultdict, deque

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

ALLOWED = {("GET", "/healthz"), ("GET", "/v1/packs"), ("POST", "/v1/decide")}
MAX_BODY = 16_000
MAX_STATE_CHARS = 2_000
MAX_QUESTIONS = 6
MAX_INFLIGHT = 8
RATE_LIMIT = 20
RATE_WINDOW = 60.0


def _client_ip(scope) -> str:
    for key, value in scope["headers"]:
        if key == b"x-forwarded-for":
            return value.decode().split(",")[0].strip()
    return (scope.get("client") or ("unknown",))[0]


class Guard:
    def __init__(self, app, rate_limit: int = RATE_LIMIT, window: float = RATE_WINDOW):
        self.app = app
        self.rate_limit = rate_limit
        self.window = window
        self.hits: dict[str, deque[float]] = defaultdict(deque)
        self.inflight = 0

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] == "OPTIONS":
            return await self.app(scope, receive, send)
        if (scope["method"], scope["path"]) not in ALLOWED:
            return await self._reply(send, 404, "not available on the public demo")
        if scope["path"] != "/v1/decide":
            return await self.app(scope, receive, send)
        if not self._allow(_client_ip(scope)):
            return await self._reply(send, 429, "rate limit reached, try again in a minute")
        if self.inflight >= MAX_INFLIGHT:
            return await self._reply(send, 503, "the demo is busy, try again shortly")

        body = b""
        while True:
            message = await receive()
            body += message.get("body", b"")
            if len(body) > MAX_BODY:
                return await self._reply(send, 413, "request too large")
            if not message.get("more_body"):
                break
        problem = self._check(body)
        if problem:
            return await self._reply(send, 422, problem)

        sent = False

        async def replay():
            nonlocal sent
            if sent:
                return {"type": "http.disconnect"}
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}

        self.inflight += 1
        try:
            await self.app(scope, replay, send)
        finally:
            self.inflight -= 1

    def _allow(self, ip: str) -> bool:
        now = time.monotonic()
        hits = self.hits[ip]
        while hits and now - hits[0] > self.window:
            hits.popleft()
        if len(hits) >= self.rate_limit:
            return False
        hits.append(now)
        if len(self.hits) > 10_000:
            self.hits = defaultdict(deque, {k: v for k, v in self.hits.items() if v})
        return True

    @staticmethod
    def _check(body: bytes) -> str | None:
        try:
            data = json.loads(body)
        except ValueError:
            return "body must be JSON"
        if not isinstance(data, dict):
            return "body must be a JSON object"
        if len(json.dumps(data.get("state", ""))) > MAX_STATE_CHARS:
            return f"state is limited to {MAX_STATE_CHARS} characters on the public demo"
        questions = data.get("questions") or {}
        if not isinstance(questions, dict) or len(questions) > MAX_QUESTIONS:
            return f"at most {MAX_QUESTIONS} questions per request on the public demo"
        return None

    @staticmethod
    async def _reply(send, status: int, detail: str):
        body = json.dumps({"detail": detail}).encode()
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


def protect(
    app: FastAPI, origins: list[str] | None = None, origin_regex: str | None = None
) -> FastAPI:
    if origins is None:
        origins = [o for o in os.environ.get("SITE_ORIGINS", "").split(",") if o]
    if origin_regex is None:
        origin_regex = os.environ.get("SITE_ORIGIN_REGEX") or None
    if origin_regex:
        re.compile(origin_regex)
    app.add_middleware(Guard)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_origin_regex=origin_regex,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
        expose_headers=["X-Gutcheck-Trace-Id"],
        max_age=3600,
    )
    return app
