"""Model calls that survive busy periods.

Hosted models sometimes answer 429 (rate limit), 503 (high demand) or 504
(timeout). In CI that would fail the whole run, so each call has a time limit,
is retried with a short backoff, and moves on to the next model in the list if
one stays busy.
"""

import asyncio
import time

from google import genai
from google.genai import errors, types

RETRYABLE = {429, 500, 503, 504}
DELAYS = (3, 8)  # seconds to wait before each retry on the same model
CALL_TIMEOUT_MS = 60_000

# Models that stayed busy earlier in this run. An agent makes many calls, so
# once a model gives up we skip it instead of waiting on it at every step.
_busy = set()


def _candidates(models):
    available = [m for m in models if m not in _busy]
    return available or list(models)  # if everything was busy, try them all again


def make_client(api_key):
    # The SDK has its own silent retries; turn them off so ours are the only
    # ones and a busy model can't stall the run for minutes.
    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(
            timeout=CALL_TIMEOUT_MS,
            retry_options=types.HttpRetryOptions(attempts=1),
        ),
    )


def generate(client, models, **kwargs):
    last_error = None
    for model in _candidates(models):
        for delay in (0, *DELAYS):
            time.sleep(delay)
            try:
                return client.models.generate_content(model=model, **kwargs), model
            except errors.APIError as exc:
                if exc.code not in RETRYABLE:
                    raise
                last_error = exc
                print(f"   {model} busy ({exc.code}), retrying...", flush=True)
        _busy.add(model)
        print(f"   skipping {model} for the rest of this run", flush=True)
    raise last_error


async def agenerate(client, models, **kwargs):
    last_error = None
    for model in _candidates(models):
        for delay in (0, *DELAYS):
            await asyncio.sleep(delay)
            try:
                return await client.aio.models.generate_content(model=model, **kwargs), model
            except errors.APIError as exc:
                if exc.code not in RETRYABLE:
                    raise
                last_error = exc
                print(f"   {model} busy ({exc.code}), retrying...", flush=True)
        _busy.add(model)
        print(f"   skipping {model} for the rest of this run", flush=True)
    raise last_error
