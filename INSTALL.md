# GPT Reverse Proxy 完整安装教程

## 系统要求

- Python 3.11+
- pip 或 conda

---

## 方法一：pip 安装（推荐）

### 1. 克隆仓库

```bash
git clone https://github.com/art3m1s-tju/GPT_reverse.git
cd GPT_reverse
```

### 2. 创建虚拟环境（可选但推荐）

```bash
# 使用 venv
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 或使用 conda
conda create -n gpt-proxy python=3.11
conda activate gpt-proxy
```

### 3. 安装依赖

```bash
pip install -e .
```

### 4. 启动服务

```bash
gpt-proxy serve
```

服务将在 http://localhost:8000 启动

---

## 方法二：Docker 安装

### 1. 构建镜像

```bash
git clone https://github.com/art3m1s-tju/GPT_reverse.git
cd GPT_reverse
docker build -t gpt-proxy -f docker/Dockerfile .
```

### 2. 运行容器

```bash
docker run -p 8000:8000 gpt-proxy
```

---

## 方法三：直接运行（无需安装）

```bash
git clone https://github.com/art3m1s-tju/GPT_reverse.git
cd GPT_reverse
pip install fastapi uvicorn httpx pydantic pydantic-settings typer rich
python -m gpt_proxy serve
```

---

## 获取 ChatGPT Session Token

### 方法一：浏览器开发者工具

1. 打开 https://chat.openai.com 并登录
2. 按 `F12` 打开开发者工具
3. 点击 **Application** 标签
4. 左侧菜单：**Cookies** → **chat.openai.com**
5. 找到 `__Secure-next-auth.session-token`
6. 复制它的值

### 方法二：浏览器控制台

在 chat.openai.com 页面打开控制台（F12 → Console），粘贴：

```javascript
document.cookie.split('; ').find(c => c.startsWith('__Secure-next-auth.session-token='))?.split('=')[1]
```

复制输出的字符串。

---

## 使用步骤

### 1. 启动服务

```bash
gpt-proxy serve
```

看到以下输出表示成功：
```
Starting ChatGPT Reverse Proxy...
Server: http://0.0.0.0:8000
Docs: http://0.0.0.0:8000/docs
```

### 2. 登录

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"session_token": "你的session_token"}'
```

成功返回：
```json
{
  "session_id": "abc123...",
  "user_email": "your@email.com",
  "expires_at": "2024-...",
  "message": "Login successful. Use session_id as Bearer token in API requests."
}
```

### 3. 调用 API

保存上一步返回的 `session_id`，用于后续请求：

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer 你的session_id" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4",
    "messages": [{"role": "user", "content": "你好"}]
  }'
```

---

## Python 客户端示例

```python
import httpx

# 1. 登录
login_resp = httpx.post(
    "http://localhost:8000/auth/login",
    json={"session_token": "你的session_token"}
)
session_id = login_resp.json()["session_id"]
print(f"登录成功，session_id: {session_id}")

# 2. 聊天
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

---

## 流式输出示例

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

## 可用模型

- `gpt-4` - 需要 ChatGPT Plus 订阅
- `gpt-4o` - 需要 ChatGPT Plus 订阅
- `gpt-3.5-turbo` - 免费账户可用

---

## 常见问题

### Q: 登录失败怎么办？
A: Session token 会过期，重新从浏览器获取新的 token。

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