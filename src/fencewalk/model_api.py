"""Model provider drivers for the API model pass (`run-model`).

One driver per provider, behind `call_provider`. Adding a provider
means adding a driver function and one dispatch line — the command
never learns provider specifics. Stdlib only (`urllib.request`):
`dependencies = []` is a product property.

The driver never sees a key except as a parameter passed in by the
caller, never prints it, never writes it anywhere, and never stores
it. No retry, ever: a retry re-sends the packet and can
double-charge; the operator re-runs the command.
"""

import json
import urllib.error
import urllib.request

ANTHROPIC_BASE_URL = "https://api.anthropic.com"
ANTHROPIC_MESSAGES_PATH = "/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
REQUEST_TIMEOUT_SECONDS = 300


class ModelApiError(ValueError):
    """A model provider call failed: printed cleanly by main(), exit 1."""


def call_anthropic(model, packet_text, api_key, max_tokens,
                   base_url=ANTHROPIC_BASE_URL,
                   timeout=REQUEST_TIMEOUT_SECONDS):
    """Call the Anthropic Messages API with the packet as the single
    user message. Returns (output_text, input_tokens, output_tokens,
    skipped_thinking_blocks).

    Thinking-family blocks (`thinking`, `redacted_thinking`) are
    skipped: they are the model's internal reasoning, not part of
    the output the operator records. The skipped count is returned
    so the command can tell the operator part of what they paid
    for was dropped (thinking tokens are inside output_tokens).
    A response with no text blocks at all is an error.

    base_url is a parameter (defaulting to the real API) so tests can
    point the driver at a local stub server; the CLI exposes no base
    URL and no test-only environment variable exists in shipped code.
    """
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": packet_text}],
    }
    request = urllib.request.Request(
        base_url.rstrip("/") + ANTHROPIC_MESSAGES_PATH,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "x-api-key": api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:500]
        raise ModelApiError(
            f"model API returned HTTP {exc.code}: {detail}"
        ) from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        raise ModelApiError(f"model API call failed: {reason}") from None
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise ModelApiError(
            f"unexpected model response: not valid JSON ({exc})"
        ) from None
    content = payload.get("content") if isinstance(payload, dict) else None
    if not isinstance(content, list):
        raise ModelApiError(
            "unexpected model response: missing content list"
        )
    # A response that stopped for any reason other than end_turn
    # (max_tokens above all) is incomplete; it is refused rather
    # than written out and ingested as if it were a whole run.
    if "stop_reason" not in payload:
        raise ModelApiError("unexpected model response: missing stop_reason")
    stop_reason = payload["stop_reason"]
    if stop_reason != "end_turn":
        raise ModelApiError(
            f"unexpected model response: stop_reason is {stop_reason},"
            " not end_turn"
        )
    parts = []
    skipped_thinking_blocks = 0
    for block in content:
        if not isinstance(block, dict):
            raise ModelApiError(
                "unexpected model response: non-text content block "
                "(not an object)"
            )
        kind = block.get("type")
        if kind in ("thinking", "redacted_thinking"):
            skipped_thinking_blocks += 1
            continue
        if kind != "text":
            raise ModelApiError(
                f"unexpected model response: non-text content block ({kind})"
            )
        text = block.get("text")
        if not isinstance(text, str):
            raise ModelApiError(
                "unexpected model response: text block without text"
            )
        parts.append(text)
    if not parts:
        raise ModelApiError("unexpected model response: no text content")
    usage = payload.get("usage") if isinstance(payload, dict) else None
    if not isinstance(usage, dict):
        raise ModelApiError("unexpected model response: missing usage")
    try:
        input_tokens = int(usage["input_tokens"])
        output_tokens = int(usage["output_tokens"])
    except (KeyError, TypeError, ValueError):
        raise ModelApiError("unexpected model response: missing usage")
    return "".join(parts), input_tokens, output_tokens, skipped_thinking_blocks


def call_provider(provider, model, packet_text, api_key, max_tokens):
    """Dispatch to the driver for provider. Unknown providers are an
    error here as well as in the command, so direct callers fail
    the same way."""
    if provider == "anthropic":
        return call_anthropic(model, packet_text, api_key, max_tokens)
    raise ModelApiError(f"unknown provider: {provider}")
