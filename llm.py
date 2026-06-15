"""统一 LLM 调用接口 — 支持多种大模型 API"""
import os
import json
import http.client
from abc import ABC, abstractmethod
from typing import Literal
from dotenv import load_dotenv

import config

load_dotenv()


# ===== Provider 抽象基类 =====

class LLMProvider(ABC):
    """LLM Provider 接口"""

    @abstractmethod
    def complete(self, prompt: str, **kwargs) -> str:
        """给定提示词，返回 LLM 生成的文本"""
        raise NotImplementedError

    @abstractmethod
    def name(self) -> str:
        return "unknown"


# ===== Anthropic (Claude) =====

class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str = None, model: str = None):
        import anthropic
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
        self.model = model or os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
        self.max_tokens = int(os.getenv("MAX_TOKENS", "4096"))
        self.client = anthropic.Anthropic(api_key=self.api_key)

    def name(self) -> str:
        return f"anthropic/{self.model}"

    def complete(self, prompt: str, **kwargs) -> str:
        max_tokens = kwargs.get("max_tokens", self.max_tokens)
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()


# ===== OpenAI (GPT-4o / o1 等) =====

class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o")
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com")

    def name(self) -> str:
        return f"openai/{self.model}"

    def complete(self, prompt: str, **kwargs) -> str:
        max_tokens = kwargs.get("max_tokens", 4096)
        temperature = kwargs.get("temperature", 0.7)

        # 支持 OpenAI 兼容接口（如 Groq, LM Studio, Ollama proxy 等）
        if "/v1" not in self.base_url:
            url = f"{self.base_url.rstrip('/')}/v1/chat/completions"
        else:
            url = f"{self.base_url.rstrip('/')}/chat/completions"

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        import urllib.request
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"].strip()


# ===== Google Gemini =====

class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        self.base_url = "https://generativelanguage.googleapis.com"

    def name(self) -> str:
        return f"gemini/{self.model}"

    def complete(self, prompt: str, **kwargs) -> str:
        url = (
            f"{self.base_url}/v1beta/models/{self.model}:generateContent"
            f"?key={self.api_key}"
        )
        payload = {"contents": [{"parts": [{"text": prompt}]}]}

        import urllib.request
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()


# ===== 本地模型（Ollama / LM Studio 等兼容 OpenAI 接口）=====

class LocalProvider(LLMProvider):
    """接入任何兼容 OpenAI ChatML 接口的本地/自托管模型"""

    def __init__(self, base_url: str = None, model: str = None, api_key: str = None):
        self.base_url = base_url or os.getenv("LOCAL_LLM_BASE_URL", "http://localhost:11434/v1")
        self.model = model or os.getenv("LOCAL_LLM_MODEL", "qwen2.5")
        self.api_key = api_key or os.getenv("LOCAL_LLM_API_KEY", "not-needed")

    def name(self) -> str:
        return f"local/{self.model}"

    def complete(self, prompt: str, **kwargs) -> str:
        max_tokens = kwargs.get("max_tokens", 4096)
        temperature = kwargs.get("temperature", 0.7)

        url = f"{self.base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        import urllib.request
        headers = {"Content-Type": "application/json"}
        if self.api_key and self.api_key != "not-needed":
            headers["Authorization"] = f"Bearer {self.api_key}"

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=300) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"].strip()


# ===== 通用的 qwen-long 等阿里云模型 =====

class DashScopeProvider(LLMProvider):
    """阿里云通义千问 / DashScope API"""

    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY") or os.getenv("DASHSCOPE_API_KEY")
        self.model = model or os.getenv("DASHSCOPE_MODEL", "qwen-long")
        self.base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    def name(self) -> str:
        return f"dashscope/{self.model}"

    def complete(self, prompt: str, **kwargs) -> str:
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
        }

        import urllib.request
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"].strip()


# ===== DeepSeek =====

class DeepSeekProvider(LLMProvider):
    """DeepSeek API（OpenAI 兼容）"""

    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY", "")
        self.model = model or os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        self.base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

    def name(self) -> str:
        return f"deepseek/{self.model}"

    def complete(self, prompt: str, **kwargs) -> str:
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
        }

        import urllib.request
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"].strip()


# ===== Kimi / Moonshot AI =====

class KimiProvider(LLMProvider):
    """Kimi (Moonshot AI) API（OpenAI 兼容）"""

    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or os.getenv("KIMI_API_KEY", "")
        self.model = model or os.getenv("KIMI_MODEL", "moonshot-v1-8k")
        self.base_url = os.getenv("KIMI_BASE_URL", "https://api.moonshot.cn/v1")

    def name(self) -> str:
        return f"kimi/{self.model}"

    def complete(self, prompt: str, **kwargs) -> str:
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
        }

        import urllib.request
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"].strip()


# ===== MiniMax =====

class MiniMaxProvider(LLMProvider):
    """MiniMax API（OpenAI 兼容）"""

    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or os.getenv("MINIMAX_API_KEY", "")
        self.model = model or os.getenv("MINIMAX_MODEL", "abab6.5s-chat")
        self.base_url = os.getenv("MINIMAX_BASE_URL", "https://api.minimax.chat/v")

    def name(self) -> str:
        return f"minimax/{self.model}"

    def complete(self, prompt: str, **kwargs) -> str:
        # MiniMax 路径格式略有不同
        url = f"{self.base_url.rstrip('/')}/text/chatcompletion_v2"

        import urllib.request
        req = urllib.request.Request(
            url,
            data=json.dumps({
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
            }).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"].strip()


# ===== Provider 工厂 =====

_PROVIDER_REGISTRY: dict[str, type[LLMProvider]] = {
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
    "gemini": GeminiProvider,
    "local": LocalProvider,
    "dashscope": DashScopeProvider,
    "deepseek": DeepSeekProvider,
    "kimi": KimiProvider,
    "minimax": MiniMaxProvider,
}


def create_provider(name: str = None) -> LLMProvider:
    """
    根据配置名称创建 LLM Provider。

    读取环境变量 LLM_PROVIDER 确定使用哪个 Provider。
    支持：anthropic / openai / gemini / local / dashscope / deepseek / kimi / minimax

    示例：
        os.environ["LLM_PROVIDER"] = "deepseek"
        os.environ["DEEPSEEK_API_KEY"] = "sk-..."
        provider = create_provider()
    """
    name = name or os.getenv("LLM_PROVIDER", "anthropic")
    if name not in _PROVIDER_REGISTRY:
        raise ValueError(
            f"未知的 LLM Provider：{name}，支持的：{list(_PROVIDER_REGISTRY.keys())}"
        )
    return _PROVIDER_REGISTRY[name]()


# ===== 统一调用入口 =====

def complete(prompt: str, provider_name: str = None, **kwargs) -> str:
    """
    统一调用入口，根据配置自动选择 Provider。

    环境变量：
        LLM_PROVIDER   — 提供商名称（默认 anthropic）
        *_<MODEL/KEY/BASE_URL> — 各 Provider 的配置
    """
    provider = create_provider(provider_name)
    return provider.complete(prompt, **kwargs)
