"""Observe handler for performing observations of page elements using LLMs."""

from typing import Any, Optional

from stagehand.a11y.utils import get_accessibility_tree, get_xpath_by_resolved_object_id
from stagehand.llm.inference import observe as observe_inference
from stagehand.metrics import StagehandFunctionName  # Changed import location
from stagehand.schemas import ObserveOptions, ObserveResult
from stagehand.utils import draw_observe_overlay
from stagehand.cache import StagehandCache


class ObserveHandler:
    """Handler for processing observe operations locally."""

    def __init__(
        self, stagehand_page, stagehand_client, user_provided_instructions=None
    ):
        """
        Initialize the ObserveHandler.

        Args:
            stagehand_page: StagehandPage instance
            stagehand_client: Stagehand client instance
            user_provided_instructions: Optional custom system instructions
        """
        self.stagehand_page = stagehand_page
        self.stagehand = stagehand_client
        self.logger = stagehand_client.logger
        self.user_provided_instructions = user_provided_instructions
        # 初始化缓存管理器
        self.cache_manager = StagehandCache(logger=self.logger)

    # TODO: better kwargs
    async def observe(
        self,
        options: ObserveOptions,
        from_act: bool = False,
        use_cache: bool = True,
        cache_ttl: int = 3600,
    ) -> list[ObserveResult]:
        """
        Execute an observation operation locally.

        Args:
            options: ObserveOptions containing the instruction and other parameters
            from_act: Whether this observe call is from an act operation
            use_cache: Whether to use caching mechanism
            cache_ttl: Cache time-to-live in seconds

        Returns:
            list of ObserveResult instances
        """
        instruction = options.instruction
        if not instruction:
            instruction = (
                "Find elements that can be used for any future actions in the page. "
                "These may be navigation links, related pages, section/subsection links, "
                "buttons, or other interactive elements. Be comprehensive: if there are "
                "multiple elements that may be relevant for future actions, return all of them."
            )

        if not from_act:
            self.logger.info(
                f"Starting observation for task: '{instruction}'",
                category="observe",
            )

        # Start inference timer if available
        if hasattr(self.stagehand, "start_inference_timer"):
            self.stagehand.start_inference_timer()

        # Get DOM representation
        output_string = ""
        iframes = []

        await self.stagehand_page._wait_for_settled_dom()

        # 获取页面信息用于缓存
        page_url = self.stagehand_page._page.url
        page_title = None
        try:
            page_title = await self.stagehand_page._page.title()
        except:
            pass

        # 检查缓存（如果启用）
        if use_cache:
            cached_result = self.cache_manager.get_cached_result(
                instruction, page_url, page_title, cache_ttl
            )
            if cached_result:
                # 验证缓存的xpath是否仍然有效
                is_valid = await self.cache_manager.validate_cached_xpath(
                    self.stagehand_page, cached_result.selector
                )
                if is_valid:
                    self.logger.info("🚀 使用缓存结果，跳过LLM调用")
                    return [cached_result]
                else:
                    self.logger.info("⚠️ 缓存的xpath已失效，将重新分析")

        # Get accessibility tree data using our utility function
        self.logger.info("Getting accessibility tree data")
        tree = await get_accessibility_tree(self.stagehand_page, self.logger)
        output_string = tree["simplified"]
        iframes = tree.get("iframes", [])

        # use inference to call the llm
        observation_response = observe_inference(
            instruction=instruction,
            tree_elements=output_string,
            llm_client=self.stagehand.llm,
            user_provided_instructions=self.user_provided_instructions,
            logger=self.logger,
            log_inference_to_file=False,  # TODO: Implement logging to file if needed
            from_act=from_act,
        )

        # Extract metrics from response
        prompt_tokens = observation_response.get("prompt_tokens", 0)
        completion_tokens = observation_response.get("completion_tokens", 0)
        inference_time_ms = observation_response.get("inference_time_ms", 0)

        # Update metrics directly using the Stagehand client
        function_name = (
            StagehandFunctionName.ACT if from_act else StagehandFunctionName.OBSERVE
        )
        self.stagehand.update_metrics(
            function_name, prompt_tokens, completion_tokens, inference_time_ms
        )

        # Add iframes to the response if any
        elements = observation_response.get("elements", [])
        for iframe in iframes:
            elements.append(
                {
                    "element_id": int(iframe.get("nodeId", 0)),
                    "description": "an iframe",
                    "method": "not-supported",
                    "arguments": [],
                }
            )

        # Generate selectors for all elements
        elements_with_selectors = await self._add_selectors_to_elements(elements)

        self.logger.debug(
            "Found elements", auxiliary={"elements": elements_with_selectors}
        )

        # 保存到缓存（如果启用且有结果）
        if use_cache and elements_with_selectors:
            try:
                # 保存第一个最相关的结果到缓存
                first_result = elements_with_selectors[0]
                self.cache_manager.set_cache(
                    instruction, page_url, first_result, page_title
                )
            except Exception as e:
                self.logger.warning(f"保存缓存失败: {e}")

        # Draw overlay if requested
        if options.draw_overlay:
            await draw_observe_overlay(self.stagehand_page, elements_with_selectors)

        # Return the list of results without trying to attach _llm_response
        return elements_with_selectors

    async def _add_selectors_to_elements(
        self,
        elements: list[dict[str, Any]],
    ) -> list[ObserveResult]:
        """
        Add selectors to elements based on their element IDs.

        Args:
            elements: list of elements from LLM response

        Returns:
            list of elements with selectors added (xpaths)
        """
        result = []

        for element in elements:
            element_id = element.get("element_id")
            rest = {k: v for k, v in element.items() if k != "element_id"}

            # Generate xpath for element using CDP
            self.logger.info(
                "Getting xpath for element",
                auxiliary={"elementId": str(element_id)},
            )

            args = {"backendNodeId": element_id}
            response = await self.stagehand_page.send_cdp("DOM.resolveNode", args)
            object_id = response.get("object", {}).get("objectId")

            if not object_id:
                self.logger.info(
                    f"Invalid object ID returned for element: {element_id}"
                )
                continue

            # Use our utility function to get the XPath
            cdp_client = await self.stagehand_page.get_cdp_client()
            xpath = await get_xpath_by_resolved_object_id(cdp_client, object_id)

            if not xpath:
                self.logger.info(f"Empty xpath returned for element: {element_id}")
                continue

            result.append(ObserveResult(**{**rest, "selector": f"xpath={xpath}"}))

        return result
