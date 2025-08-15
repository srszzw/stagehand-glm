# Stagehand-GLM

<div align="center">

![Logo](media/logo.png)

**基于GLM大模型的渐进式AI浏览器自动化框架**

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![GLM](https://img.shields.io/badge/GLM-4.5V-green.svg)](https://open.bigmodel.cn/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Stagehand](https://img.shields.io/badge/Based%20on-Stagehand-purple.svg)](https://github.com/browserbase/stagehand-python)

</div>

## 🌟 项目简介

**Stagehand-GLM** 是基于 [stagehand-python](https://github.com/browserbase/stagehand-python) 深度定制的AI浏览器自动化框架，专门适配了智谱AI的GLM文本和多模态大模型。它提供了渐进式的RPA操作策略，让开发者在智能便捷和成本效益之间找到最佳平衡点。

### 🎯 核心理念

- **渐进式智能**: 从缓存复用 → 文本模型 → 多模态模型的智能降级策略
- **成本优化**: 通过智能缓存减少70-90%的LLM调用，提升3-5倍性能
- **自然语言驱动**: 用简单的中文描述替代复杂的代码逻辑
- **多模态增强**: GLM-4.5V视觉理解能力处理复杂UI交互

## ✨ 项目特点

### 🧠 全面适配GLM生态
- ✅ **GLM-4.5文本模型**: 智能理解页面结构和操作指令
- ✅ **GLM-4.5V多模态**: 视觉理解复杂UI元素和验证码识别,实测GLM4.5V界面理解定位非常准确，点赞智谱GLM-4.5V!
- ✅ **API完全兼容**: 无缝集成智谱AI的API服务
- ⚠️ **其他模型**: OpenAI、Anthropic等模型兼容性待验证

### ⚡ 智能缓存机制
- 🧠 **智能缓存**: 自动缓存元素定位结果，避免重复分析
- 📈 **性能提升**: 减少70-90%的LLM调用，提升3-5倍执行速度
- 🔍 **自动验证**: 缓存失效时自动重新分析，确保操作可靠性
- 💾 **持久存储**: 支持跨会话的缓存复用

### 🎮 渐进式操作策略
1. **缓存优先**: 优先使用已缓存的元素定位信息
2. **文本模型**: 常规控件使用GLM-4.5文本模型分析
3. **多模态模型**: 复杂UI使用GLM-4.5V视觉理解
4. **原生操作**: 直接使用Playwright+XPath的传统方式

### 🚀 开发友好
- 🗣️ **自然语言**: 中文指令驱动，无需学习复杂API
- 🔧 **屏蔽底层**: 自动处理Playwright和鼠标键盘操作
- 📝 **环境变量**: 安全的配置管理方式
- 🛠️ **丰富工具**: 缓存管理、性能监控等辅助工具
- 📊 **数据提取**: 支持结构化数据提取和Pydantic模型验证

## 🚀 快速开始

### 环境准备

```bash
# 1. 克隆项目
git clone https://github.com/srszzw/stagehand-glm.git
cd stagehand-glm

# 2. 安装Python 3.11+ (推荐使用uv)
uv python install 3.11
uv venv .venv --python 3.11

# 3. 激活虚拟环境
# Windows
.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate

# 4. 安装依赖
uv pip install -e .
```

### 配置API密钥

在当前目录下创建 `.env` 文件：

```bash
# GLM-4.5V API配置
GLM_API_KEY=your_glm_api_key_here
GLM_API_BASE=https://open.bigmodel.cn/api/paas/v4/
```

### 运行示例

```bash
cd examples
uv run admin_login_cached.py
```

**📋 示例功能说明**:

本示例针对著名开源项目**若依**的在线演示网站进行了完整测试，演示了以下自动化流程：

1. **🔐 登录流程**: 
   - 导航到登录页面
   - 输入用户名和密码
   - 使用GLM-4.5V多模态模型识别数学验证码并自动输入
   - 点击登录按钮

2. **📊 后台管理操作**:
   - 点击"系统管理"菜单
   - 进入"用户管理"模块
   - 点击"新增"按钮

3. **👤 用户信息填写**:
   - 输入用户昵称
   - 输入用户名
   - 使用多模态Agent逐级选取部门(树形控件)
   - 下拉选择用户角色
   - 点击确定提交

整个过程展示了**渐进式RPA策略**的完整应用：从基础的表单填写(使用缓存)到复杂的UI交互(使用多模态视觉理解)，是企业级后台管理系统自动化的典型案例。

## 💡 核心功能示例

### 1. 基础配置

```python
import asyncio
import os
from dotenv import load_dotenv
from stagehand import Stagehand, StagehandConfig

# 加载环境变量
load_dotenv()
    
async def main():
    # 创建配置
    config = StagehandConfig(
        env="LOCAL",
        model_name="openai/glm-4.5",
        model_api_key=os.getenv("GLM_API_KEY"),
        model_api_base=os.getenv("GLM_API_BASE"),
    )
    
    stagehand = Stagehand(config)
    await stagehand.init()
    page = stagehand.page
```

### 2. 基本操作模式

```python
# 方式1: 直接使用act方法 (适合固定值场景)
await page.act("在用户名输入框输入admin", use_cache=True, cache_ttl=7200)
await page.act("在密码输入框输入admin123", use_cache=True, cache_ttl=7200)
await page.act("点击登录按钮", use_cache=True, cache_ttl=7200)

# 方式2: observe + locator模式 (适合动态值场景)
username_elements = await page.observe(
    "找到用户名输入框", 
    use_cache=True,      # 启用缓存
    cache_ttl=7200       # 缓存2小时
)
if username_elements:
    selector = username_elements[0].selector
    await page.locator(selector).fill("dynamic_username")
    print("✅ 用户名输入成功 (使用缓存)")
```

### 3. 渐进式操作策略

```python
async def smart_login(page, username, password):
    """渐进式登录策略示例"""
    
    # 策略1: 直接XPath/CSS选择器 (最快，几乎无成本)
    try:
        await page.locator("#username").fill(username)
        await page.locator("#password").fill(password)
        await page.locator("#login-btn").click()
        return "直接定位成功"
    except:
        pass
    
    # 策略2: 文本模型分析 (中等速度和成本)
    try:
        # 方式2a: 固定值使用act (缓存命中率高)
        await page.act("在用户名输入框输入admin", use_cache=True, cache_ttl=7200)
        await page.act("在密码输入框输入admin123", use_cache=True, cache_ttl=7200)
        await page.act("点击登录按钮", use_cache=True, cache_ttl=7200)
        
        # 方式2b: 动态值使用observe + locator (推荐)
        # 先观察元素位置(可缓存)，再赋值(灵活)
        username_elements = await page.observe(
            "找到用户名输入框", 
            use_cache=True, 
            cache_ttl=7200
        )
        if username_elements:
            await page.locator(username_elements[0].selector).fill(username)
        
        password_elements = await page.observe(
            "找到密码输入框", 
            use_cache=True, 
            cache_ttl=7200
        )
        if password_elements:
            await page.locator(password_elements[0].selector).fill(password)
            
        return "文本模型成功"
    except:
        pass
    
    # 策略3: 多模态分析 (最智能，成本较高)
    agent = stagehand.agent(provider="openai", model="glm-4.5v")
    result = await agent.execute(
        instruction=f"请在页面上找到登录表单，输入用户名{username}和密码{password}，然后点击登录",
        max_steps=5
    )
    return "多模态成功"
```

**💡 缓存策略说明**:

- **固定值场景**: 如果输入值固定(如测试账号)，直接使用`page.act("在用户名输入框输入admin")`，缓存命中率高
- **动态值场景**: 如果输入值经常变化，建议用`observe + locator`模式:
  - `observe`操作可以缓存(元素定位不变)
  - `locator.fill()`灵活赋值(不影响缓存)
- **避免缓存失效**: 使用`act`时，提示词中的值会作为缓存key的一部分，不同的值会导致缓存无法命中

### 4. 多模态验证码识别

```python
# 创建多模态Agent
captcha_agent = stagehand.agent(
    provider="openai",
    model="glm-4.5v",
    instructions="""你是验证码识别专家，需要：
1. 识别页面中的数学表达式验证码
2. 计算正确结果
3. 在验证码输入框中填入答案"""
)

# 执行验证码识别和填写
result = await captcha_agent.execute(
    instruction="识别验证码中的数学表达式并计算结果，然后填入验证码输入框",
    max_steps=3,
    auto_screenshot=True  # 自动截图用于调试
)

if result.completed:
    print("✅ 验证码识别成功")
```

### 5. 复杂UI交互

```python
# 处理复杂的树形控件
ui_agent = stagehand.agent(
    provider="openai", 
    model="glm-4.5v",
    instructions="你是UI操作专家，精确识别和操作复杂控件"
)

# 展开树形菜单
await ui_agent.execute(
    instruction="找到'系统管理'菜单的展开箭头并点击",
    max_steps=2
)

# 选择子菜单
await ui_agent.execute(
    instruction="在展开的菜单中找到'用户管理'并点击",
    max_steps=2
)
```

### 6. 批量表单操作

```python
# 定义表单字段
form_fields = [
    {"instruction": "找到用户名输入框", "value": "zhangsan", "cache_ttl": 7200},
    {"instruction": "找到密码输入框", "value": "password123", "cache_ttl": 7200},
    {"instruction": "找到邮箱输入框", "value": "user@example.com", "cache_ttl": 3600},
]

# 批量填写 (支持缓存)
for field in form_fields:
    elements = await page.observe(
        field["instruction"], 
        use_cache=True, 
        cache_ttl=field["cache_ttl"]
    )
    if elements:
        await page.locator(elements[0].selector).fill(field["value"])
        print(f"✅ {field['instruction']} 填写完成")
```

### 7. 智能数据提取

```python
from pydantic import BaseModel, Field
from typing import List

# 定义数据结构
class UserInfo(BaseModel):
    username: str = Field(..., description="用户名")
    email: str = Field(..., description="邮箱地址")
    role: str = Field(..., description="用户角色")

class UserList(BaseModel):
    users: List[UserInfo] = Field(..., description="用户列表")
    total_count: int = Field(..., description="总用户数")

# 简单文本提取
summary = await page.extract("获取页面第一段的摘要内容")
print(f"页面摘要: {summary}")

# 结构化数据提取
user_data = await page.extract(
    "提取用户管理页面中的所有用户信息，包括用户名、邮箱和角色",
    schema=UserList
)

# 使用提取的数据
print(f"总共找到 {user_data.total_count} 个用户:")
for user in user_data.users:
    print(f"- {user.username} ({user.email}) - {user.role}")

# 表格数据提取
class ProductInfo(BaseModel):
    name: str = Field(..., description="商品名称")
    price: float = Field(..., description="价格")
    stock: int = Field(..., description="库存数量")

class ProductTable(BaseModel):
    products: List[ProductInfo] = Field(..., description="商品列表")

products = await page.extract(
    "提取商品表格中的所有商品信息",
    schema=ProductTable
)
```

**💡 数据提取优势**:

- **结构化输出**: 使用Pydantic模型确保数据格式一致性
- **类型验证**: 自动验证提取数据的类型和格式
- **智能理解**: GLM模型能理解复杂的页面结构和数据关系
- **灵活描述**: 支持自然语言描述提取需求

## 🛠️ 缓存管理

### 命令行工具

```bash
# 查看缓存统计
python cache_manager_tool.py --stats

# 清理过期缓存
python cache_manager_tool.py --clear --expired-only

# 搜索特定缓存
python cache_manager_tool.py --search "用户名"

# 导出/导入缓存
python cache_manager_tool.py --export backup.json
python cache_manager_tool.py --import backup.json
```

### 程序化管理

```python
# 获取缓存统计
if hasattr(page._observe_handler, "cache_manager"):
    stats = page._observe_handler.cache_manager.get_cache_stats()
    print(f"缓存数量: {stats['total_caches']}")
    print(f"命中次数: {stats['total_hits']}")
    print(f"命中率: {stats['total_hits']/max(stats['total_caches'],1)*100:.1f}%")
```

## 📊 性能对比

| 操作类型 | 传统方式 | 缓存命中 | 性能提升 | 成本节省 |
|---------|---------|---------|---------|---------|
| 简单定位 | 2-3秒 | 0.1秒 | **20x** | 95% |
| 复杂查找 | 5-8秒 | 0.2秒 | **30x** | 90% |
| 表单填充 | 10-15秒 | 1-2秒 | **10x** | 85% |
| 验证码识别 | 3-5秒 | 3-5秒 | 1x | 0% (不缓存) |

## 🎯 使用场景

### ✅ 适用场景
- 🏢 **企业级RPA**: 后台管理系统自动化
- 🧪 **Web测试**: 自动化测试和回归测试
- 📊 **数据采集**: 智能网页数据抓取和结构化提取
- 🔄 **重复操作**: 批量表单填写和处理
- 🎮 **复杂交互**: 需要视觉理解的UI操作
- 📋 **信息监控**: 定期提取和分析网页数据


## 📁 项目结构

```
stagehand-python/              # 核心框架
├── stagehand/                 # 主要模块
│   ├── agent/                # 多模态智能代理
│   ├── handlers/             # 操作处理器
│   ├── cache.py              # 缓存机制
│   └── ...
├── examples/                 # 示例代码
│   ├── admin_login_cached.py # 带缓存的登录示例
│   ├── cache_manager_tool.py # 缓存管理工具
│   └── ...
├── media/                    # 媒体资源
├── README.md                 # 项目说明
├── .env.example             # 环境变量示例
└── ...
```

## 📚 文档和指南

- 💾 [缓存机制](CACHE_GUIDE.md) - 缓存功能详细说明

## 🤝 贡献

欢迎提交Issue和Pull Request！

1. Fork 本仓库
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

## 📄 许可证

本项目基于 MIT 许可证开源。

## 🙏 致谢

- [Stagehand](https://github.com/browserbase/stagehand-python) - 提供了强大的基础框架
- [智谱AI](https://open.bigmodel.cn/) - 提供了优秀的GLM模型服务
- [Playwright](https://playwright.dev/) - 提供了可靠的浏览器自动化能力

## 📞 联系方式

- 项目主页: [GitHub Repository](https://github.com/srszzw/stagehand-glm)
- 问题反馈: [Issues](https://github.com/srszzw/stagehand-glm/issues)
- 联系邮箱: srszzw@163.com

---

<div align="center">

**⭐ 如果这个项目对您有帮助，请给我们一个Star！**

Made with ❤️ by [Your Name]

</div>
