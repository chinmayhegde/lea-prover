"""Lea agent — the core loop. Model calls tools until done."""

import os

from google import genai
from google.genai import types

from .prompt import SYSTEM_PROMPT
from .tools import TOOLS_SCHEMA, TOOL_HANDLERS

DEFAULT_MODEL = "gemini-3-pro-preview"
MAX_TURNS = 30


def _build_tools() -> types.Tool:
    """Convert our tool schemas to Gemini FunctionDeclarations."""
    declarations = []
    for tool in TOOLS_SCHEMA:
        declarations.append(
            {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["input_schema"],
            }
        )
    return types.Tool(function_declarations=declarations)


def run(
    task: str,
    model: str = DEFAULT_MODEL,
    max_turns: int = MAX_TURNS,
    verbose: bool = False,
) -> str:
    """Run the agent on a formalization task. Returns the final assistant message."""
    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

    tools = _build_tools()
    config = types.GenerateContentConfig(
        tools=[tools],
        system_instruction=SYSTEM_PROMPT,
    )

    contents = [types.Content(role="user", parts=[types.Part.from_text(text=task)])]

    for turn in range(max_turns):
        if verbose:
            print(f"\n--- turn {turn + 1} ---")

        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=config,
        )

        # Append assistant response to history
        contents.append(response.candidates[0].content)

        # Check for function calls
        function_calls = [
            part for part in response.candidates[0].content.parts
            if part.function_call
        ]

        # Print text parts
        if verbose:
            for part in response.candidates[0].content.parts:
                if part.text:
                    print(part.text)
                elif part.function_call:
                    print(f"  -> {part.function_call.name}({dict(part.function_call.args)})")

        # If no function calls, we're done
        if not function_calls:
            text_parts = [
                part.text
                for part in response.candidates[0].content.parts
                if part.text
            ]
            return "\n".join(text_parts) if text_parts else "(no response)"

        # Execute each function call and send results back
        function_response_parts = []
        for part in function_calls:
            fc = part.function_call
            handler = TOOL_HANDLERS.get(fc.name)
            if handler:
                result = handler(dict(fc.args))
            else:
                result = f"Error: unknown tool '{fc.name}'"

            if verbose:
                preview = result[:200] + "..." if len(result) > 200 else result
                print(f"  <- {preview}")

            function_response_parts.append(
                types.Part.from_function_response(
                    name=fc.name,
                    response={"result": result},
                )
            )

        contents.append(types.Content(role="user", parts=function_response_parts))

    return "Error: max turns reached without completing the proof."
