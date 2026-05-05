# GPT Reverse Proxy 完整安装教程

## 系统要求

- Python 3.11+
- pip 或 conda

---

## 快速开始（推荐）

### 1. 克隆并安装

```bash
git clone https://github.com/art3m1s-tju/GPT_reverse.git
cd GPT_reverse
pip install -e .
```

### 2. 安装浏览器自动化（可选，用于自动登录）

```bash
pip install playwright
playwright install chromium
```

### 3. 启动服务

```bash
gpt-proxy serve
```

### 4. 登录

**方式一：浏览器自动登录（推荐）**
```bash
gpt-proxy login
```
会自动打开浏览器，登录ChatGPT后自动获取token。

**方式二：手动输入token**
```bash
curl -X POST http://localhost:8000/auth/login -H "Content-Type: application/json" -d '{"session_token": "你的token"}'
```

---

## 详细安装方法

### 方法一：pip 安装（推荐）

#### 1. 克隆仓库

```bash
git clone https://github.com/art3m1s-tju/GPT_reverse.git
cd GPT_reverse
```

#### 2. 创建虚拟环境（可选但推荐）

```bash
# 使用 venv
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 或使用 conda
conda create -n gpt-proxy python=3.11
conda activate gpt-proxy
```

#### 3. 安装依赖

```bash
pip install -e .
```

#### 4. 安装浏览器自动化（可选）

```bash
pip install playwright
playwright install chromium
```

#### 5. 启动服务

```bash
gpt-proxy serve
```

服务将在 http://localhost:8000 启动

---

### 方法二：Docker 安装

```bash
git clone https://github.com/art3m1s-tju/GPT_reverse.git
cd GPT_reverse
docker build -t gpt-proxy -f docker/Dockerfile .
docker run -p 8000:8000 gpt-proxy
```

---

### 方法三：直接运行（无需安装）

```bash
git clone https://github.com/art3m1s-tju/GPT_reverse.git
cd GPT_reverse
pip install fastapi uvicorn httpx pydantic pydantic-settings typer rich playwright
playwright install chromium
python -m gpt_proxy serve
```

---

## 登录方式

### 方式一：浏览器自动登录（推荐）

**前提：已安装 playwright 和 chromium**

```bash
# 启动服务
gpt-proxy serve

# 新开终端，运行登录命令
gpt-proxy login
```

系统会自动打开浏览器窗口：
1. 在浏览器中登录你的ChatGPT账号
2. 登录成功后自动提取token
3. 返回session_id用于后续API调用

**优点：**
- 无需手动复制cookie
- 浏览器profile持久化，下次登录更快
- 可视化操作，体验更好

---

### 方式二：手动获取 Session Token

如果不想安装playwright，可以手动获取token。

#### 步骤1：获取 Token

**方法A：浏览器开发者工具**

1. 打开 https://chat.openai.com 并登录
2. 按 `F12` 打开开发者工具
3. 点击 **Application** 标签
4. 左侧菜单：**Cookies** → **chat.openai.com**
5. 找到 `__Secure-next-auth.session-token`
6. 复制它的值

**方法B：浏览器控制台**

在 chat.openai.com 页面打开控制台（F12 → Console），粘贴：

```javascript
document.cookie.split('; ').find(c => c.startsWith('__Secure-next-auth.session-token='))?.split('=')[1]
```

复制输出的字符串。

#### 步骤2：登录

```bash
curl -X POST http://localhost:8000/auth/login -H "Content-Type: application/json" -d '{"session_token": "你的token"}'
```

---

## 使用 API

### 调用聊天接口

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer 你的session_id" \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-4", "messages": [{"role": "user", "content": "你好"}]}'
```

### Python 客户端

```python
import httpx

# 方式一：使用浏览器登录后的session_id
session_id = "你的session_id"

# 方式二：通过API登录
# login_resp = httpx.post(
#     "http://localhost:8000/auth/login",
#     json={"session_token": "你的token"}
# )
# session_id = login_resp.json()["session_id"]

# 聊天
client = httpx.Client(
    base_url="http://localhost:8000",
    headers={"Authorization": f"Bearer {session_id}"}
)

response = client.post(
    "/v1/chat/completions",
    json={
        "model": "gpt-4",
        "messages": [{"role": "user", "content": "你好"}]
    }
)
print(response.json())
```

### 流式输出

```python
import httpx

session_id = "你的session_id"

with httpx.stream(
    "POST",
    "http://localhost:8000/v1/chat/completions",
    headers={"Authorization": f"Bearer {session_id}"},
    json={
        "model": "gpt-4",
        "messages": [{"role": "user", "content": "讲个故事"}],
        "stream": True
    }
) as response:
    for line in response.iter_lines():
        if line:
            print(line)
```

---

## CLI 命令

| 命令 | 说明 |
|------|------|
| `gpt-proxy serve` | 启动服务器 |
| `gpt-proxy login` | 浏览器自动登录 |
| `gpt-proxy help-token` | 显示如何获取token |
| `gpt-proxy version` | 显示版本 |

---

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/auth/login/browser` | POST | 浏览器自动登录 |
| `/auth/login` | POST | 手动token登录 |
| `/auth/login/status` | GET | 检查登录状态 |
| `/auth/sessions` | GET | 列出所有会话 |
| `/auth/logout` | POST | 登出 |
| `/v1/chat/completions` | POST | 聊天补全 |
| `/v1/models` | GET | 列出模型 |

---

## 可用模型

- `gpt-4` - 需要 ChatGPT Plus 订阅
- `gpt-4o` - 需要 ChatGPT Plus 订阅
- `gpt-3.5-turbo` - 免费账户可用

---

## 常见问题

### Q: playwright install chromium 下载失败？
A: 网络问题，可以：
1. 使用代理
2. 或使用手动获取token的方式

### Q: 登录失败怎么办？
A: Session token 会过期，重新登录获取新的 token。

### Q: 401 错误？
A: Session 过期，重新登录获取新的 session_id。

### Q: 没有响应？
A: 检查网络连接，确保能访问 chat.openai.com。

### Q: Windows 下命令不生效？
A: 确保使用正确的路径分隔符，或使用 PowerShell。

---

## API 文档

启动服务后访问：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc