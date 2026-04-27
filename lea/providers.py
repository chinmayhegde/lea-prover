"""Provider abstraction — thin wrappers over LLM APIs.

Each provider yields a stream of events from a unified interface.
Dependencies (anthropic, openai) are optional; imported only when selected.
"""

import os
from dataclasses import dataclass


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class TextDelta:
    text: str


@dataclass
class ToolCall:
    name: str
    args: dict
    raw_part: object = None  # Provider-specific part for faithful replay


@dataclass
class Done:
    usage: Usage


def detect_provider(model: str) -> str:
    """Guess provider from model name."""
    if model.startswith("gemini"):
        return "gemini"
    if model.startswith("claude"):
        return "anthropic"
    if model.startswith(("gpt", "o3", "o4")):
        return "openai"
    raise ValueError(f"Can't detect provider for model '{model}'. Use -p to specify.")


def stream(model: str, system: str, messages: list, tools: list, provider: str | None = None):
    """Yield TextDelta, ToolCall, and Done events from the model.

    messages: list of {"role": "user"|"assistant", "content": ...}
    tools: list of tool schema dicts (name, description, input_schema)
    """
    provider = provider or detect_provider(model)
    if provider == "gemini":
        yield from _stream_gemini(model, system, messages, tools)
    elif provider == "anthropic":
        yield from _stream_anthropic(model, system, messages, tools)
    elif provider == "openai":
        yield from _stream_openai(model, system, messages, tools)
    else:
        raise ValueError(f"Unknown provider: {provider}")


# ---------------------------------------------------------------------------
# Gemini
# ---------------------------------------------------------------------------

def _stream_gemini(model, system, messages, tools):
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

    declarations = [
        {"name": t["name"], "description": t["description"], "parameters": t["input_schema"]}
        for t in tools
    ]
    gemini_tools = types.Tool(function_declarations=declarations)
    config = types.GenerateContentConfig(tools=[gemini_tools], system_instruction=system)

    # Convert messages to Gemini contents
    contents = []
    for msg in messages:
        if msg["role"] == "user":
            if isinstance(msg["content"], str):
                contents.append(types.Content(role="user", parts=[types.Part.from_text(text=msg["content"])]))
            elif isinstance(msg["content"], list):
                # Tool results
                parts = []
                for item in msg["content"]:
                    if item.get("type") == "tool_result":
                        parts.append(types.Part.from_function_response(
                            name=item["tool_name"], response={"result": item["content"]},
                        ))
                    else:
                        parts.append(types.Part.from_text(text=str(item)))
                contents.append(types.Content(role="user", parts=parts))
        elif msg["role"] == "assistant":
            parts = []
            for item in msg["content"]:
                if item.get("type") == "text":
                    parts.append(types.Part.from_text(text=item["text"]))
                elif item.get("type") == "tool_call":
                    # Use raw_part if available (preserves thought_signature)
                    if item.get("raw_part") is not None:
                        parts.append(item["raw_part"])
                    else:
                        parts.append(types.Part(function_call=types.FunctionCall(
                            name=item["name"], args=item["args"],
                        )))
            contents.append(types.Content(role="model", parts=parts))

    usage = Usage()
    for chunk in client.models.generate_content_stream(model=model, contents=contents, config=config):
        if chunk.usage_metadata:
            usage.input_tokens = chunk.usage_metadata.prompt_token_count or 0
            usage.output_tokens = chunk.usage_metadata.candidates_token_count or 0
        if not chunk.candidates:
            continue
        for part in chunk.candidates[0].content.parts:
            if part.text:
                yield TextDelta(part.text)
            elif part.function_call:
                yield ToolCall(part.function_call.name, dict(part.function_call.args), raw_part=part)

    yield Done(usage)


# ---------------------------------------------------------------------------
# Anthropic
# ---------------------------------------------------------------------------

def _stream_anthropic(model, system, messages, tools):
    import anthropic

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    # Convert tools to Anthropic format
    anthropic_tools = [
        {
            "name": t["name"],
            "description": t["description"],
            "input_schema": t["input_schema"],
        }
        for t in tools
    ]

    # Convert messages to Anthropic format
    anthropic_messages = []
    for msg in messages:
        if msg["role"] == "user":
            if isinstance(msg["content"], str):
                anthropic_messages.append({"role": "user", "content": msg["content"]})
            elif isinstance(msg["content"], list):
                content = []
                for item in msg["content"]:
                    if item.get("type") == "tool_result":
                        content.append({
                            "type": "tool_result",
                            "tool_use_id": item["tool_use_id"],
                            "content": item["content"],
                        })
                    else:
                        content.append(item)
                anthropic_messages.append({"role": "user", "content": content})
        elif msg["role"] == "assistant":
            content = []
            for item in msg["content"]:
                if item.get("type") == "text":
                    content.append({"type": "text", "text": item["text"]})
                elif item.get("type") == "tool_call":
                    content.append({
                        "type": "tool_use",
                        "id": item["id"],
                        "name": item["name"],
                        "input": item["args"],
                    })
            anthropic_messages.append({"role": "assistant", "content": content})

    usage = Usage()
    current_tool_name = None
    current_tool_json = ""
    current_tool_id = None

    with client.messages.stream(
        model=model,
        max_tokens=16384,
        system=system,
        messages=anthropic_messages,
        tools=anthropic_tools,
    ) as stream:
        for event in stream:
            if event.type == "content_block_start":
                if event.content_block.type == "tool_use":
                    current_tool_name = event.content_block.name
                    current_tool_id = event.content_block.id
                    current_tool_json = ""
            elif event.type == "content_block_delta":
                if event.delta.type == "text_delta":
                    yield TextDelta(event.delta.text)
                elif event.delta.type == "input_json_delta":
                    current_tool_json += event.delta.partial_json
            elif event.type == "content_block_stop":
                if current_tool_name:
                    import json
                    args = json.loads(current_tool_json) if current_tool_json else {}
                    yield ToolCall(current_tool_name, args)
                    # Stash the id so the caller can build tool_result messages
                    yield _ToolMeta(current_tool_id)
                    current_tool_name = None
                    current_tool_json = ""
                    current_tool_id = None
            elif event.type == "message_delta":
                if hasattr(event, "usage") and event.usage:
                    usage.output_tokens = event.usage.output_tokens
            elif event.type == "message_start":
                if hasattr(event.message, "usage") and event.message.usage:
                    usage.input_tokens = event.message.usage.input_tokens

    yield Done(usage)


@dataclass
class _ToolMeta:
    """Internal: carries Anthropic tool_use_id so the agent can build tool_result messages."""
    tool_use_id: str


# ---------------------------------------------------------------------------
# OpenAI
# ---------------------------------------------------------------------------

def _stream_openai(model, system, messages, tools):
    # GPT-5.4 "-pro" variants are reasoning-only and require the Responses API.
    if "-pro" in model:
        yield from _stream_openai_responses(model, system, messages, tools)
        return

    import json
    from openai import OpenAI

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"], base_url=os.environ.get("OPENAI_BASE_URL", None))

    # Convert tools to OpenAI format
    openai_tools = [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["input_schema"],
            },
        }
        for t in tools
    ]

    # Convert messages to OpenAI format
    openai_messages = [{"role": "system", "content": system}]
    for msg in messages:
        if msg["role"] == "user":
            if isinstance(msg["content"], str):
                openai_messages.append({"role": "user", "content": msg["content"]})
            elif isinstance(msg["content"], list):
                for item in msg["content"]:
                    if item.get("type") == "tool_result":
                        openai_messages.append({
                            "role": "tool",
                            "tool_call_id": item["tool_call_id"],
                            "content": item["content"],
                        })
        elif msg["role"] == "assistant":
            oai_msg = {"role": "assistant", "content": None}
            tool_calls = []
            text_parts = []
            for item in msg["content"]:
                if item.get("type") == "text":
                    text_parts.append(item["text"])
                elif item.get("type") == "tool_call":
                    tool_calls.append({
                        "id": item["id"],
                        "type": "function",
                        "function": {"name": item["name"], "arguments": json.dumps(item["args"])},
                    })
            if text_parts:
                oai_msg["content"] = "\n".join(text_parts)
            if tool_calls:
                oai_msg["tool_calls"] = tool_calls
            openai_messages.append(oai_msg)

    usage = Usage()
    tool_calls_acc = {}  # index -> {id, name, args_json}

    response = client.chat.completions.create(
        model=model,
        messages=openai_messages,
        tools=openai_tools,
        stream=True,
        stream_options={"include_usage": True},
    )

    for chunk in response:
        if chunk.usage:
            usage.input_tokens = chunk.usage.prompt_tokens or 0
            usage.output_tokens = chunk.usage.completion_tokens or 0

        if not chunk.choices:
            continue

        delta = chunk.choices[0].delta

        if delta.content:
            yield TextDelta(delta.content)

        if delta.tool_calls:
            for tc in delta.tool_calls:
                idx = tc.index
                if idx not in tool_calls_acc:
                    tool_calls_acc[idx] = {"id": tc.id or "", "name": "", "args_json": ""}
                if tc.id:
                    tool_calls_acc[idx]["id"] = tc.id
                if tc.function and tc.function.name:
                    tool_calls_acc[idx]["name"] = tc.function.name
                if tc.function and tc.function.arguments:
                    tool_calls_acc[idx]["args_json"] += tc.function.arguments

        if chunk.choices[0].finish_reason == "tool_calls":
            for idx in sorted(tool_calls_acc.keys()):
                tc = tool_calls_acc[idx]
                args = json.loads(tc["args_json"]) if tc["args_json"] else {}
                yield ToolCall(tc["name"], args)
                yield _ToolMeta(tc["id"])
            tool_calls_acc = {}

    yield Done(usage)


def _stream_openai_responses(model, system, messages, tools):
    """OpenAI Responses API path — required for gpt-*-pro reasoning models."""
    import json
    from openai import OpenAI

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    # Responses API tool schema: flat, no "function" wrapper.
    openai_tools = [
        {
            "type": "function",
            "name": t["name"],
            "description": t["description"],
            "parameters": t["input_schema"],
        }
        for t in tools
    ]

    # Build input list from the unified message format.
    input_items = []
    for msg in messages:
        if msg["role"] == "user":
            if isinstance(msg["content"], str):
                input_items.append({"role": "user", "content": msg["content"]})
            elif isinstance(msg["content"], list):
                for item in msg["content"]:
                    if item.get("type") == "tool_result":
                        content = item["content"]
                        if not isinstance(content, str):
                            content = json.dumps(content)
                        input_items.append({
                            "type": "function_call_output",
                            "call_id": item["tool_call_id"],
                            "output": content,
                        })
        elif msg["role"] == "assistant":
            if isinstance(msg["content"], list):
                for item in msg["content"]:
                    if item.get("type") == "text" and item.get("text"):
                        input_items.append({"role": "assistant", "content": item["text"]})
                    elif item.get("type") == "tool_call":
                        input_items.append({
                            "type": "function_call",
                            "call_id": item["id"],
                            "name": item["name"],
                            "arguments": json.dumps(item["args"]),
                        })

    usage = Usage()
    pending_calls = {}  # item_id -> {call_id, name, args_json}

    stream = client.responses.create(
        model=model,
        instructions=system,
        input=input_items,
        tools=openai_tools,
        stream=True,
    )

    for event in stream:
        etype = getattr(event, "type", "")

        if etype == "response.output_text.delta":
            yield TextDelta(event.delta)

        elif etype == "response.output_item.added":
            item = getattr(event, "item", None)
            if item is not None and getattr(item, "type", "") == "function_call":
                pending_calls[item.id] = {
                    "call_id": item.call_id,
                    "name": item.name,
                    "args_json": "",
                }

        elif etype == "response.function_call_arguments.delta":
            item_id = getattr(event, "item_id", None)
            if item_id in pending_calls:
                pending_calls[item_id]["args_json"] += event.delta

        elif etype == "response.output_item.done":
            item = getattr(event, "item", None)
            if item is not None and getattr(item, "type", "") == "function_call":
                info = pending_calls.pop(item.id, None)
                if info is not None:
                    args_json = info["args_json"] or getattr(item, "arguments", "") or ""
                    args = json.loads(args_json) if args_json else {}
                    yield ToolCall(info["name"], args)
                    yield _ToolMeta(info["call_id"])

        elif etype == "response.completed":
            resp = getattr(event, "response", None)
            u = getattr(resp, "usage", None) if resp is not None else None
            if u is not None:
                usage.input_tokens = getattr(u, "input_tokens", 0) or 0
                usage.output_tokens = getattr(u, "output_tokens", 0) or 0

    yield Done(usage)
