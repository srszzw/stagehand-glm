"""
带缓存功能的后台管理系统自动登录测试
演示如何使用 Stagehand 缓存机制提升性能
"""

import asyncio
import os
import time

from dotenv import load_dotenv

from stagehand import Stagehand, StagehandConfig

# Load environment variables
load_dotenv()


async def main():
    # Create configuration with custom API base
    config = StagehandConfig(
        env="LOCAL",
        # 使用支持多模态的模型
        model_name="openai/glm-4.5",
        model_api_key=os.getenv("GLM_API_KEY"),
        model_api_base=os.getenv(
            "GLM_API_BASE", "https://open.bigmodel.cn/api/paas/v4/"
        ),  # 支持自定义API地址，提供默认值
        # 🖥️ 配置全屏浏览器启动选项
        local_browser_launch_options={
            "headless": False,
            "args": [
                "--start-maximized",  # 启动时最大化窗口
                "--start-fullscreen",  # 全屏模式
                "--disable-blink-features=AutomationControlled",
                "--no-default-browser-check",
                "--disable-extensions",
                "--disable-web-security",  # 禁用web安全限制
                "--disable-features=VizDisplayCompositor",  # 提高渲染性能
            ],
            "viewport": {"width": 1920, "height": 1080},  # 设置更大的视口尺寸
        },
    )

    stagehand = Stagehand(config)

    try:
        print("\n启动带缓存功能的后台管理系统自动登录测试...")
        # Initialize Stagehand
        await stagehand.init()

        page = stagehand.page

        # 🖥️ 显示当前浏览器视口信息（全屏配置）
        viewport = page.viewport_size
        print(f"当前浏览器视口尺寸: {viewport['width']}x{viewport['height']}")
        print("使用全屏浏览器配置，无需手动调整视口尺寸")

        # 导航到登录页面
        print("导航到后台管理登录页面...")
        await page.goto("https://vue.ruoyi.vip/login?redirect=%2Findex")

        # 等待页面加载完成
        await page.wait_for_timeout(8000)
        print("等待页面资源加载完成...")

        # 登录重试循环
        max_attempts = 5  # 减少重试次数，因为缓存会提高成功率
        attempt = 0
        login_successful = False

        while attempt < max_attempts and not login_successful:
            attempt += 1
            print(f"\n第 {attempt} 次登录尝试...")
            current_url = page.url
            if "login" not in current_url.lower():
                print("登录成功！已进入后台管理系统")
                login_successful = True
                break

            try:
                # 每次重试前清空输入框并重新输入
                print("清空并重新填写登录信息...")

                # 输入用户名 - 新方法：observe + locator.fill()
                print("输入用户名: admin")
                start_time = time.time()

                # 使用缓存观察用户名输入框
                username_elements = await page.observe(
                    "找到用户名输入框", use_cache=True, cache_ttl=7200
                )
                if username_elements:
                    username_selector = username_elements[0].selector
                    print(f"  用户名框定位: {username_selector}")
                    # 直接使用 locator 填充值
                    await page.locator(username_selector).fill("admin")
                    print("  用户名输入成功")
                else:
                    print("  未找到用户名输入框")

                username_time = time.time() - start_time
                print(f"  用户名输入耗时: {username_time:.2f}秒")

                # await page.wait_for_timeout(1000)

                # 输入密码 - 新方法：observe + locator.fill()
                print("输入密码: admin123")
                start_time = time.time()

                # 使用缓存观察密码输入框
                password_elements = await page.observe(
                    "找到密码输入框", use_cache=True, cache_ttl=7200
                )
                if password_elements:
                    password_selector = password_elements[0].selector
                    print(f"  密码框定位: {password_selector}")
                    # 直接使用 locator 填充值
                    await page.locator(password_selector).fill("admin123")
                    print("  密码输入成功")
                else:
                    print("  未找到密码输入框")

                password_time = time.time() - start_time
                print(f"  密码输入耗时: {password_time:.2f}秒")

                # 使用Agent一体化处理验证码识别和填写
                print("使用Agent一体化处理验证码...")
                start_time = time.time()

                # 创建验证码处理Agent
                captcha_agent = stagehand.agent(
                    provider="openai",
                    model="glm-4.5v",
                    instructions="""你是一个验证码处理专家。你需要：
1. 仔细观察页面中的验证码图片，识别数学表达式（如 3+5、8-2、4*3、9/3 等）
2. 计算出正确的数字结果
3. 找到验证码输入框并直接在其中输入结果

操作指令格式：
- 直接在输入框输入：TYPE: x=坐标X, y=坐标Y, text=数字结果
- 或者分步操作：
  第一步：CLICK: x=坐标X, y=坐标Y (点击输入框)
  第二步：TYPE: text=数字结果 (输入结果)

重要提示：
- 乘号用*表示，除号用/表示  
- 只输入最终的数字结果，不要输入表达式
- 推荐使用带坐标的TYPE指令，一步完成点击和输入
- TYPE指令会自动清空输入框的旧内容，确保输入干净的新值""",
                    options={
                        "apiKey": stagehand.config.model_api_key,
                        "baseURL": stagehand.config.model_api_base,
                    },
                )

                # 执行验证码识别和填写的一体化操作
                captcha_result = await captcha_agent.execute(
                    instruction="请识别页面上验证码图片中的数学表达式并计算结果，然后点击验证码输入框并输入计算结果。例如：看到'3+5'就输入'8'，看到'4*2'就输入'8'。",
                    max_steps=3,  # 步骤：识别计算→点击输入框→输入结果
                    auto_screenshot=True,
                )

                captcha_time = time.time() - start_time

                # 检查是否成功处理验证码
                captcha_success = captcha_result and captcha_result.completed

                if captcha_success:
                    print("Agent验证码处理成功，继续提交登录")

                    # 提交登录表单 - 新方法：observe + locator.click()
                    print("提交登录表单...")
                    login_start_time = time.time()

                    # 使用缓存观察登录按钮
                    login_elements = await page.observe(
                        "找到登录按钮", use_cache=True, cache_ttl=7200
                    )
                    if login_elements:
                        login_selector = login_elements[0].selector
                        print(f"  登录按钮定位: {login_selector}")
                        # 直接使用 locator 点击
                        await page.locator(login_selector).click()
                        print("  登录按钮点击成功")
                    else:
                        print("  未找到登录按钮")

                    login_time = time.time() - login_start_time
                    print(f"  登录按钮点击耗时: {login_time:.2f}秒")

                    # 等待登录结果
                    await page.wait_for_timeout(1500)

                    # 检查登录是否成功
                    current_url = page.url
                    print(f"当前页面URL: {current_url}")

                    if "login" not in current_url.lower():
                        print("登录成功！已进入后台管理系统")
                        login_successful = True

                        # 显示性能统计
                        total_time = (
                            username_time + password_time + captcha_time + login_time
                        )
                        print("\n本次登录性能统计:")
                        print(f"  用户名输入: {username_time:.2f}秒")
                        print(f"  密码输入: {password_time:.2f}秒")
                        print(f"  验证码处理(Agent): {captcha_time:.2f}秒")
                        print(f"  登录按钮: {login_time:.2f}秒")
                        print(f"  总计: {total_time:.2f}秒")

                        # 显示缓存统计
                        if hasattr(page._observe_handler, "cache_manager"):
                            cache_stats = (
                                page._observe_handler.cache_manager.get_cache_stats()
                            )
                            print("\n缓存统计:")
                            print(f"  总缓存数量: {cache_stats['total_caches']}")
                            print(f"  总命中次数: {cache_stats['total_hits']}")
                            print(f"  内存缓存大小: {cache_stats['memory_cache_size']}")

                    else:
                        print(f"第 {attempt} 次登录失败，仍在登录页面")
                        if attempt < max_attempts:
                            print(f"准备进行第 {attempt + 1} 次尝试...")
                            await page.wait_for_timeout(1000)
                else:
                    print(f"第 {attempt} 次Agent验证码处理失败")
                    if attempt < max_attempts:
                        print(f"准备进行第 {attempt + 1} 次尝试...")
                        await page.wait_for_timeout(1000)

            except Exception as e:
                print(f"第 {attempt} 次登录尝试出现异常: {e}")
                if attempt < max_attempts:
                    print(f"准备进行第 {attempt + 1} 次尝试...")
                    await page.wait_for_timeout(1000)  # 等待2秒后重试

        if not login_successful:
            print(f"经过 {max_attempts} 次尝试后登录仍然失败")
        else:
            print(f"登录成功！总共尝试了 {attempt} 次")

            # 基础操作：导航到用户管理
            await page.act("点击系统管理", use_cache=True, cache_ttl=7200)

            await page.act("点击用户管理", use_cache=True, cache_ttl=7200)

            await page.act("点击新增按钮", use_cache=True, cache_ttl=7200)

            # 基础信息填写
            try:
                await page.act(
                    "在用户昵称输入框中输入张三", use_cache=True, cache_ttl=7200
                )
                # 优化用户名输入指令
                await page.act(
                    "在用户名输入框中输入zhangsan", use_cache=True, cache_ttl=7200
                )

            except Exception as e:
                print(f"基础信息填写遇到问题: {e}")

            # 使用多模态Agent处理复杂的树形控件操作
            try:
                # 创建专门用于UI操作的Agent
                ui_agent = stagehand.agent(
                    provider="openai",
                    model="glm-4.5v",  # 使用多模态模型
                    instructions="""你是一个专业的UI操作专家。你需要：
1. 仔细观察页面上的UI元素，特别是下拉框、树形控件等复杂组件
2. 识别目标元素的位置和状态
3. 按照指令精确地点击相应的控件
4. 对于树形控件，要准确识别展开/收起的三角图标
5. 操作要精确，避免点击错误的元素""",
                    options={
                        "apiKey": stagehand.config.model_api_key,
                        "baseURL": stagehand.config.model_api_base,
                    },
                )
                # 执行Agent分析
                dept_result = await ui_agent.execute(
                    instruction="找到'归属部门'或'请选择归属部门'旁边的下拉箭头，返回点击指令。必须回答格式：CLICK: x=坐标X, y=坐标Y",
                    max_steps=3,
                    auto_screenshot=True,
                )
                print(f"  部门下拉框操作结果: {dept_result}")
                expand_result = await ui_agent.execute(
                    instruction="在添加用户对话框区域，找到'归属部门'下拉框中的'若依科技'左边的三角展开图标(▷)的中间位置，返回点击指令。必须回答格式：CLICK: x=坐标X, y=坐标Y",
                    max_steps=4,
                    auto_screenshot=True,
                )
                print(f"  节点展开操作结果: {expand_result}")
                select_dept_result = await ui_agent.execute(
                    instruction="在添加用户对话框区域，找到'归属部门'下拉框中的'深圳总公司'左边的三角展开图标(▷)的中间位置，返回点击指令。必须回答格式：CLICK: x=坐标X, y=坐标Y",
                    max_steps=2,
                    auto_screenshot=True,
                )
                print(f"  部门选择操作结果: {select_dept_result}")

                select_dept_result = await ui_agent.execute(
                    instruction="在添加用户对话框区域，找到'归属部门'下拉框中的'深圳总公司'下属的研发部门，返回点击指令。必须回答格式：CLICK: x=坐标X, y=坐标Y",
                    max_steps=2,
                    auto_screenshot=True,
                )
                print(f"  部门选择操作结果: {select_dept_result}")

            except Exception as e:
                print(f"Agent部门操作遇到问题: {e}")
                print(" 尝试简化的部门选择...")

            # 角色选择
            print("\n步骤4: 选择用户角色")
            try:
                await page.act("点击角色下拉框", use_cache=True, cache_ttl=7200)
                await page.act("选择普通角色", use_cache=True, cache_ttl=7200)
                print("角色选择成功")

            except Exception as e:
                print(f"角色选择遇到问题: {e}")

            # 提交表单
            print("\n步骤5: 提交新增用户表单")
            try:
                await page.act(
                    "点击确定按钮提交用户信息", use_cache=True, cache_ttl=7200
                )

            except Exception as e:
                print(f"提交表单遇到问题: {e}")

            print("\n用户管理操作流程完成！")

    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback

        traceback.print_exc()
    finally:
        # Close the client
        print("\n🔚 关闭浏览器...")
        await stagehand.close()


if __name__ == "__main__":
    asyncio.run(main())
