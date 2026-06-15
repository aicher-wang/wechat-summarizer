"""会话类型分类器 — LLM 辅助判断工作/非工作"""
from typing import Literal

import config
import llm


ReportStyle = Literal["work", "newspaper"]


def classify_session(
    chat_name: str,
    messages_preview: str,
    keywords: str,
    metadata: dict = None,
) -> dict:
    """
    使用 LLM 辅助判断会话的类型风格。

    传入摘要前的原始信息（不调 summarizer），直接根据会话名、
    消息预览和关键词做轻量判断。

    返回：
        {
            "style": "work" 或 "newspaper",
            "confidence": 0.0 ~ 1.0,
            "reasoning": str,  # 判断理由（1句话）
        }
    """
    metadata = metadata or {}
    msg_count = metadata.get("msg_count", 0)

    # 消息预览截断
    preview = (messages_preview or "")[:500].strip()
    if not preview:
        preview = "（无可用消息内容）"

    prompt = f"""你是一个聊天记录类型判断助手。请根据以下信息，判断这个微信会话更接近"工作相关"还是"非工作相关"。

【会话名称】：{chat_name}
【消息预览（前500字）】：
{preview}

【高频关键词】：{keywords}
【消息数量】：{msg_count} 条

【判断标准】：
- 工作相关：讨论项目、业务、客户、会议、任务、决策、报销、进度、工作安排、合同、报价等
- 非工作相关：家人日常、朋友闲聊、兴趣话题、聚会安排、美食、旅行、八卦、同学群、兴趣群等
- 边界情况：优先看消息内容本身，而非仅凭群名判断

【输出格式】：
先给出你的判断理由（1-2句话），然后明确输出分类结果：
WORK：如果高度确信是工作相关（置信度 ≥ 0.7）
NEWSPAPER：如果高度确信是非工作相关（置信度 ≥ 0.7）
UNCERTAIN：如果两者都有可能，置信度 < 0.7

请直接输出判断理由和结果，不要有多余的格式。"""

    try:
        result_text = llm.complete(prompt, max_tokens=200)
    except Exception as e:
        # 判断失败时默认工作报告（保守）
        return {
            "style": "work",
            "confidence": 0.0,
            "reasoning": f"LLM 判断失败：{e}，默认工作报告格式"
        }

    result_text = result_text.strip()

    # 解析结果
    if "WORK" in result_text.upper() and "NEWSPAPER" not in result_text.upper():
        style: ReportStyle = "work"
        confidence = 0.8
    elif "NEWSPAPER" in result_text.upper():
        style = "newspaper"
        confidence = 0.8
    else:
        # 解析置信度
        conf_match = [s for s in result_text.split() if any(c.isdigit() for c in s)]
        confidence = 0.5
        style = "newspaper"  # 模糊时默认娱乐

    # 提取推理
    lines = result_text.split("\n")
    reasoning = lines[0].strip() if lines else "无法提取判断理由"

    return {
        "style": style,
        "confidence": confidence,
        "reasoning": reasoning[:100],
        "raw_response": result_text,
    }


def classify_for_daily(
    account_purpose: str,
    session_data_list: list[dict],
    keywords_per_session: dict = None,
) -> dict:
    """
    对 daily 报告场景做全局判断。

    综合账号用途 + 各会话信息，判断整份报告应该用什么风格。
    返回全局风格 + 各会话子风格。
    """
    keywords_per_session = keywords_per_session or {}

    # 如果账号用途明确，按账号用途判断
    work_keywords = {"工作", "业务", "客户", "项目", "商务", "销售", "运营", "技术", "财务", "法务"}
    non_work_keywords = {"家人", "家庭", "私人", "朋友", "生活", "兴趣", "同学", "老乡"}

    purpose = account_purpose or ""

    # 规则预判
    if any(k in purpose for k in work_keywords):
        preferred_style: ReportStyle = "work"
        rule_based = True
    elif any(k in purpose for k in non_work_keywords):
        preferred_style = "newspaper"
        rule_based = True
    else:
        preferred_style = "newspaper"
        rule_based = False

    # 统计会话风格分布
    session_styles = []
    work_count = 0
    non_work_count = 0

    for sess in session_data_list:
        chat_name = sess.get("chat_name", "")
        messages_text = (sess.get("messages_text", "") or "")[:300]
        keywords = keywords_per_session.get(chat_name, sess.get("metadata", {}).get("keywords", ""))

        result = classify_session(chat_name, messages_text, keywords, sess.get("metadata"))
        session_styles.append({
            "chat_name": chat_name,
            "style": result["style"],
            "confidence": result["confidence"],
            "reasoning": result["reasoning"],
        })

        if result["style"] == "work":
            work_count += 1
        else:
            non_work_count += 1

    # 全局风格：多数表决
    if rule_based:
        global_style = preferred_style
    elif work_count > non_work_count * 1.5:
        global_style = "work"
    elif non_work_count > work_count * 1.5:
        global_style = "newspaper"
    else:
        # 接近时以账号用途为准
        global_style = preferred_style

    return {
        "global_style": global_style,
        "work_sessions": work_count,
        "non_work_sessions": non_work_count,
        "session_styles": session_styles,
    }
