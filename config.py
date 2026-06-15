"""配置管理"""
import os
import re
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ===== 路径配置 =====
PROJECT_ROOT = Path(__file__).resolve().parent
STATE_DIR = PROJECT_ROOT / "state"
ACCOUNTS_DIR = STATE_DIR / "accounts"
EXPORTS_DIR = PROJECT_ROOT / "exports"

# ===== LLM 配置 =====
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic")

# Anthropic
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")

# OpenAI（兼容 Groq、LM Studio、Ollama proxy 等）
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "")

# Google Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

# 本地模型 (Ollama / LM Studio)
LOCAL_LLM_BASE_URL = os.getenv("LOCAL_LLM_BASE_URL", "http://localhost:11434/v1")
LOCAL_LLM_MODEL = os.getenv("LOCAL_LLM_MODEL", "qwen2.5")
LOCAL_LLM_API_KEY = os.getenv("LOCAL_LLM_API_KEY", "not-needed")

# 阿里云 DashScope
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
DASHSCOPE_MODEL = os.getenv("DASHSCOPE_MODEL", "qwen-long")

# DeepSeek / Kimi / MiniMax
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

KIMI_API_KEY = os.getenv("KIMI_API_KEY", "")
KIMI_MODEL = os.getenv("KIMI_MODEL", "moonshot-v1-8k")
KIMI_BASE_URL = os.getenv("KIMI_BASE_URL", "https://api.moonshot.cn/v1")

MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY", "")
MINIMAX_MODEL = os.getenv("MINIMAX_MODEL", "abab6.5s-chat")
MINIMAX_BASE_URL = os.getenv("MINIMAX_BASE_URL", "https://api.minimax.chat/v")

# 通用参数
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "4096"))
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.7"))

# ===== 采集配置 =====
DEFAULT_SESSION_LIMIT = 50
DEFAULT_HISTORY_LIMIT = 100
MAX_HISTORY_LIMIT = 500

# ===== 系统账号黑名单 =====
SYSTEM_USERNAMES = {
    "newsapp", "fmessage", "filehelper", "notifymessage",
    "notification_messages", "weibo", "qqmail", "tmessage",
    "qmessage", "qqsync", "floatbottle", "lbsapp", "shakeapp",
    "medianote", "qqfriend", "readerapp", "blogapp", "facebookapp",
    "masssendapp", "meishiapp", "feedsapp", "voip", "blogappweixin",
    "weixin", "brandsessionholder", "weixinreminder", "officialaccounts",
    "wxitil", "userexperience_alarm",
}


# =============================================================================
# 提示词模板 — 信息特征驱动（不按群类型分类）
# =============================================================================

# -----------------------------------------------------------------------------
# 单会话摘要模板（summary 命令用）
# -----------------------------------------------------------------------------
SESSION_SUMMARY_PROMPT = """你是一个专业的聊天记录分析助手。请从以下聊天记录中提取所有有价值的信息，按结构化格式输出。

【会话基本信息】
- 会话名称：{chat_name}
- 会话类型：{chat_type}
- 时间范围：{time_range}
- 消息总数：{msg_count} 条
- 参与人数：{participant_count} 人
- 高频关键词（自动提取）：{keywords}

【消息内容】
{messages}

【输出要求】

## 信息概览
一句话描述本次对话的核心主题和状态（活跃/平静/有分歧/有决策等），不要超过 30 字。

## 行动项（Action Items）
从消息中找出所有"有人承诺做某事"或"有人说要做什么"的内容。
格式：- [人名/角色] + 承诺事项 + 截止时间（如果有）

## 决策结论（Decisions）
从消息中找出所有人明确确认、定下来、同意的内容。
格式：- [决策内容] + 确认人

## 被提及的重要信息（Key Mentions）
提取所有值得单独记录的内容，包括：
- 文件名 / 链接 / 金额 / 地址 / 联系方式 / 数字凭证 等
- 每项注明是谁提供的

## 时间节点（Dates & Deadlines）
提取所有明确的时间点：
- 约定的日期/时间（会议、deadline、约局等）
- 到期/截止类提醒
格式：- [时间] + 事件 + 负责人（如果有）

## 关键人物发言（Key Statements）
最能代表本次讨论深度或方向的 1-3 条发言，注明发言人。
选真正有分量的发言，不要凑数。

## 悬而未决（Open Questions）
有提到但没结论、等待回复、等待确认的事项。
格式：- [事项内容] + 等待对象（如果有）

## 需要关注的情况（Notable）
- 争议/分歧/情绪变化（争吵、不满、感谢、庆祝等）
- 突发情况或意外信息
- 值得特别注意的非寻常内容
如果没有，输出"无"。

请用中文回复。如果某一项为空或无内容，如实说明，不要编造。"""


# -----------------------------------------------------------------------------
# 每日汇总模板（daily 命令用，多会话合并）
# -----------------------------------------------------------------------------
DAILY_REPORT_PROMPT = """你是一个专业的微信聊天记录分析助手。请根据以下多个会话的聊天记录，生成一份完整的每日汇总报告。

【账号信息】
- 账号用途：{account_purpose}
- 汇总日期：{date}
- 会话数量：{session_count} 个
- 总消息数：{total_msg_count} 条

【各会话记录】
{all_sessions}

【输出要求】

## 今日总览
用 2-3 句话概括今天微信的整体状态：有哪些重要进展、哪些需要重点关注。

## 各会话要点
对每个会话，按以下结构输出（无内容的项如实说明）：
- **会话名称**：{会话名}
- **消息数/参与人数**：X 条 / X 人
- **核心内容**：一句话描述这个会话今天在聊什么
- **行动项**：从这个会话中提取的待办/承诺
- **重要信息**：文件/链接/金额等关键内容
- **待确认**：悬而未决的事项

## 全局待办汇总
把所有会话中的行动项汇总，标注来自哪个会话。

## 重要信息汇总
把所有会话中被提及的文件、链接、金额、地址等关键信息集中列出。

## 今日待回复
列出所有等待你回复的人和事。

## 风险提示
如果有争议、分歧、问题、延期等需要关注的情况，在这里指出。

## 明日优先事项
根据今天的聊天内容，推测明天应该优先处理什么。

请用中文回复，简洁有条理，不要重复信息。如果某项无内容，如实说明。"""


# -----------------------------------------------------------------------------
# 群聊专属模板（信息特征驱动，不预设群类型）
# -----------------------------------------------------------------------------
GROUP_SUMMARY_PROMPT = """你是一个专业的聊天记录分析助手。请从以下聊天记录中提取所有有价值的信息，按结构化格式输出。

【群聊基本信息】
- 群名称：{chat_name}
- 时间范围：{time_range}
- 消息总数：{msg_count} 条
- 群成员总数：约 {participant_count} 人
- 本次发言人数：{active_participants} 人
- 高频关键词：{keywords}

【消息内容】
{messages}

【输出要求】

## 群聊概览
2-3 句话描述：这个群今天在聊什么、整体氛围如何、有没有值得特别记录的事。

## 行动项（Action Items）
从群聊中找出所有"有人承诺做某事"的内容。
格式：[发言人] + 承诺事项 + 截止时间（无则不写）
如果没有，输出"无"。

## 决策与共识（Decisions）
从群聊中找出所有人明确达成一致、确认下来的内容。
如果没有，输出"无"。

## 重要提及（Key Mentions）
提取群内分享的所有有价值的内容：
- 文件/链接/资料
- 金额/价格/报价
- 地址/位置/时间
- 联系方式
- 编号/凭证
标注来源发言人。

## 时间节点（Dates & Deadlines）
提取所有明确的时间安排：
- 会议/活动/约定
- 截止/到期提醒
- 任何日期类信息

## 关键发言（Key Statements）
最能代表本次群聊深度或方向的 1-5 条发言，注明发言人。
选真正有分量的话，不要凑数。如果群里以闲聊为主，选最有意思或最有代表性的 2-3 条。

## 悬而未决（Open Questions）
群里有人提出但没结论、等待回复、等待确认的事项。
如果没有，输出"无"。

## 值得注意的情况（Notable）
- @ 提醒 / 互相点名
- 争议/分歧/争吵
- 情绪变化（感谢、庆祝、不满等）
- 成员变化（新加入/退出，如果有）
- 其他非寻常或值得记录的事
如果没有，输出"无"。

请用中文回复。如果某一项为空，如实说明，不要编造。"""
