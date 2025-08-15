import asyncio
import json
import os
import re
from typing import Any, Optional

from dotenv import load_dotenv
from openai import OpenAI as OpenAISDK

from ..handlers.cua_handler import CUAHandler
from ..types.agent import (
    ActionExecutionResult,
    AgentAction,
    AgentActionType,
    AgentConfig,
    AgentExecuteOptions,
    AgentResult,
    FunctionAction,
)
from .client import AgentClient

load_dotenv()


class OpenAICUAClient(AgentClient):
    def __init__(
        self,
        model: str = "gpt-4o",
        instructions: Optional[str] = None,  # System prompt
        config: Optional[AgentConfig] = None,
        logger: Optional[Any] = None,
        handler: Optional[CUAHandler] = None,
        viewport: Optional[dict[str, int]] = None,
        **kwargs,  # Allow for other OpenAI specific options if any
    ):
        super().__init__(model, instructions, config, logger, handler)
        # TODO pass api key
        api_key = (
            config.options.get("apiKey")
            if config and config.options
            else os.getenv("OPENAI_API_KEY")
        )
        base_url = None
        if config and config.options:
            base_url = config.options.get("baseURL") or config.options.get("api_base")

        self.logger.info(
            f"OpenAI client config - api_key: {api_key[:10] if api_key else None}..., base_url: {base_url}"
        )

        self.openai_sdk_client = OpenAISDK(api_key=api_key, base_url=base_url)

        self.tools = [
            {
                "type": "function",
                "name": "goto",
                "description": "Navigate to a specific URL",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": (
                                "The URL to navigate to. Provide a full URL, including the protocol (e.g., https://www.google.com)."
                            ),
                        },
                    },
                    "required": ["url"],
                },
            },
        ]

    def format_screenshot(self, screenshot_base64: str) -> dict:
        """Formats a screenshot for the OpenAI CUA model."""
        return {
            "type": "input_image",
            "image_url": f"data:image/png;base64,{screenshot_base64}",
        }

    def _format_initial_messages(
        self, instruction: str, screenshot_base64: Optional[str]
    ) -> list[Any]:
        messages: list[Any] = []
        if self.instructions:  # System prompt from AgentConfig.instructions
            messages.append({"role": "system", "content": self.instructions})

        user_content: list[Any] = [{"type": "input_text", "text": instruction}]
        if screenshot_base64:
            user_content.append(self.format_screenshot(screenshot_base64))
        messages.append({"role": "user", "content": user_content})
        return messages

    def _process_provider_response(
        self, response: Any
    ) -> tuple[Optional[AgentAction], Optional[str], bool, Optional[str]]:
        if not response.output:
            self.logger.error(
                "No output from OpenAI model in response object", category="agent"
            )
            return (
                None,
                "Error: No output from model",
                True,
                "Error: No output from model",
            )

        output_items = response.output

        function_call_item = next(
            (item for item in output_items if item.type == "function_call"), None
        )
        reasoning_item = next(
            (item for item in output_items if item.type == "reasoning"), None
        )
        message_item = next(
            (item for item in output_items if item.type == "message"), None
        )

        reasoning_text = None
        if (
            reasoning_item
            and reasoning_item.summary
            and isinstance(reasoning_item.summary, list)
            and len(reasoning_item.summary) > 0
        ):
            reasoning_text = reasoning_item.summary[0].text

        final_model_message = None
        if (
            message_item
            and message_item.content
            and isinstance(message_item.content, list)
        ):
            final_model_message_parts = [
                content_item.text
                for content_item in message_item.content
                if hasattr(content_item, "text") and content_item.type == "output_text"
            ]
            if final_model_message_parts:
                final_model_message = " ".join(final_model_message_parts)

        agent_action: Optional[AgentAction] = None

        if function_call_item:
            try:
                arguments = (
                    json.loads(function_call_item.arguments)
                    if isinstance(function_call_item.arguments, str)
                    else function_call_item.arguments
                )
                # Ensure arguments is a dict, even if empty
                if not isinstance(arguments, dict):
                    self.logger.debug(
                        f"Function call arguments are not a dict: {arguments}. Using empty dict.",
                        category="agent",
                    )
                    arguments = {}

                function_action_payload = FunctionAction(
                    type="function", name=function_call_item.name, arguments=arguments
                )  # type: ignore
                agent_action = AgentAction(
                    action_type="function",  # Literal 'function'
                    action=AgentActionType(root=function_action_payload),
                    reasoning=reasoning_text,  # Reasoning applies to this action
                    status=(
                        function_call_item.status
                        if hasattr(function_call_item, "status")
                        else "in_progress"
                    ),  # function_call might not have status
                    step=[item.model_dump() for item in output_items],
                )
                return agent_action, reasoning_text, False, final_model_message
            except json.JSONDecodeError as e_json:
                self.logger.error(
                    f"JSONDecodeError for function_call arguments: {function_call_item.arguments}. Error: {e_json}",
                    category="agent",
                )
                return (
                    None,
                    reasoning_text,
                    True,
                    f"Error: Invalid JSON arguments for function call {function_call_item.name}",
                )
            except Exception as e_parse_fn:
                self.logger.error(
                    f"Error parsing function_call_item: {e_parse_fn}", category="agent"
                )
                return (
                    None,
                    reasoning_text,
                    True,
                    f"Error: Failed to parse function_call action: {e_parse_fn}",
                )

        # If no function_call, the task might be complete or just a message/reasoning turn.
        task_complete_reason = (
            final_model_message
            if final_model_message
            else "No further actions from model."
        )
        if (
            not final_model_message and reasoning_text and not agent_action
        ):  # If only reasoning, it's not task completion by message
            task_complete_reason = "Model provided reasoning but no executable action."
        self.logger.info(
            f"OpenAI CUA: Task appears complete or requires user input. Reason: {task_complete_reason}",
            category="agent",
        )
        return None, reasoning_text, True, final_model_message

    def _format_action_feedback(
        self,
        action_type_performed: str,
        call_id_performed: str,
        action_result: ActionExecutionResult,
    ) -> list[Any]:
        if not call_id_performed:
            self.logger.error(
                "Missing call_id for formatting action feedback.", category="agent"
            )
            return [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "Error: Internal error, missing call_id for feedback."
                            ),
                        }
                    ],
                }
            ]

        output_item_type = "function_call_output"

        output_payload: Any
        if action_result["success"]:
            # Function results are often simple strings or JSON strings.
            output_payload = json.dumps(
                {
                    "status": "success",
                    "detail": f"Function {action_type_performed} executed.",
                }
            )
        else:
            error_message = f"Action {action_type_performed} failed: {action_result.get('error', 'Unknown error')}"
            self.logger.info(
                f"Formatting failed action feedback for OpenAI: {error_message}",
                category="agent",
            )
            output_payload = json.dumps({"status": "error", "detail": error_message})

        return [
            {
                "type": output_item_type,
                "call_id": call_id_performed,
                "output": output_payload,
            }
        ]

    async def run_task(
        self,
        instruction: str,
        max_steps: int = 20,
        options: Optional[AgentExecuteOptions] = None,
    ) -> AgentResult:
        self.logger.debug(
            f"OpenAI CUA starting task: '{instruction}' with max_steps: {max_steps}",
            category="agent",
        )

        if not self.handler:
            self.logger.error(
                "CUAHandler not available for OpenAIClient.", category="agent"
            )
            return AgentResult(
                completed=False,
                actions=[],
                message="Internal error: Handler not set.",
                usage={"input_tokens": 0, "output_tokens": 0, "inference_time_ms": 0},
            )

        await self.handler.inject_cursor()
        current_screenshot_b64 = await self.handler.get_screenshot_base64()

        current_input_items: list[Any] = self._format_initial_messages(
            instruction, current_screenshot_b64
        )

        actions_taken: list[AgentAction] = []
        total_input_tokens = 0
        total_output_tokens = 0
        total_inference_time_ms = 0  # Placeholder

        for step_count in range(max_steps):
            self.logger.info(
                f"OpenAI CUA - Step {step_count + 1}/{max_steps}",
                category="agent",
            )

            start_time = asyncio.get_event_loop().time()
            try:
                # 使用标准的 Chat Completions API 而不是 Computer Use API
                # 将消息格式转换为标准格式

                messages = []
                for item in current_input_items:
                    if isinstance(item, dict):
                        if item.get("role") == "system":
                            messages.append(
                                {"role": "system", "content": item.get("content", "")}
                            )
                        elif item.get("role") == "user":
                            content = item.get("content", [])
                            if isinstance(content, list):
                                # 处理多模态内容
                                user_content = []
                                for c in content:
                                    if c.get("type") == "input_text":
                                        user_content.append(
                                            {"type": "text", "text": c.get("text", "")}
                                        )
                                    elif c.get("type") == "input_image":
                                        # 从 format_screenshot 方法返回的格式中提取 image_url
                                        image_url = c.get("image_url", "")
                                        user_content.append(
                                            {
                                                "type": "image_url",
                                                "image_url": {"url": image_url},
                                            }
                                        )

                                messages.append(
                                    {"role": "user", "content": user_content}
                                )
                            else:
                                messages.append({"role": "user", "content": content})

                # 如果没有消息，添加一个默认消息
                if not messages:
                    messages = [
                        {"role": "user", "content": "请分析当前页面并执行指定任务"}
                    ]

                response = self.openai_sdk_client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=1000,
                )
                print("--------------------------------")
                print(response)
                end_time = asyncio.get_event_loop().time()
                total_inference_time_ms += int((end_time - start_time) * 1000)

                # 处理智谱AI的usage字段差异
                if hasattr(response, "usage") and response.usage:
                    # 智谱AI可能使用不同的字段名
                    input_tokens = getattr(
                        response.usage, "input_tokens", None
                    ) or getattr(response.usage, "prompt_tokens", 0)
                    output_tokens = getattr(
                        response.usage, "output_tokens", None
                    ) or getattr(response.usage, "completion_tokens", 0)
                    total_input_tokens += input_tokens
                    total_output_tokens += output_tokens
                    self.logger.info(
                        f"Token usage - input: {input_tokens}, output: {output_tokens}"
                    )

            except Exception as e:
                self.logger.error(f"OpenAI API call failed: {e}", category="agent")
                # Ensure usage is a valid AgentUsage object or None
                usage_obj = {
                    "input_tokens": total_input_tokens,
                    "output_tokens": total_output_tokens,
                    "inference_time_ms": total_inference_time_ms,
                }
                return AgentResult(
                    actions=[act.action for act in actions_taken if act.action],
                    message=f"OpenAI API error: {e}",
                    completed=True,
                    usage=usage_obj,
                )

            # 处理标准 Chat Completions 响应
            if response.choices and response.choices[0].message:
                message_content = response.choices[0].message.content
                self.logger.info(f"GLM API response: {message_content}")

                # 解析响应中的操作指令
                agent_action = self._parse_action_from_response(message_content)

                if agent_action:
                    # 执行解析出的操作
                    self.logger.info(f"Executing action: {agent_action.action_type}")

                    # 🔧 GLM-4.5V坐标转换：千分比 → 像素坐标
                    if (
                        agent_action.action_type == "click"
                        and hasattr(agent_action, "action")
                        and agent_action.action
                        and hasattr(agent_action.action.root, "x")
                        and hasattr(agent_action.action.root, "y")
                    ):
                        # 获取视口尺寸
                        viewport = self.handler.page.viewport_size
                        viewport_width = viewport["width"]
                        viewport_height = viewport["height"]

                        # GLM-4.5V返回的是千分比坐标，需要转换为实际像素
                        glm_x = agent_action.action.root.x
                        glm_y = agent_action.action.root.y

                        # 转换公式：千分比 → 实际像素坐标
                        actual_x = int((glm_x / 1000) * viewport_width)
                        actual_y = int((glm_y / 1000) * viewport_height)

                        self.logger.info(
                            f"GLM-4.5V坐标转换: 千分比({glm_x}, {glm_y}) → 像素({actual_x}, {actual_y})"
                        )
                        self.logger.info(
                            f"视口尺寸: {viewport_width}x{viewport_height}"
                        )

                        # 更新坐标
                        agent_action.action.root.x = actual_x
                        agent_action.action.root.y = actual_y

                    action_result = await self.handler.perform_action(agent_action)
                    actions_taken.append(agent_action)

                    # 获取执行后的新截图
                    new_screenshot_b64 = await self.handler.get_screenshot_base64()

                    # 检查是否需要继续
                    if action_result.get("success", False):
                        # 如果操作成功且只有一步，可以标记为完成
                        task_completed = True
                    else:
                        # 操作失败，继续尝试
                        current_input_items = [
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "input_text",
                                        "text": f"Previous action failed: {action_result.get('error', 'Unknown error')}. Please try a different approach.",
                                    },
                                    self.format_screenshot(new_screenshot_b64),
                                ],
                            }
                        ]
                        continue
                else:
                    # 没有解析到操作，标记为完成
                    task_completed = True

                if task_completed:
                    return AgentResult(
                        actions=[act.action for act in actions_taken if act.action],
                        message=message_content or "Task completed successfully",
                        completed=True,
                        usage={
                            "input_tokens": total_input_tokens,
                            "output_tokens": total_output_tokens,
                            "inference_time_ms": total_inference_time_ms,
                        },
                    )
            else:
                self.logger.error("No response from GLM API")
                return AgentResult(
                    actions=[],
                    message="No response from GLM API",
                    completed=True,
                    usage={
                        "input_tokens": total_input_tokens,
                        "output_tokens": total_output_tokens,
                        "inference_time_ms": total_inference_time_ms,
                    },
                )

        self.logger.info("Max steps reached for OpenAI CUA task.", category="agent")
        usage_obj = {
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens,
            "inference_time_ms": total_inference_time_ms,
        }
        return AgentResult(
            actions=[act.action for act in actions_taken if act.action],
            message="Max steps reached.",
            completed=False,
            usage=usage_obj,
        )

    def _parse_action_from_response(
        self, message_content: str
    ) -> Optional[AgentAction]:
        """解析GLM响应中的操作指令"""
        import re
        from ..types.agent import (
            ClickAction,
            TypeAction,
            ScrollAction,
            WaitAction,
            AgentActionType,
        )

        if not message_content:
            return None

        message_content = message_content.strip()

        # 解析点击指令: "CLICK: x=150, y=200"
        click_pattern = r"CLICK:\s*x\s*=\s*(\d+)\s*,\s*y\s*=\s*(\d+)"
        click_match = re.search(click_pattern, message_content, re.IGNORECASE)
        if click_match:
            x, y = int(click_match.group(1)), int(click_match.group(2))
            click_action = ClickAction(type="click", x=x, y=y, button="left")
            return AgentAction(
                action_type="click",
                action=AgentActionType(root=click_action),
                reasoning=f"Clicking at coordinates ({x}, {y})",
            )

        # 解析输入指令: "TYPE: text=hello world" 或 "TYPE: x=100, y=200, text=hello world"
        type_pattern_with_coords = (
            r"TYPE:\s*x\s*=\s*(\d+)\s*,\s*y\s*=\s*(\d+)\s*,\s*text\s*=\s*(.+?)(?:\n|$)"
        )
        type_match_with_coords = re.search(
            type_pattern_with_coords, message_content, re.IGNORECASE
        )
        if type_match_with_coords:
            x, y, text = (
                int(type_match_with_coords.group(1)),
                int(type_match_with_coords.group(2)),
                type_match_with_coords.group(3).strip(),
            )

            # 🔧 GLM-4.5V坐标转换：千分比 → 像素坐标
            viewport = self.handler.page.viewport_size
            viewport_width = viewport["width"]
            viewport_height = viewport["height"]

            # GLM-4.5V返回的是千分比坐标，需要转换为实际像素
            actual_x = int((x / 1000) * viewport_width)
            actual_y = int((y / 1000) * viewport_height)

            self.logger.info(
                f"GLM-4.5V TYPE坐标转换: 千分比({x}, {y}) → 像素({actual_x}, {actual_y})"
            )

            # 🧹 清理GLM-4.5V响应中的特殊标记
            clean_text = self._clean_glm_response_text(text)

            type_action = TypeAction(
                type="type", text=clean_text, x=actual_x, y=actual_y
            )
            return AgentAction(
                action_type="type",
                action=AgentActionType(root=type_action),
                reasoning=f"Typing text '{clean_text}' at coordinates ({actual_x}, {actual_y})",
            )

        # 解析简单输入指令: "TYPE: text=hello world" (不带坐标)
        type_pattern = r"TYPE:\s*text\s*=\s*(.+?)(?:\n|$)"
        type_match = re.search(type_pattern, message_content, re.IGNORECASE)
        if type_match:
            text = type_match.group(1).strip()
            # 🧹 清理GLM-4.5V响应中的特殊标记
            clean_text = self._clean_glm_response_text(text)

            type_action = TypeAction(type="type", text=clean_text)
            return AgentAction(
                action_type="type",
                action=AgentActionType(root=type_action),
                reasoning=f"Typing text: {clean_text}",
            )

        # 解析滚动指令: "SCROLL: x=500, y=300, scroll_y=-100"
        scroll_pattern = r"SCROLL:\s*x\s*=\s*(\d+)\s*,\s*y\s*=\s*(\d+)(?:\s*,\s*scroll_x\s*=\s*([+-]?\d+))?\s*(?:\s*,\s*scroll_y\s*=\s*([+-]?\d+))?"
        scroll_match = re.search(scroll_pattern, message_content, re.IGNORECASE)
        if scroll_match:
            x, y = int(scroll_match.group(1)), int(scroll_match.group(2))
            scroll_x = int(scroll_match.group(3)) if scroll_match.group(3) else 0
            scroll_y = int(scroll_match.group(4)) if scroll_match.group(4) else 0
            scroll_action = ScrollAction(
                type="scroll", x=x, y=y, scroll_x=scroll_x, scroll_y=scroll_y
            )
            return AgentAction(
                action_type="scroll",
                action=AgentActionType(root=scroll_action),
                reasoning=f"Scrolling at ({x}, {y}) with scroll_x={scroll_x}, scroll_y={scroll_y}",
            )

        # 解析等待指令: "WAIT: milliseconds=2000"
        wait_pattern = r"WAIT:\s*milliseconds\s*=\s*(\d+)"
        wait_match = re.search(wait_pattern, message_content, re.IGNORECASE)
        if wait_match:
            milliseconds = int(wait_match.group(1))
            wait_action = WaitAction(type="wait", miliseconds=milliseconds)
            return AgentAction(
                action_type="wait",
                action=AgentActionType(root=wait_action),
                reasoning=f"Waiting for {milliseconds} milliseconds",
            )

        # 增强解析：处理GLM-4.5V可能的各种响应格式

        # 1. 从自然语言中提取点击坐标
        coord_patterns = [
            r"(?:点击|click).*?(?:坐标|coordinates?).*?[(\[]?\s*(\d+)\s*[,，]\s*(\d+)\s*[)\]]?",
            r"[(\[]?\s*(\d+)\s*[,，]\s*(\d+)\s*[)\]]?.*?(?:点击|click)",
            r"x\s*[:=]\s*(\d+).*?y\s*[:=]\s*(\d+)",
            r"位置\s*[(\[]?\s*(\d+)\s*[,，]\s*(\d+)\s*[)\]]?",
        ]

        for pattern in coord_patterns:
            coord_match = re.search(pattern, message_content, re.IGNORECASE)
            if coord_match:
                x, y = int(coord_match.group(1)), int(coord_match.group(2))
                click_action = ClickAction(type="click", x=x, y=y, button="left")
                return AgentAction(
                    action_type="click",
                    action=AgentActionType(root=click_action),
                    reasoning=f"Extracted click coordinates from natural language: ({x}, {y})",
                )

        # 2. 如果GLM返回了描述性文字，尝试智能推断操作
        # 检查是否提到了点击操作
        if re.search(r"点击|click", message_content, re.IGNORECASE):
            # 这里可以添加更智能的坐标推断逻辑
            # 暂时返回None，让系统提示GLM返回正确格式
            self.logger.warning(
                f"GLM returned descriptive text instead of action command: {message_content}"
            )
            self.logger.warning(
                "Please check if the system prompt is correctly instructing GLM to return action commands"
            )

        # 3. 检查是否提到了输入操作
        if re.search(r"输入|input|type", message_content, re.IGNORECASE):
            # 尝试提取要输入的文本
            input_patterns = [
                r"输入[\"']([^\"']+)[\"']",
                r"输入\s*[:：]\s*([^\n]+)",
                r"type\s*[:：]\s*([^\n]+)",
            ]

            for pattern in input_patterns:
                input_match = re.search(pattern, message_content, re.IGNORECASE)
                if input_match:
                    text = input_match.group(1).strip()
                    type_action = TypeAction(type="type", text=text)
                    return AgentAction(
                        action_type="type",
                        action=AgentActionType(root=type_action),
                        reasoning=f"Extracted text input from natural language: {text}",
                    )

        return None

    def _clean_glm_response_text(self, text: str) -> str:
        """
        清理GLM-4.5V响应中的特殊标记
        移除如 <|end_of_box|>、<|start_of_box|> 等标记
        """
        if not text:
            return text

        # 定义需要清理的GLM特殊标记模式
        glm_markers = [
            r"<\|end_of_box\|>",
            r"<\|start_of_box\|>",
            r"<\|end_of_text\|>",
            r"<\|start_of_text\|>",
            r"<\|.*?\|>",  # 通用的GLM标记模式
        ]

        clean_text = text
        for pattern in glm_markers:
            clean_text = re.sub(pattern, "", clean_text, flags=re.IGNORECASE)

        # 清理多余的空白字符
        clean_text = clean_text.strip()

        if clean_text != text:
            self.logger.info(f"🧹 清理GLM响应文本: '{text}' → '{clean_text}'")

        return clean_text

    def key_to_playwright(self, key: str) -> str:
        """Converts a key name if OpenAI CUA uses specific names not covered by CUAHandler."""
        return key
