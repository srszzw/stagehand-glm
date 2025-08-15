"""Stagehand - The AI Browser Automation Framework"""

from importlib.metadata import version as get_version

from .agent import Agent
from .config import StagehandConfig, default_config
from .handlers.observe_handler import ObserveHandler
from .llm import LLMClient
from .logging import LogConfig, configure_logging
from .main import Stagehand
from .metrics import StagehandFunctionName, StagehandMetrics
from .page import StagehandPage
from .schemas import (
    ActOptions,
    ActResult,
    AgentConfig,
    AgentExecuteOptions,
    AgentExecuteResult,
    AgentProvider,
    ExtractOptions,
    ExtractResult,
    ObserveOptions,
    ObserveResult,
)

__version__ = get_version("stagehand")

__all__ = [
    "Stagehand",
    "StagehandConfig",
    "StagehandPage",
    "Agent",
    "AgentConfig",
    "AgentExecuteOptions",
    "AgentExecuteResult",
    "AgentProvider",
    "ActOptions",
    "ActResult",
    "ExtractOptions",
    "ExtractResult",
    "ObserveOptions",
    "ObserveResult",
    "ObserveHandler",
    "LLMClient",
    "configure_logging",
    "StagehandFunctionName",
    "StagehandMetrics",
    "LogConfig",
]
