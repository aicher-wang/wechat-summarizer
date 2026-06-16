"""聊天记录采集器 — 含元数据提取"""
import json
import shlex
import subprocess
import platform
import re
from collections import Counter
from datetime import date, datetime, time
from pathlib import Path
from typing import Any, Optional

import config
import accounts


# =============================================================================
# 工具函数
# =============================================================================

def is_system_username(username: str, include_system: bool = False) -> bool:
    """判断是否为系统账号"""
    if not username:
        return True
    if username in config.SYSTEM_USERNAMES and not include_system:
        return True
    return False


def split_command_prefix(command_prefix: str) -> list[str]:
    # Use posix=True to properly strip quotes from paths on all platforms
    return shlex.split(command_prefix, posix=True)


def run_wechat_cli(command_prefix: str, args: list[str], timeout: int = 120) -> dict[str, Any]:
    """调用 wechat-cli 命令，返回结构化结果"""
    cmd = split_command_prefix(command_prefix) + args
    env = accounts.isolated_subprocess_env()

    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
            env=env,
        )
    except FileNotFoundError:
        return {"ok": False, "error": f"命令不存在：{' '.join(cmd[:3])}"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"命令超时（{timeout}秒）"}

    if proc.returncode != 0:
        return {"ok": False, "error": proc.stderr.decode("utf-8", errors="replace").strip()}

    try:
        data = json.loads(proc.stdout.decode("utf-8", errors="replace").strip() or "[]")
    except json.JSONDecodeError:
        data = proc.stdout.decode("utf-8", errors="replace").strip()

    return {"ok": True, "data": data, "stdout": proc.stdout, "stderr": proc.stderr}


# =============================================================================
# 消息元数据提取
# =============================================================================

def extract_keywords(text: str, top_n: int = 10) -> str:
    """
    从文本中提取高频词汇作为关键词。
    过滤掉停用词（单字、常见语气词等），返回 top_n 个高频词。
    """
    # 简单分词：按空格和标点分割
    words = re.findall(r"[\u4e00-\u9fff]{2,}|[\w]{3,}", text)
    # 停用词
    stopwords = {
        "的", "了", "是", "在", "我", "有", "和", "就", "不", "人", "都", "一",
        "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着",
        "没有", "看", "好", "自己", "这", "什么", "那", "他", "她", "它",
        "我们", "你们", "他们", "这个", "那个", "怎么", "为什么", "可以",
        "但是", "因为", "所以", "如果", "虽然", "还是", "或者", "而且",
        "已经", "现在", "时候", "这样", "那样", "一直", "一下", "一点",
        "什么", "怎么", "为什么", "哪个", "哪些", "多少", "这里", "那里",
    }
    filtered = [w for w in words if w.lower() not in stopwords and len(w) >= 2]
    counter = Counter(filtered)
    return "、".join([w for w, _ in counter.most_common(top_n)])


def extract_metadata(messages: list) -> dict[str, Any]:
    """
    从消息列表中提取元数据，用于填充 prompt 上下文。
    不调 LLM，纯规则计算。
    支持结构化 dict 消息或预格式化字符串。
    """
    if not messages:
        return {
            "msg_count": 0,
            "participant_count": 0,
            "active_participants": 0,
            "keywords": "无",
        }

    msg_count = len(messages)

    # 提取发言人
    senders = set()
    all_text_parts = []
    for msg in messages:
        if isinstance(msg, str):
            # 预格式化字符串: "[时间] sender：content"
            all_text_parts.append(msg)
            # 简单解析出发送人
            m = re.match(r"\[([^\]]+)\]\s*([^：\s]+)：", msg)
            if m:
                senders.add(m.group(2).strip())
        else:
            sender = str(msg.get("sender") or msg.get("from") or msg.get("nickname") or "").strip()
            if sender and sender not in ("未知", "", "系统"):
                senders.add(sender)
            content = str(msg.get("content") or msg.get("text") or msg.get("message") or "")
            if content:
                all_text_parts.append(content)

    participant_count = len(senders)
    active_participants = participant_count  # 有发言的 = 参与人数

    all_text = " ".join(all_text_parts)
    keywords = extract_keywords(all_text, top_n=10)

    return {
        "msg_count": msg_count,
        "participant_count": participant_count,
        "active_participants": active_participants,
        "keywords": keywords or "无",
    }


# =============================================================================
# 核心采集
# =============================================================================

def get_sessions(account_id: str, limit: int = None) -> list[dict]:
    """获取会话列表"""
    account = accounts.get_account(account_id)
    if not account:
        raise ValueError(f"账号不存在：{account_id}")

    limit = limit or config.DEFAULT_SESSION_LIMIT
    result = run_wechat_cli(
        account["command_prefix"],
        ["sessions", "--limit", str(limit), "--format", "json"],
    )

    if not result["ok"]:
        raise RuntimeError(f"获取会话列表失败：{result['error']}")

    sessions = result["data"]
    if not isinstance(sessions, list):
        raise RuntimeError(f"sessions 返回格式异常：{type(sessions)}")

    # 过滤系统账号
    filtered = []
    for s in sessions:
        username = str(s.get("username") or s.get("userName") or s.get("wxid") or "")
        if is_system_username(username):
            continue
        filtered.append(s)
    return filtered


def get_history(
    account_id: str,
    username: str,
    limit: int = None,
    start_time: str = "",
    end_time: str = "",
) -> list[dict]:
    """获取指定会话的历史消息"""
    account = accounts.get_account(account_id)
    if not account:
        raise ValueError(f"账号不存在：{account_id}")

    limit = min(limit or config.DEFAULT_HISTORY_LIMIT, config.MAX_HISTORY_LIMIT)

    args = ["history", username, "--limit", str(limit), "--format", "json"]
    if start_time:
        args.extend(["--start-time", start_time])
    if end_time:
        args.extend(["--end-time", end_time])

    result = run_wechat_cli(account["command_prefix"], args)

    if not result["ok"]:
        raise RuntimeError(f"获取历史消息失败：{result['error']}")

    data = result["data"]
    if isinstance(data, dict):
        return data.get("messages", [])
    if isinstance(data, list):
        return data
    return []


def get_history_by_date(
    account_id: str,
    username: str,
    target_date: date = None,
) -> list[dict]:
    """获取指定日期的消息（默认今天）"""
    target_date = target_date or date.today()
    start_dt = datetime.combine(target_date, time.min)
    end_dt = datetime.now().replace(microsecond=0) if target_date == date.today() \
        else datetime.combine(target_date, time.max).replace(microsecond=0)

    return get_history(
        account_id,
        username,
        limit=config.MAX_HISTORY_LIMIT,
        start_time=start_dt.strftime("%Y-%m-%d %H:%M:%S"),
        end_time=end_dt.strftime("%Y-%m-%d %H:%M:%S"),
    )


def get_multi_account_sessions(account_ids: list[str] = None) -> dict[str, list[dict]]:
    """获取多个账号的会话列表，按账号分组"""
    if account_ids is None:
        account_ids = [a["account_id"] for a in accounts.list_accounts()]

    result = {}
    for aid in account_ids:
        try:
            result[aid] = get_sessions(aid)
        except Exception as e:
            result[aid] = []
    return result


def format_message_for_summary(msg: dict | str) -> str:
    """将单条消息格式化为可读文本（支持结构化 dict 或预格式化字符串）"""
    # Handle pre-formatted string from wechat-cli
    if isinstance(msg, str):
        return msg.strip()
    sender = str(msg.get("sender") or msg.get("from") or msg.get("nickname") or "未知").strip()
    content = str(msg.get("content") or msg.get("text") or msg.get("message") or "").strip()
    msg_time = str(msg.get("time") or msg.get("datetime") or "").strip()

    if not content:
        return ""
    if sender in ("未知", ""):
        return content

    # 简化时间格式
    if msg_time:
        try:
            dt = datetime.fromisoformat(msg_time.replace(" ", "T"))
            msg_time = dt.strftime("%H:%M")
        except (ValueError, TypeError):
            pass

    return f"[{msg_time}] {sender}：{content}"


def collect_session_data(
    account_id: str,
    username: str,
    date_filter: date = None,
    include_metadata: bool = True,
) -> dict[str, Any]:
    """
    采集指定会话的完整数据，用于 LLM 总结。
    返回包含元数据和格式化消息的字典。

    返回值结构：
        {
            "chat_name": str,
            "chat_type": str,         # "群聊" 或 "单聊"
            "username": str,
            "messages_text": str,      # 格式化的消息文本
            "metadata": dict,          # 元数据（msg_count, participant_count 等）
        }
    """
    account = accounts.get_account(account_id)
    if not account:
        raise ValueError(f"账号不存在：{account_id}")

    is_group = "chatroom" in username.lower()

    # 获取会话名称
    chat_name = username
    try:
        sessions = get_sessions(account_id, limit=200)
        for s in sessions:
            uname = str(s.get("username") or s.get("userName") or "")
            if uname == username:
                chat_name = str(s.get("chat") or s.get("name") or s.get("display_name") or username)
                break
    except Exception:
        pass

    # 获取消息
    if date_filter:
        messages = get_history_by_date(account_id, username, date_filter)
    else:
        messages = get_history(account_id, username)

    # 格式化消息文本
    lines = []
    for msg in messages:
        line = format_message_for_summary(msg)
        if line:
            lines.append(line)
    messages_text = "\n".join(lines)

    # 提取元数据
    metadata = extract_metadata(messages) if include_metadata else {
        "msg_count": len(messages),
        "participant_count": 0,
        "active_participants": 0,
        "keywords": "无",
    }

    return {
        "chat_name": chat_name,
        "chat_type": "群聊" if is_group else "单聊",
        "username": username,
        "messages_text": messages_text,
        "raw_messages": messages,     # 原始消息列表，用于统计计算
        "metadata": metadata,
    }
