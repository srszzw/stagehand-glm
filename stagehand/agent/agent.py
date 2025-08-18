import asyncio
from typing import Optional, Union

from ..handlers.cua_handler import CUAHandler
from ..schemas import (
    AgentExecuteResult,
    AgentProvider,
)
from ..types.agent import (
    AgentConfig,
    AgentExecuteOptions,
    AgentResult,
    AgentUsage,
)
from .anthropic_cua import AnthropicCUAClient
from .client import AgentClient
from .openai_cua import OpenAICUAClient

# 尝试导入Agent缓存功能（可选依赖）
try:
    from ..agent_cache import AgentCache

    AGENT_CACHE_AVAILABLE = True
except ImportError:
    AgentCache = None
    AGENT_CACHE_AVAILABLE = False

MODEL_TO_CLIENT_CLASS_MAP: dict[str, type[AgentClient]] = {
    "computer-use-preview": OpenAICUAClient,
    "claude-3-5-sonnet-latest": AnthropicCUAClient,
    "claude-3-7-sonnet-latest": AnthropicCUAClient,
    "claude-sonnet-4-20250514": AnthropicCUAClient,
    # 支持更多OpenAI兼容的模型
    "glm-4v": OpenAICUAClient,
    "glm-4.5v": OpenAICUAClient,
    "qwen-vl-max": OpenAICUAClient,
    "qwen-vl-plus": OpenAICUAClient,
}
MODEL_TO_PROVIDER_MAP: dict[str, AgentProvider] = {
    "computer-use-preview": AgentProvider.OPENAI,
    "claude-3-5-sonnet-20240620": AgentProvider.ANTHROPIC,
    "claude-3-7-sonnet-20250219": AgentProvider.ANTHROPIC,
    "claude-sonnet-4-20250514": AgentProvider.ANTHROPIC,
    # Add more mappings as needed
}

AGENT_METRIC_FUNCTION_NAME = "AGENT_EXECUTE_TASK"


class Agent:
    def __init__(self, stagehand_client, **kwargs):
        self.stagehand = stagehand_client
        self.config = AgentConfig(**kwargs) if kwargs else AgentConfig()
        self.logger = self.stagehand.logger

        # 初始化缓存机制
        cache_enabled = kwargs.get("enable_cache", False)
        cache_strategy = kwargs.get("cache_strategy", "adaptive")
        cache_ttl = kwargs.get("cache_ttl", 3600 * 24 * 365)

        if cache_enabled and not self.stagehand.use_api:
            if not AGENT_CACHE_AVAILABLE:
                # 使用info方法替代warning，因为StagehandLogger可能没有warning方法
                self.logger.info(
                    "Agent缓存功能不可用，缺少依赖包。请安装：\n"
                    "pip install 'stagehand[agent-cache]' 或 pip install opencv-python scikit-image"
                )
                self.cache = None
                self.cache_enabled = False
            else:
                try:
                    self.cache = AgentCache(
                        cache_file="agent_cache.json",
                        validation_strategy=cache_strategy,
                        default_ttl=cache_ttl,
                        logger=self.logger,
                    )
                    self.cache_enabled = True
                    self.logger.info(
                        f"Agent缓存已启用: 策略={cache_strategy}, TTL={cache_ttl}s"
                    )
                except Exception as e:
                    # 使用info方法替代warning
                    self.logger.info(f"Agent缓存初始化失败: {e}")
                    self.cache = None
                    self.cache_enabled = False
        else:
            self.cache = None
            self.cache_enabled = False

        # 调试输出
        self.logger.info(f"Agent initialized with kwargs: {kwargs}")
        self.logger.info(f"Agent config: {self.config}")
        if self.config.options:
            self.logger.info(f"Agent options: {self.config.options}")
        if self.stagehand.use_api:
            if self.config.model in MODEL_TO_PROVIDER_MAP:
                self.provider = MODEL_TO_PROVIDER_MAP[self.config.model]
            else:
                self.provider = None
                self.logger.error(
                    f"Could not infer provider for model: {self.config.model}"
                )
        else:
            if not hasattr(self.stagehand, "page") or not hasattr(
                self.stagehand.page, "_page"
            ):
                self.logger.error(
                    "Stagehand page object not available for CUAHandler initialization."
                )
                raise ValueError("Stagehand page not initialized. Cannot create Agent.")

            self.cua_handler = CUAHandler(
                stagehand=self.stagehand,
                page=self.stagehand.page._page,
                logger=self.logger,
            )

            self.viewport = self.stagehand.page._page.viewport_size
            # self.viewport = {"width": 1024, "height": 768}
            self.client: AgentClient = self._get_client()

    def _get_client(self) -> AgentClient:
        ClientClass = MODEL_TO_CLIENT_CLASS_MAP.get(self.config.model)  # noqa: N806

        # 如果模型不在映射表中，但提供了自定义baseURL，则假设是OpenAI兼容的
        if not ClientClass and self.config.options.get("baseURL"):
            self.logger.info(
                f"Using OpenAI-compatible client for custom model: {self.config.model}"
            )
            ClientClass = OpenAICUAClient

        if not ClientClass:
            self.logger.error(
                f"Unsupported model or client not mapped: {self.config.model}"
            )
            raise ValueError(
                f"Unsupported model or client not mapped: {self.config.model}"
            )

        return ClientClass(
            model=self.config.model,
            instructions=(
                self.config.instructions
                if self.config.instructions
                else """你是一个网页操作代理，必须通过精确的操作指令与网页交互。

【重要】：你必须分析截图并返回具体的操作指令，不能只是描述要做什么！

【强制要求】：你的回答必须严格按照以下格式：
- 点击操作：CLICK: x=像素X坐标, y=像素Y坐标
- 输入文字：TYPE: text=要输入的内容 (在当前焦点输入)
- 定位输入：TYPE: x=像素X坐标, y=像素Y坐标, text=要输入的内容 (先点击再输入)
- 滚动页面：SCROLL: x=500, y=300, scroll_y=-100
- 等待时间：WAIT: milliseconds=2000

【示例】：
用户说"点击登录按钮"，你必须回答："CLICK: x=350, y=200"
用户说"在输入框输入admin"，你必须回答："TYPE: x=350, y=200, text=admin"
用户说"输入用户名admin"，你必须回答："TYPE: text=admin"

【禁止】：不要返回描述性文字如"点击右侧的下拉框"，必须返回具体的操作指令！

现在分析截图，找到目标元素的精确像素坐标，返回操作指令。"""
            ),
            config=self.config,
            logger=self.logger,
            handler=self.cua_handler,
            viewport=self.viewport,
            experimental=self.stagehand.experimental,
        )

    async def execute(
        self,
        options_or_instruction: Union[AgentExecuteOptions, str, dict, None] = None,
        **kwargs,
    ) -> AgentResult:
        options: Optional[AgentExecuteOptions] = None
        options_dict = {}

        if isinstance(options_or_instruction, AgentExecuteOptions):
            options_dict = options_or_instruction.model_dump()
        elif isinstance(options_or_instruction, dict):
            options_dict = options_or_instruction.copy()
        elif isinstance(options_or_instruction, str):
            options_dict["instruction"] = options_or_instruction

        options_dict.update(kwargs)

        try:
            options = AgentExecuteOptions(**options_dict)
        except Exception as e:
            self.logger.error(f"Invalid agent execute options: {e}")
            raise

        if not options.instruction:
            self.logger.error("No instruction provided for agent execution.")
            return AgentResult(
                message="No instruction provided.",
                completed=True,
                actions=[],
                usage={},
            )

        instruction = options.instruction

        if not self.stagehand.use_api:
            # 尝试从缓存获取结果
            cached_actions = None
            if self.cache_enabled and self.cache:
                try:
                    # 获取当前页面截图
                    current_screenshot = await self.cua_handler.get_screenshot_base64()

                    # 构建页面上下文
                    page_context = {
                        "url": self.stagehand.page._page.url,
                        "title": await self.stagehand.page._page.title(),
                        "viewport": self.viewport,
                    }

                    # 检查缓存
                    cached_actions = await self.cache.get_cached_actions(
                        instruction=instruction,
                        current_screenshot=current_screenshot,
                        page_context=page_context,
                        ttl=options_dict.get("cache_ttl"),
                    )

                    if cached_actions:
                        # 缓存命中，执行缓存的操作
                        self.logger.info("🚀 Agent缓存命中，执行缓存的操作")

                        try:
                            # 将缓存的操作转换为可执行的格式
                            executable_actions = []
                            for action_dict in cached_actions:
                                agent_action = self._create_agent_action_from_dict(
                                    action_dict
                                )
                                if agent_action:
                                    executable_actions.append(agent_action)

                            # 执行缓存的操作
                            for i, agent_action in enumerate(executable_actions):
                                self.logger.info(
                                    f"执行缓存操作 {i + 1}/{len(executable_actions)}: {agent_action.action_type}"
                                )

                                # 执行操作
                                action_result = await self.cua_handler.perform_action(
                                    agent_action
                                )

                                # 添加操作间的延迟，让页面有时间响应
                                if i < len(executable_actions) - 1:  # 不是最后一个操作
                                    await asyncio.sleep(0.5)  # 500ms延迟

                                # 检查操作结果
                                if not action_result.get("success", True):
                                    self.logger.info(
                                        f"缓存操作执行失败: {action_result.get('error', '未知错误')}"
                                    )
                                    # 如果操作失败，跳出循环，让系统重新调用LLM
                                    raise Exception(
                                        f"缓存操作执行失败: {action_result.get('error', '未知错误')}"
                                    )

                                self.logger.info(f"缓存操作 {i + 1} 执行成功")

                            return AgentResult(
                                message="成功执行缓存的操作序列",
                                completed=True,
                                actions=cached_actions,
                                usage={
                                    "input_tokens": 0,
                                    "output_tokens": 0,
                                    "inference_time_ms": 0,
                                },
                            )

                        except Exception as e:
                            self.logger.info(f"执行缓存操作失败: {e}，将重新调用LLM")
                            # 如果执行失败，继续正常的LLM调用流程
                            cached_actions = None

                except Exception as e:
                    # 使用info方法替代warning
                    self.logger.info(f"缓存检查失败: {e}")
                    cached_actions = None
            self.logger.info(
                f"Agent starting execution for instruction: '{instruction}'",
                category="agent",
            )

            try:
                agent_result = await self.client.run_task(
                    instruction=instruction,
                    max_steps=self.config.max_steps,
                    options=options,
                )
            except Exception as e:
                self.logger.error(
                    f"Exception during client.run_task: {e}", category="agent"
                )
                empty_usage = AgentUsage(
                    input_tokens=0, output_tokens=0, inference_time_ms=0
                )
                return AgentResult(
                    message=f"Error: {str(e)}",
                    completed=True,
                    actions=[],
                    usage=empty_usage,
                )

            # Update metrics if usage data is available in the result
            if agent_result.usage:
                # self.stagehand.update_metrics(
                #     AGENT_METRIC_FUNCTION_NAME,
                #     agent_result.usage.get("input_tokens", 0),
                #     agent_result.usage.get("output_tokens", 0),
                #     agent_result.usage.get("inference_time_ms", 0),
                # )
                pass  # Placeholder if metrics are to be handled differently or not at all

            self.logger.info(
                f"Agent execution finished. Success: {agent_result.completed}. Message: {agent_result.message}",
                category="agent",
            )
            # To clean up pydantic model output
            actions_repr = [action.root for action in agent_result.actions]
            self.logger.debug(
                f"Agent actions: {actions_repr}",
                category="agent",
            )
            agent_result.actions = actions_repr

            # 保存成功的结果到缓存
            if (
                self.cache_enabled
                and self.cache
                and agent_result.completed
                and agent_result.actions
                and not options_dict.get("disable_cache_save", False)
            ):
                try:
                    # 获取执行后的截图
                    final_screenshot = await self.cua_handler.get_screenshot_base64()

                    # 构建页面上下文
                    page_context = {
                        "url": self.stagehand.page._page.url,
                        "title": await self.stagehand.page._page.title(),
                        "viewport": self.viewport,
                    }

                    # 保存到缓存
                    self.cache.set_cached_actions(
                        instruction=instruction,
                        actions=actions_repr,
                        screenshot=final_screenshot,
                        page_context=page_context,
                    )

                except Exception as e:
                    # 使用info方法替代warning
                    self.logger.info(f"保存Agent缓存失败: {e}")

            return agent_result
        else:
            agent_config_payload = self.config.model_dump(
                exclude_none=True, by_alias=True
            )
            agent_config_payload["provider"] = self.provider
            payload = {
                # Use the stored config
                "agentConfig": agent_config_payload,
                "executeOptions": options.model_dump(exclude_none=True, by_alias=True),
            }

            lock = self.stagehand._get_lock_for_session()
            async with lock:
                result = await self.stagehand._execute("agentExecute", payload)

            if isinstance(result, dict):
                # Ensure all expected fields are present
                # If not present in result, use defaults from AgentExecuteResult schema
                if "success" not in result:
                    raise ValueError("Response missing required field 'success'")

                # Ensure completed is set with default if not present
                if "completed" not in result:
                    result["completed"] = False

                # Add default for message if missing
                if "message" not in result:
                    result["message"] = None

                return AgentExecuteResult(**result)
            elif result is None:
                # Handle cases where the server might return None or an empty response
                # Return a default failure result or raise an error
                return AgentExecuteResult(
                    success=False,
                    completed=False,
                    message="No result received from server",
                )
            else:
                # If the result is not a dict and not None, it's unexpected
                raise TypeError(f"Unexpected result type from server: {type(result)}")

    def get_cache_stats(self) -> Optional[dict]:
        """获取Agent缓存统计信息"""
        if self.cache_enabled and self.cache:
            return self.cache.get_cache_stats()
        return None

    def clear_cache(self):
        """清空Agent缓存"""
        if self.cache_enabled and self.cache:
            self.cache.clear_cache()
            self.logger.info("Agent缓存已清空")
        else:
            # 使用info方法替代warning
            self.logger.info("Agent缓存未启用，无法清空")

    def set_cache_strategy(self, strategy: str):
        """设置缓存验证策略"""
        if self.cache_enabled and self.cache:
            self.cache.validator.strategy = strategy
            self.logger.info(f"Agent缓存策略已更新为: {strategy}")
        else:
            # 使用info方法替代warning
            self.logger.info("Agent缓存未启用，无法设置策略")

    def _create_agent_action_from_dict(self, action_dict: dict):
        """从字典创建AgentAction对象"""
        try:
            action_type = action_dict.get("type")

            # 创建具体的操作对象
            specific_action = None
            if action_type == "click":
                from ..types.agent import ClickAction

                specific_action = ClickAction(**action_dict)
            elif action_type == "double_click":
                from ..types.agent import DoubleClickAction

                specific_action = DoubleClickAction(**action_dict)
            elif action_type == "type":
                from ..types.agent import TypeAction

                specific_action = TypeAction(**action_dict)
            elif action_type == "key_press":
                from ..types.agent import KeyPressAction

                specific_action = KeyPressAction(**action_dict)
            elif action_type == "scroll":
                from ..types.agent import ScrollAction

                specific_action = ScrollAction(**action_dict)
            elif action_type == "drag":
                from ..types.agent import DragAction

                specific_action = DragAction(**action_dict)
            elif action_type == "move":
                from ..types.agent import MoveAction

                specific_action = MoveAction(**action_dict)
            elif action_type == "wait":
                from ..types.agent import WaitAction

                specific_action = WaitAction(**action_dict)
            elif action_type == "screenshot":
                from ..types.agent import ScreenshotAction

                specific_action = ScreenshotAction(**action_dict)
            elif action_type == "function":
                from ..types.agent import FunctionAction

                specific_action = FunctionAction(**action_dict)
            elif action_type == "key":
                from ..types.agent import KeyAction

                specific_action = KeyAction(**action_dict)
            else:
                self.logger.info(f"未知的操作类型: {action_type}")
                return None

            if specific_action:
                # 创建AgentActionType (RootModel)
                from ..types.agent import AgentAction, AgentActionType

                action_root_model = AgentActionType(root=specific_action)

                # 创建AgentAction对象
                agent_action = AgentAction(
                    action_type=action_type,
                    action=action_root_model,
                    reasoning="从缓存恢复的操作",
                )

                return agent_action

            return None

        except Exception as e:
            self.logger.info(f"创建AgentAction对象失败: {e}")
            return None
