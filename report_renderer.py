"""报告渲染器 — 工作报告风格 & 娱乐报纸风格"""
import re
from datetime import date
from typing import Any

import config
import classifier
import stats


# =============================================================================
# 工作报告渲染器（Work Report Style）
# =============================================================================

def render_work_report(
    account_purpose: str,
    session_summaries: list[dict],
    target_date: date,
    classification: dict = None,
) -> str:
    """
    渲染工作报告风格。
    适用于：项目群、客户群、工作会议、业务沟通等。
    """
    date_str = target_date.strftime("%Y年%m月%d日")

    lines = []

    # ===== 报告头部 =====
    lines.append("=" * 56)
    lines.append(f"  微信工作群报告")
    lines.append("=" * 56)
    lines.append(f"  日期：{date_str}")
    if account_purpose:
        lines.append(f"  账号用途：{account_purpose}")
    lines.append(f"  汇总会话数：{len(session_summaries)} 个")
    if classification:
        lines.append(f"  工作会话：{classification.get('work_sessions', 0)} 个")
        lines.append(f"  非工作会话：{classification.get('non_work_sessions', 0)} 个")
    lines.append("=" * 56)
    lines.append("")

    # ===== 遍历每个会话 =====
    for i, sess in enumerate(session_summaries, 1):
        chat_name = sess.get("chat_name", "未知会话")
        summary_text = sess.get("summary", "")
        is_group = "群聊" if sess.get("chat_type") == "群聊" else "单聊"

        lines.append("")
        lines.append(f"{'─' * 56}")
        lines.append(f"  【{i}】{chat_name}（{is_group}）")
        lines.append(f"{'─' * 56}")

        if not summary_text.strip():
            lines.append("  （无有效内容）")
            lines.append("")
            continue

        # 解析摘要结构，渲染为工作格式
        parsed = _parse_summary_to_dict(summary_text)

        # 信息概览
        if parsed.get("overview"):
            lines.append("")
            lines.append(f"  📋 概况")
            lines.append(f"  {parsed['overview']}")

        # 行动项
        action_items = parsed.get("action_items", [])
        if action_items:
            lines.append("")
            lines.append(f"  ✅ 行动项（共 {len(action_items)} 项）")
            for item in action_items[:10]:  # 最多 10 条
                lines.append(f"  • {item}")

        # 决策结论
        decisions = parsed.get("decisions", [])
        if decisions:
            lines.append("")
            lines.append(f"  ✔️ 决策结论（共 {len(decisions)} 项）")
            for d in decisions[:5]:
                lines.append(f"  • {d}")

        # 重要信息
        key_mentions = parsed.get("key_mentions", [])
        if key_mentions:
            lines.append("")
            lines.append(f"  📎 重要信息（共 {len(key_mentions)} 项）")
            for m in key_mentions[:5]:
                lines.append(f"  • {m}")

        # 时间节点
        deadlines = parsed.get("deadlines", [])
        if deadlines:
            lines.append("")
            lines.append(f"  ⏰ 时间节点（共 {len(deadlines)} 项）")
            for d in deadlines[:5]:
                lines.append(f"  • {d}")

        # 待确认
        open_questions = parsed.get("open_questions", [])
        if open_questions:
            lines.append("")
            lines.append(f"  ❓ 待确认事项（共 {len(open_questions)} 项）")
            for q in open_questions[:5]:
                lines.append(f"  • {q}")

        # 风险/Notable
        notable = parsed.get("notable", [])
        if notable:
            lines.append("")
            lines.append(f"  ⚠️ 需要关注的情况")
            for n in notable[:5]:
                lines.append(f"  • {n}")

        lines.append("")

    # ===== 汇总区块 =====
    lines.append("")
    lines.append("=" * 56)
    lines.append("  📌 全局汇总")
    lines.append("=" * 56)

    # 收集所有行动项
    all_actions = []
    all_questions = []
    all_files = []
    for sess in session_summaries:
        parsed = _parse_summary_to_dict(sess.get("summary", ""))
        all_actions.extend(parsed.get("action_items", []))
        all_questions.extend(parsed.get("open_questions", []))
        all_files.extend(parsed.get("key_mentions", []))

    if all_actions:
        lines.append("")
        lines.append(f"  📝 全局待办（共 {len(all_actions)} 项）")
        for a in all_actions[:15]:
            lines.append(f"  • {a}")

    if all_questions:
        lines.append("")
        lines.append(f"  ⏳ 待确认（共 {len(all_questions)} 项）")
        for q in all_questions[:10]:
            lines.append(f"  • {q}")

    if all_files:
        lines.append("")
        lines.append(f"  📎 重要文件/链接汇总")
        for f in all_files[:10]:
            lines.append(f"  • {f}")

    # ===== 页脚 =====
    lines.append("")
    lines.append("=" * 56)
    lines.append(f"  报告生成时间：{date.strftime('%Y-%m-%d %H:%M')}")
    lines.append("  本报告由微信聊天记录总结器自动生成")
    lines.append("=" * 56)

    return "\n".join(lines)


# =============================================================================
# 娱乐报纸渲染器（Newspaper Style）
# =============================================================================

def _extract_quote(summary_text: str) -> str:
    """从摘要中提取最有意思的一句话"""
    lines = summary_text.split("\n")
    candidates = []
    for line in lines:
        stripped = line.strip()
        # 找关键发言、Notable 等有"金句感"的内容
        if any(k in stripped for k in ["「", "」", '"', '"', '"', '"', "说：", "："]):
            # 清理一下
            clean = stripped.strip("•-1234567890.、:： ").strip()
            if 10 < len(clean) < 150:
                candidates.append(clean)
    if candidates:
        return candidates[0]
    # 兜底：找最长的非结构化句子
    for line in reversed(lines):
        stripped = line.strip()
        if len(stripped) > 20 and not stripped.startswith("#") and "：" not in stripped[:10]:
            return stripped[:100]
    return ""


def _generate_headline(summary_text: str, chat_name: str) -> str:
    """用 LLM 生成报纸风格的标题"""
    import llm as llm_module

    prompt = f"""你是一个微信群聊报纸标题生成器。请根据以下摘要，给这个群聊生成一个简短有趣的报纸风格标题。

【群名】：{chat_name}
【摘要内容】：
{summary_text[:800]}

要求：
- 标题要有新闻感、趣闻感，读起来像在看报纸头条
- 8-20 个字
- 可以用 emoji 增加活泼感
- 不要太正经，要有一点"今日焦点"的意味
- 直接输出标题，不要解释

标题："""

    try:
        result = llm_module.complete(prompt, max_tokens=50)
        result = result.strip()
        if result and len(result) < 50:
            return result
    except Exception:
        pass

    # 兜底标题
    if "项目" in chat_name:
        return f"🔥 {chat_name}今日战报来啦"
    elif "家人" in chat_name or "家庭" in chat_name:
        return f"🏠 {chat_name}：今日份温馨请查收"
    elif "同学" in chat_name:
        return f"👨‍🎓 {chat_name}：今日份回忆杀"
    else:
        return f"📢 {chat_name}：今日群聊精选"


def _generate_subheadline(summary_text: str) -> str:
    """生成副标题（次条）"""
    import llm as llm_module

    prompt = f"""你是一个微信群聊副标题生成器。请根据摘要，生成一句简短的次条说明（1句话）。

【摘要】：
{summary_text[:600]}

要求：
- 5-15 个字
- 突出最有意思的一点
- 要有一点"新闻摘要"的感觉
- 直接输出，不要解释

副标题："""

    try:
        result = llm_module.complete(prompt, max_tokens=30)
        result = result.strip()
        if result and len(result) < 30:
            return result
    except Exception:
        pass
    return ""


def _generate_fun_facts(summary_text: str) -> list[str]:
    """生成趣味统计（报纸侧栏用的"今日数据"）"""
    import llm as llm_module

    prompt = f"""你是一个微信群聊趣味统计员。请从摘要中提取3个有趣的统计或观察，用轻松幽默的方式表达。

【摘要】：
{summary_text[:800]}

要求：
- 输出3条
- 每条不超过25个字
- 格式自由，要像报纸侧栏的"今日趣味数据"
- 可以带一点夸张或幽默感
- 直接输出3条，用换行分隔

示例格式：
某某群今日发言人均50字，废话含量超标
群里今天出现了XX次"哈哈哈哈"
今日最卷的人发言了XX次

趣味数据："""

    try:
        result = llm_module.complete(prompt, max_tokens=150)
        lines = [l.strip() for l in result.strip().split("\n") if l.strip()]
        return [l for l in lines if 5 < len(l) < 50][:3]
    except Exception:
        return []


def _render_single_newspaper_session(
    sess: dict,
    headline: str,
    subheadline: str,
    quote: str,
    session_stats: dict = None,
) -> list[str]:
    """渲染单个会话的报纸格式"""
    lines = []
    chat_name = sess.get("chat_name", "未知")
    summary_text = sess.get("summary", "")
    parsed = _parse_summary_to_dict(summary_text)
    session_stats = session_stats or {}

    # 会话标题栏
    lines.append(f"  【{chat_name}】")
    lines.append("")

    # 头条
    if headline:
        lines.append(f"  📰 头条：{headline}")
        lines.append("")

    # 副标题
    if subheadline:
        lines.append(f"  📌 次条：{subheadline}")
        lines.append("")

    # 金句
    if quote:
        lines.append(f"  💬 金句：{quote}")
        lines.append("")

    # 重要信息（趣味侧栏风格）
    key_mentions = parsed.get("key_mentions", [])
    if key_mentions:
        lines.append(f"  📋 今日要点：")
        for m in key_mentions[:3]:
            lines.append(f"    • {m}")
        lines.append("")

    # 行动项（不正经的表述）
    action_items = parsed.get("action_items", [])
    if action_items:
        lines.append(f"  📌 有人立了 flag（待办）：")
        for a in action_items[:3]:
            lines.append(f"    • {a}")
        lines.append("")

    # 待确认
    open_questions = parsed.get("open_questions", [])
    if open_questions:
        lines.append(f"  🤔 还有人没回话：")
        for q in open_questions[:3]:
            lines.append(f"    • {q}")
        lines.append("")

    # Notable
    notable = parsed.get("notable", [])
    if notable:
        lines.append(f"  🎯 值得记录：")
        for n in notable[:3]:
            lines.append(f"    • {n}")
        lines.append("")

    # ===== 统计模块（方向一） =====
    if session_stats:
        # 发言排行榜
        speaker = session_stats.get("speaker_stats", {})
        ranked = speaker.get("ranked", [])
        if ranked:
            lines.append("  ┌──────────────────────────────────┐")
            medals = ["🥇", "🥈", "🥉"]
            for i, (name, count) in enumerate(ranked[:3]):
                medal = medals[i]
                dn = name[:8] + ".." if len(name) > 8 else name
                lines.append(f"  │ {medal} {dn:<12} {count}条              │")
            if len(ranked) > 3:
                lines.append(f"  │  🏊 潜水达人：{ranked[-1][0][:8]}（{ranked[-1][1]}条）     │")
            lines.append("  └──────────────────────────────────┘")
            lines.append("")

        # 群话题天气
        group_weather = session_stats.get("group_weather", "")
        if group_weather:
            lines.append(f"  🌤️ {group_weather}")
            lines.append("")

        # 媒体统计
        media = session_stats.get("media_stats", {})
        if media.get("total", 0) > 0:
            parts = []
            if media.get("images", 0) > 0:
                parts.append(f"📷{media['images']}")
            if media.get("videos", 0) > 0:
                parts.append(f"🎬{media['videos']}")
            if media.get("files", 0) > 0:
                parts.append(f"📎{media['files']}")
            if media.get("voice", 0) > 0:
                parts.append(f"🎤{media['voice']}")
            if parts:
                lines.append(f"  📦 媒体产出：{' '.join(parts)}")
                lines.append("")

        # 链接雷达
        link = session_stats.get("link_stats", {})
        if link.get("total", 0) > 0:
            cats = link.get("categories", {})
            cat_str = " / ".join(f"{k}{v}个" for k, v in list(cats.items())[:4])
            lines.append(f"  🔗 链接：共{link['total']}个，{cat_str}")
            lines.append("")

        # 热词
        hot = session_stats.get("hot_words", {})
        words = hot.get("words", [])
        laugh = hot.get("laugh_count", 0)
        question = hot.get("question_count", 0)
        if words:
            top_word = words[0][0] if words else ""
            top_count = words[0][1] if words else 0
            lines.append(f"  🔥 热词：{top_word}×{top_count}")
            extras = []
            if laugh >= 5:
                extras.append(f"😂哈哈哈{laugh}次")
            if question >= 3:
                extras.append(f"❓提问{question}次")
            if extras:
                lines.append(f"     {' | '.join(extras)}")
            lines.append("")

    return lines


def render_newspaper_report(
    account_purpose: str,
    session_summaries: list[dict],
    target_date: date,
    classification: dict = None,
) -> str:
    """
    渲染娱乐报纸风格。
    适用于：家人群、朋友群、兴趣群、同学群等。
    集成方向一全部7个统计模块。
    """
    date_str = target_date.strftime("%Y年%m月%d日")
    issue_no = target_date.strftime("%m%d%y")

    lines = []

    # ===== 报头 =====
    lines.append("")
    lines.append("  ╔══════════════════════════════════════════════════╗")
    lines.append("  ║                                                          ║")
    lines.append("  ║        🗞️  WEIXIN DAILY · 你的群聊小报           ║")
    lines.append(f"  ║              {date_str} · 第 {issue_no} 期              ║")
    lines.append("  ║                                                          ║")
    lines.append("  ╚══════════════════════════════════════════════════╝")
    lines.append("")

    # ===== 遍历每个会话 =====
    for i, sess in enumerate(session_summaries, 1):
        chat_name = sess.get("chat_name", "未知会话")
        summary_text = sess.get("summary", "")
        parsed = _parse_summary_to_dict(summary_text)
        quote = _extract_quote(summary_text)
        headline = _generate_headline(summary_text, chat_name)
        subheadline = _generate_subheadline(summary_text)
        session_stats = sess.get("session_stats", {})

        lines.append("")
        lines.append(f"  ┌──────────────────────────────────────────────┐")
        lines.append(f"  │  📰 会话 {i}：{chat_name:<32}  │")
        lines.append(f"  └──────────────────────────────────────────────┘")
        lines.append("")

        # 头条 + 副标题
        if headline:
            lines.append(f"  ┃  📰 头条：{headline}")
        if subheadline:
            lines.append(f"  ┃  📌 次条：{subheadline}")
        lines.append("")

        # 金句
        if quote:
            lines.append(f"  ┃  💬 金句：「{quote[:60]}{'...' if len(quote)>60 else ''}」")
            lines.append("")

        # ===== 7 大统计模块 =====
        s = session_stats

        # 模块1：发言排行榜
        speaker = s.get("speaker_stats", {})
        ranked = speaker.get("ranked", [])
        if ranked:
            lines.append("  ┃  🏆 发言排行榜")
            medals = ["🥇", "🥈", "🥉"]
            for i_rank, (name, count) in enumerate(ranked[:3]):
                medal = medals[i_rank]
                dn = name[:10] + ".." if len(name) > 10 else name
                bar_len = min(10, count)
                bar = "█" * bar_len
                lines.append(f"  ┃    {medal} {dn:<12} {bar} {count}条")
            if len(ranked) > 3:
                lines.append(f"  ┃    🏊 潜水达人：{ranked[-1][0][:10]}（仅{ranked[-1][1]}条）")
            lines.append("")

        # 模块2：群话题天气
        group_weather = s.get("group_weather", "")
        if group_weather:
            lines.append(f"  ┃  🌤️ {group_weather}")
            lines.append("")

        # 模块3：活跃脉搏
        pulse = s.get("activity_pulse", {})
        if pulse.get("total", 0) > 0:
            peak = pulse.get("peak_hour", 0)
            density = pulse.get("density", 0)
            total = pulse.get("total", 0)
            lines.append(f"  ┃  📈 活跃脉搏：{total}条 / 最热{peak:02d}:00 / 均{density}条-时")
            lines.append("")

        # 模块4：今日热词
        hot = s.get("hot_words", {})
        words = hot.get("words", [])
        laugh = hot.get("laugh_count", 0)
        question = hot.get("question_count", 0)
        if words:
            top_word = words[0][0] if words else ""
            top_count = words[0][1] if words else 0
            extras = []
            if laugh >= 5:
                extras.append(f"😂哈哈哈{laugh}次")
            if question >= 3:
                extras.append(f"❓提问{question}次")
            extras_str = (" | " + " | ".join(extras)) if extras else ""
            lines.append(f"  ┃  🔥 热词：{top_word}×{top_count}{extras_str}")
            lines.append("")

        # 模块5：媒体统计
        media = s.get("media_stats", {})
        if media.get("total", 0) > 0:
            parts = []
            if media.get("images", 0) > 0:
                parts.append(f"📷{media['images']}张")
            if media.get("videos", 0) > 0:
                parts.append(f"🎬{media['videos']}个")
            if media.get("files", 0) > 0:
                parts.append(f"📎{media['files']}份")
            if media.get("voice", 0) > 0:
                parts.append(f"🎤{media['voice']}条")
            if parts:
                lines.append(f"  ┃  📦 媒体产出：{' '.join(parts)}")
                lines.append("")

        # 模块6：链接雷达
        link = s.get("link_stats", {})
        if link.get("total", 0) > 0:
            cats = link.get("categories", {})
            top_cats = list(cats.items())[:4]
            cat_str = " / ".join(f"{k}{v}个" for k, v in top_cats)
            lines.append(f"  ┃  🔗 链接雷达：共{link['total']}个，{cat_str}")
            lines.append("")

        # 模块7：Emoji风云榜
        emoji = s.get("emoji_stats", {})
        if emoji.get("total", 0) > 0:
            top_emojis = emoji.get("top", [])[:5]
            emoji_str = " ".join(f"{e}×{c}" for e, c in top_emojis)
            lines.append(f"  ┃  😀 Emoji：共{emoji['total']}个 / {emoji_str}")
            lines.append("")

        # 摘要核心内容
        overview = parsed.get("overview", "")
        key_mentions = parsed.get("key_mentions", [])
        action_items = parsed.get("action_items", [])
        open_questions = parsed.get("open_questions", [])
        notable = parsed.get("notable", [])

        if overview:
            lines.append(f"  ┃  📝 {overview[:60]}{'...' if len(overview)>60 else ''}")
        if key_mentions:
            lines.append(f"  ┃  📋 重要：{key_mentions[0][:45]}{'...' if len(key_mentions[0])>45 else ''}")
        if action_items:
            lines.append(f"  ┃  📌 待办：{action_items[0][:45]}{'...' if len(action_items[0])>45 else ''}")
        if open_questions:
            lines.append(f"  ┃  🤔 待复：{open_questions[0][:45]}{'...' if len(open_questions[0])>45 else ''}")

        lines.append("  " + "─" * 53)

    # ===== 全局统计汇总（报纸尾版）=====
    all_stats = {"total_sessions": len(session_summaries)}
    for sess in session_summaries:
        s = sess.get("session_stats", {})
        for key in ["speaker_stats", "hot_words", "media_stats", "link_stats", "emoji_stats", "activity_pulse"]:
            pass  # 汇总在下面统一显示

    # 汇总发言总数
    total_msgs = sum(
        sess.get("session_stats", {}).get("activity_pulse", {}).get("total", 0)
        for sess in session_summaries
    )
    total_speakers = sum(
        len(sess.get("session_stats", {}).get("speaker_stats", {}).get("ranked", []))
        for sess in session_summaries
    )

    lines.append("")
    lines.append("  ╔══════════════════════════════════════════════════╗")
    lines.append(f"  ║  📊 全局汇总：共 {len(session_summaries)} 个会话 / {total_msgs} 条消息 / {total_speakers} 人发言  ║")
    lines.append(f"  ║  🌙 {date.strftime('%Y-%m-%d')} · 以上内容由微信聊天记录总结器生成       ║")
    lines.append("  ╚══════════════════════════════════════════════════╝")
    lines.append("")

    return "\n".join(lines)


# =============================================================================
# 统一渲染入口
# =============================================================================

def render_report(
    account_purpose: str,
    session_summaries: list[dict],
    target_date: date,
    classification: dict = None,
) -> str:
    """
    统一渲染入口。根据 classification 自动选择渲染风格。
    """
    style = (classification or {}).get("global_style", "newspaper")

    if style == "work":
        return render_work_report(account_purpose, session_summaries, target_date, classification)
    else:
        return render_newspaper_report(account_purpose, session_summaries, target_date, classification)


# =============================================================================
# 辅助函数：解析摘要文本为结构化 dict
# =============================================================================

def _parse_summary_to_dict(summary_text: str) -> dict:
    """
    将 LLM 生成的摘要文本解析为结构化 dict。
    这是一个尽力而为的解析，失败时返回原文本。
    """
    result = {
        "overview": "",
        "action_items": [],
        "decisions": [],
        "key_mentions": [],
        "deadlines": [],
        "key_statements": [],
        "open_questions": [],
        "notable": [],
    }

    current_section = None
    current_items = []

    section_keywords = {
        "概览": "overview",
        "行动项": "action_items",
        "action items": "action_items",
        "决策": "decisions",
        "decisions": "decisions",
        "重要": "key_mentions",
        "key mentions": "key_mentions",
        "时间节点": "deadlines",
        "dates": "deadlines",
        "关键发言": "key_statements",
        "key statements": "key_statements",
        "悬而未决": "open_questions",
        "open questions": "open_questions",
        "待确认": "open_questions",
        "值得注意": "notable",
        "notable": "notable",
        "风险": "notable",
    }

    for line in summary_text.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue

        # 检测章节标题
        matched_section = None
        for kw, key in section_keywords.items():
            if stripped.startswith("#") or re.match(rf"^\s*##?\s*{kw}", stripped, re.I):
                if kw not in ("概览",):
                    matched_section = key
                    break
            elif stripped.startswith("##") and kw.lower() in stripped.lower():
                matched_section = key
                break

        if matched_section:
            # 保存上一个 section
            if current_section and current_items:
                if current_section == "overview":
                    result[current_section] = " ".join(current_items)
                else:
                    result[current_section].extend(current_items)
            current_section = matched_section
            current_items = []
            continue

        # 收集内容行
        if current_section:
            # 去掉列表标记
            clean = re.sub(r"^[\-\*\d.。、]+", "", stripped).strip()
            clean = clean.lstrip("📋✅✔️📎⏰❓⚠️🎯·:： ").strip()
            if clean and len(clean) > 2:
                current_items.append(clean)

    # 保存最后一个 section
    if current_section and current_items:
        if current_section == "overview":
            result[current_section] = " ".join(current_items)
        else:
            result[current_section].extend(current_items)

    # 如果 overview 为空，尝试用第一段非列表内容
    if not result["overview"]:
        for line in summary_text.split("\n"):
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and not stripped.startswith("-"):
                if 5 < len(stripped) < 200:
                    result["overview"] = stripped
                    break

    return result
