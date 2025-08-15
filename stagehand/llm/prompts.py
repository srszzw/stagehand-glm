from typing import Optional

from stagehand.handlers.act_handler_utils import method_handler_map
from stagehand.types.llm import ChatMessage


def build_user_instructions_string(
    user_provided_instructions: Optional[str] = None,
) -> str:
    if not user_provided_instructions:
        return ""

    return f"""

# Custom Instructions Provided by the User

Please keep the user's instructions in mind when performing actions. If the user's instructions are not relevant to the current task, ignore them.

User Instructions:
{user_provided_instructions}"""


# extract
def build_extract_system_prompt(
    is_using_text_extract: bool = False,
    user_provided_instructions: Optional[str] = None,
) -> ChatMessage:
    base_content = """You are a JSON data extraction assistant.
Your task is to extract structured data and return it as valid JSON.

CRITICAL RULES:
- Always respond with valid JSON only
- Never include explanatory text, markdown, or code blocks
- Match the exact schema structure provided
- Use proper field names as specified in the schema
- If no data found, return empty JSON object with required fields set to empty arrays/strings

You will be given:
1. An extraction instruction with expected JSON schema
2. """

    content_detail = (
        "A text representation of a webpage to extract information from."
        if is_using_text_extract
        else "A list of DOM elements to extract from."
    )

    instructions = (
        f"Extract the exact information from the {'text-rendered webpage' if is_using_text_extract else 'DOM+accessibility tree elements'} "
        f"and format it as a valid JSON object.\n"
        f"You must respond with valid JSON only, no additional text or formatting.\n"
        f"If no information is found, return an empty JSON object {{}}."
    ).strip()

    additional_instructions = (
        """Once you are given the text-rendered webpage,
you must thoroughly and meticulously analyze it. Be very careful to ensure that you
do not miss any important information."""
        if is_using_text_extract
        else (
            "If a user is attempting to extract links or URLs, you MUST respond with ONLY the IDs of the link elements.\n"
            "Do not attempt to extract links directly from the text unless absolutely necessary. "
        )
    )

    user_instructions = build_user_instructions_string(
        user_provided_instructions,
    )

    content_parts = [
        f"{base_content}{content_detail}",
        instructions,
    ]
    if additional_instructions:
        content_parts.append(additional_instructions)
    if user_instructions:
        content_parts.append(user_instructions)

    # Join parts with newlines, filter empty strings, then replace multiple spaces
    full_content = "\n\n".join(filter(None, content_parts))
    content = " ".join(full_content.split())

    return ChatMessage(role="system", content=content)


def build_extract_user_prompt(
    instruction: str, tree_elements: str, schema_info: str = ""
) -> ChatMessage:
    """
    Build the user prompt for extraction.

    Args:
        instruction: The instruction for what to extract
        tree_elements: The DOM+accessibility tree representation
        schema_info: Optional schema information to include in the prompt

    Returns:
        User prompt for extract
    """
    schema_section = (
        f"\n\nExpected JSON structure:\n{schema_info}" if schema_info else ""
    )

    content = f"""Instruction: {instruction}
DOM+accessibility tree: {tree_elements}{schema_section}

IMPORTANT: Respond with ONLY a valid JSON object. No explanatory text, no markdown, no code blocks. Just pure JSON that matches the expected structure."""

    return ChatMessage(role="user", content=content)


def build_metadata_system_prompt() -> ChatMessage:
    """
    Build the system prompt for metadata extraction.

    Returns:
        System prompt for metadata
    """
    prompt = """You are an AI assistant that evaluates the completeness of information extraction.

Given:
1. An extraction instruction
2. The extracted data

Your task is to:
1. Determine if the extraction is complete based on the instruction
2. Provide a brief progress summary

Please respond with:
- "completed": A boolean indicating if the extraction is complete (true) or not (false)
- "progress": A brief summary of the extraction progress
"""

    return ChatMessage(role="system", content=prompt)


def build_metadata_prompt(
    instruction: str, extracted_data: dict, chunks_seen: int, chunks_total: int
) -> str:
    """
    Build the user prompt for metadata extraction.

    Args:
        instruction: The original extraction instruction
        extracted_data: The data that was extracted
        chunks_seen: Number of chunks processed
        chunks_total: Total number of chunks

    Returns:
        User prompt for metadata
    """
    prompt = f"""Extraction instruction: {instruction}

Extracted data: {extracted_data}

Chunks processed: {chunks_seen} of {chunks_total}

Evaluate if this extraction is complete according to the instruction.
"""

    return ChatMessage(role="user", content=prompt)


# observe
def build_observe_system_prompt(
    user_provided_instructions: Optional[str] = None,
) -> ChatMessage:
    tree_type_desc = "a hierarchical accessibility tree showing the semantic structure of the page. The tree is a hybrid of the DOM and the accessibility tree."

    observe_system_prompt_base = f"""
You are helping the user automate the browser by finding elements based on what the user wants to observe in the page.

You will be given:
1. an instruction of elements to observe
2. {tree_type_desc}

IMPORTANT: You must return a JSON object with this exact format:
{{
  "elements": [
    {{
      "element_id": <number>,
      "description": "<description of the element>",
      "method": "<action method>",
      "arguments": ["<argument1>", "<argument2>"]
    }}
  ]
}}

Return an array of elements that match the instruction if they exist, otherwise return {{"elements": []}}. Whenever suggesting actions, use supported playwright locator methods or preferably one of the following supported actions:
{", ".join(method_handler_map.keys())}

Always respond with valid JSON only, no explanatory text or markdown code blocks."""

    content = " ".join(observe_system_prompt_base.split())
    user_instructions_str = build_user_instructions_string(user_provided_instructions)

    final_content = content
    if user_instructions_str:
        final_content += "\n\n" + user_instructions_str

    return ChatMessage(
        role="system",
        content=final_content,
    )


def build_observe_user_message(
    instruction: str,
    tree_elements: str,
) -> ChatMessage:
    tree_or_dom = "Accessibility Tree"
    return ChatMessage(
        role="user",
        content=f"""instruction: {instruction}
{tree_or_dom}: {tree_elements}

Remember: Return only valid JSON in the exact format specified in the system prompt. No markdown, no explanations, just the JSON object with "elements" array.""",
    )


def build_act_observe_prompt(
    action: str,
    supported_actions: list[str],
    variables: Optional[dict[str, str]] = None,
) -> str:
    """
    Builds the instruction for the observeAct method to find the most relevant element for an action
    """
    instruction = f"""Find the most relevant element to perform an action on given the following action: {action}.
Provide an action for this element such as {", ".join(supported_actions)}, or any other playwright locator method. Remember that to users, buttons and links look the same in most cases.
If the action is completely unrelated to a potential action to be taken on the page, return an empty array.
ONLY return one action. If multiple actions are relevant, return the most relevant one.
If the user is asking to scroll to a position on the page, e.g., 'halfway' or 0.75, etc, you must return the argument formatted as the correct percentage, e.g., '50%' or '75%', etc.
If the user is asking to scroll to the next chunk/previous chunk, choose the nextChunk/prevChunk method. No arguments are required here.
If the action implies a key press, e.g., 'press enter', 'press a', 'press space', etc., always choose the press method with the appropriate key as argument — e.g. 'a', 'Enter', 'Space'. Do not choose a click action on an on-screen keyboard. Capitalize the first character like 'Enter', 'Tab', 'Escape' only for special keys.
If the action implies choosing an option from a dropdown, AND the corresponding element is a 'select' element, choose the selectOptionFromDropdown method. The argument should be the text of the option to select.
If the action implies choosing an option from a dropdown, and the corresponding element is NOT a 'select' element, choose the click method."""

    if variables and len(variables) > 0:
        variables_prompt = f"The following variables are available to use in the action: {', '.join(variables.keys())}. Fill the argument variables with the variable name."
        instruction += f" {variables_prompt}"

    return instruction


def build_operator_system_prompt(goal: str) -> ChatMessage:
    return ChatMessage(
        role="system",
        content=f"""You are a general-purpose agent whose job is to accomplish the user's goal across multiple model calls by running actions on the page.

You will be given a goal and a list of steps that have been taken so far. Your job is to determine if either the user's goal has been completed or if there are still steps that need to be taken.

# Your current goal
{goal}

# Important guidelines
1. Break down complex actions into individual atomic steps
2. For `act` commands, use only one action at a time, such as:
   - Single click on a specific element
   - Type into a single input field
   - Select a single option
3. Avoid combining multiple actions in one instruction
4. If multiple actions are needed, they should be separate steps""",
    )
