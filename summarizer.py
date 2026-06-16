"""聊天记录 LLM 总结器 — 信息特征驱动"""
from datetime import date
from pathlib import Path

import config
import llm


def summarize_session(
    chat_name: str,
    chat_type: str,
    messages_text: str,
    metadata: dict = None,
    time_range: str = "",
    style: str = "work",
) -> str:
    """
    对单个会话生成结构化摘要（信息特征驱动）。

    参数：
        chat_name: 会话名称
        chat_type: "群聊" 或 "单聊"
        messages_text: 格式化后的消息文本
        metadata: 元数据字典，包含：
            - msg_count: 消息总数
            - participant_count: 参与人数
            - active_participants: 发言人数
            - keywords: 高频关键词
        time_range: 时间范围描述
        style: "work" 工作报告风格 / "newspaper" 娱乐报纸风格（仅群聊生效）

    返回：
        LLM 生成的结构化摘要
    """
    if not messages_text.strip():
        return "（该会话无有效消息内容）"

    metadata = metadata or {}
    m = metadata

    # 截断过长的消息（防止超出 token 限制）
    max_chars = 8000
    if len(messages_text) > max_chars:
        messages_text = messages_text[:max_chars] + "\n...（内容已截断）"

    # 根据会话类型 + 风格选择提示词模板
    if chat_type == "群聊" and style == "newspaper":
        prompt = config.GROUP_NEWSPAPER_PROMPT.format(
            chat_name=chat_name,
            time_range=time_range or "最近一段时间",
            msg_count=m.get("msg_count", "?"),
            active_participants=m.get("active_participants", "?"),
            keywords=m.get("keywords", "无"),
            messages=messages_text,
        )
    elif chat_type == "群聊":
        prompt = config.GROUP_SUMMARY_PROMPT.format(
            chat_name=chat_name,
            time_range=time_range or "最近一段时间",
            msg_count=m.get("msg_count", "?"),
            participant_count=m.get("participant_count", "?"),
            active_participants=m.get("active_participants", "?"),
            keywords=m.get("keywords", "无"),
            messages=messages_text,
        )
    else:
        prompt = config.SESSION_SUMMARY_PROMPT.format(
            chat_name=chat_name,
            chat_type=chat_type,
            time_range=time_range or "最近一段时间",
            msg_count=m.get("msg_count", "?"),
            participant_count=m.get("participant_count", "?"),
            keywords=m.get("keywords", "无"),
            messages=messages_text,
        )

    try:
        return llm.complete(prompt)
    except Exception as e:
        raise RuntimeError(f"LLM 调用失败：{e}") from e


def summarize_daily(
    account_purpose: str,
    session_data_list: list[dict],
    target_date: date = None,
) -> str:
    """
    对多个会话生成每日汇总报告。

    参数：
        account_purpose: 账号用途描述
        session_data_list: 每个会话的完整数据（来自 collector.collect_session_data）
        target_date: 目标日期，默认今天

    返回：
        LLM 生成的日报文本
    """
    target_date = target_date or date.today()
    date_str = target_date.strftime("%Y年%m月%d日")

    # 拼接各会话记录
    all_sessions_parts = []
    total_msg_count = 0

    for i, sess in enumerate(session_data_list, 1):
        m = sess.get("metadata", {})
        msg_count = m.get("msg_count", 0)
        total_msg_count += msg_count

        all_sessions_parts.append(
            f"""【会话 {i}：{sess.get('chat_name', '未知')}】（{sess.get('chat_type', '单聊')}，{msg_count} 条消息）
核心内容：{sess.get('messages_text', '')[:2000]}"""
        )

    all_sessions_text = "\n\n".join(all_sessions_parts)

    if not all_sessions_text.strip():
        return f"{date_str} 微信无有效消息记录。"

    # 截断
    max_chars = 8000
    if len(all_sessions_text) > max_chars:
        all_sessions_text = all_sessions_text[:max_chars] + "\n...（内容已截断）"

    prompt = config.DAILY_REPORT_PROMPT.format(
        date=date_str,
        account_purpose=account_purpose or "个人微信",
        session_count=len(session_data_list),
        total_msg_count=total_msg_count,
        all_sessions=all_sessions_text,
    )

    try:
        return llm.complete(prompt)
    except Exception as e:
        raise RuntimeError(f"LLM 汇总失败：{e}") from e


def extract_todos(summary_text: str) -> list[str]:
    """从摘要文本中提取待办事项（简单规则）"""
    todos = []
    lines = summary_text.split("\n")
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # 跳过标题行
        if stripped.startswith("## ") or stripped.startswith("【"):
            continue
        # - [ ] 或 * [ ] 模式
        m = stripped
        if m.startswith("-") or m.startswith("*"):
            # 去掉前缀，保留内容
            content = m.lstrip("-*[] ").strip()
            if content:
                todos.append(content)
        # 数字编号
        if len(todos) < 20:  # 避免误匹配太多
            m2 = stripped.lstrip("0123456789.、）) ").strip()
            if len(m2) > 5 and len(m2) < 200:
                # 简单判断是否是待办类内容
                keywords = ["待", "应该", "需要", "要", "请", "记得", "别忘", "截止"]
                if any(k in m2 for k in keywords):
                    todos.append(m2)
    # 去重
    seen = set()
    deduped = []
    for t in todos:
        if t not in seen and len(t) > 3:
            seen.add(t)
            deduped.append(t)
    return deduped[:20]


def save_report(report_text: str, output_path: str) -> None:
    """保存报告到文件"""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report_text, encoding="utf-8")
    print(f"[+] 报告已保存：{path}")
