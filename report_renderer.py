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
    my_display_name: str = "我",
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
    lines.append(f"  ║  🌙 {target_date.strftime('%Y-%m-%d')} · 以上内容由微信聊天记录总结器生成       ║")
    lines.append("  ╚══════════════════════════════════════════════════╝")
    lines.append("")

    return "\n".join(lines)


# =============================================================================
# 卡片式 HTML 渲染器（现代卡片布局）
# =============================================================================

def _h(s: str) -> str:
    """HTML 转义"""
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _truncate(s: str, max_len: int = 120) -> str:
    if not s:
        return ""
    s = str(s)
    return s[:max_len] + ("..." if len(s) > max_len else "")


def render_newspaper_report_cards(
    account_purpose: str,
    session_summaries: list[dict],
    target_date,
    classification: dict = None,
    my_display_name: str = "我",
) -> str:
    """
    渲染卡片式报纸风格报告（HTML）。
    包含：报头卡片、会话卡片（含7大统计模块）、汇总尾卡。
    """
    classification = classification or {}
    date_str = target_date.strftime("%Y年%m月%d日") if hasattr(target_date, 'strftime') else str(target_date)
    issue_no = target_date.strftime("%m%d%y") if hasattr(target_date, 'strftime') else "001"

    # ---- CSS ----
    css = """<style>
    :root {
      --primary: #4f46e5;
      --primary-light: #818cf8;
      --accent: #f59e0b;
      --accent-light: #fcd34d;
      --bg-page: #f0f2f5;
      --bg-card: #ffffff;
      --bg-masthead: linear-gradient(135deg, #1e3a5f 0%, #4f46e5 50%, #7c3aed 100%);
      --text-primary: #1f2937;
      --text-secondary: #6b7280;
      --text-light: #9ca3af;
      --border: #e5e7eb;
      --shadow: 0 4px 6px -1px rgba(0,0,0,0.07), 0 2px 4px -1px rgba(0,0,0,0.04);
      --shadow-lg: 0 10px 15px -3px rgba(0,0,0,0.08), 0 4px 6px -2px rgba(0,0,0,0.04);
      --radius: 16px;
      --radius-sm: 10px;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, "Microsoft YaHei", "PingFang SC", sans-serif;
           background: var(--bg-page); color: var(--text-primary); line-height: 1.6; }
    .report { max-width: 900px; margin: 30px auto; padding: 0 16px 40px; }

    /* 卡片通用 */
    .card { background: var(--bg-card); border-radius: var(--radius); box-shadow: var(--shadow);
            overflow: hidden; margin-bottom: 20px; }

    /* 报头卡片 */
    .masthead {
      background: var(--bg-masthead); color: white; padding: 36px 32px; text-align: center;
      border-radius: var(--radius) !important; margin-bottom: 24px;
    }
    .masthead-title { font-size: 2em; font-weight: 800; letter-spacing: 0.05em;
                       margin-bottom: 8px; }
    .masthead-title span { color: var(--accent-light); }
    .masthead-sub { font-size: 0.95em; opacity: 0.85; letter-spacing: 0.1em; }
    .masthead-badge { display: inline-block; background: rgba(255,255,255,0.15);
                      border: 1px solid rgba(255,255,255,0.3); border-radius: 20px;
                      padding: 4px 16px; font-size: 0.8em; margin-top: 12px; }

    /* 会话卡片 */
    .session-card { padding: 0; }
    .card-header {
      background: linear-gradient(90deg, var(--primary) 0%, var(--primary-light) 100%);
      color: white; padding: 20px 24px; display: flex; align-items: center;
      gap: 12px;
    }
    .session-name { font-size: 1.15em; font-weight: 700; }
    .chat-type-badge {
      background: rgba(255,255,255,0.2); border: 1px solid rgba(255,255,255,0.3);
      border-radius: 20px; padding: 2px 12px; font-size: 0.78em;
    }
    .card-body { padding: 20px 24px; }

    /* 头条 */
    .headline-block { background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
                      border-left: 4px solid var(--accent); border-radius: var(--radius-sm);
                      padding: 14px 18px; margin-bottom: 16px; }
    .headline { font-size: 1.05em; font-weight: 700; color: #92400e; margin-bottom: 4px; }
    .subheadline { font-size: 0.88em; color: #b45309; }

    /* 金句 */
    .golden-quote {
      background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
      border-left: 4px solid var(--primary); border-radius: var(--radius-sm);
      padding: 12px 16px; margin-bottom: 16px; font-size: 0.92em;
      color: #1e40af;
    }
    .quote-speaker { font-weight: 700; }

    /* 统计网格 */
    .stats-grid {
      display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px; margin-bottom: 16px;
    }
    .stat-card {
      background: var(--bg-page); border: 1px solid var(--border);
      border-radius: var(--radius-sm); padding: 12px 14px;
    }
    .stat-title { font-size: 0.78em; font-weight: 700; color: var(--text-secondary);
                  text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px;
                  display: flex; align-items: center; gap: 6px; }
    .stat-content { font-size: 0.9em; color: var(--text-primary); }

    /* 发言排行条 */
    .speaker-bar { display: flex; align-items: center; gap: 8px; margin-bottom: 5px; }
    .speaker-bar .medal { font-size: 0.9em; }
    .speaker-bar .name { font-size: 0.85em; font-weight: 600; min-width: 60px; }
    .speaker-bar .bar-wrap { flex: 1; height: 8px; background: var(--border); border-radius: 4px; overflow: hidden; }
    .speaker-bar .bar-fill { height: 100%; background: var(--primary); border-radius: 4px; }
    .speaker-bar .count { font-size: 0.78em; color: var(--text-secondary); min-width: 30px; text-align: right; }

    /* 热词标签 */
    .word-tags { display: flex; flex-wrap: wrap; gap: 6px; }
    .word-tag { background: #fef3c7; color: #92400e; border-radius: 20px; padding: 2px 10px; font-size: 0.8em; }

    /* Emoji 展示 */
    .emoji-row { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
    .emoji-chip { background: #f3e8ff; color: #6b21a8; border-radius: 8px; padding: 2px 8px; font-size: 0.82em; }

    /* 媒体徽章 */
    .media-badges { display: flex; flex-wrap: wrap; gap: 8px; }
    .media-badge { display: flex; align-items: center; gap: 4px; background: #f3f4f6;
                   border-radius: 8px; padding: 4px 10px; font-size: 0.82em; }

    /* 链接分类 */
    .link-pills { display: flex; flex-wrap: wrap; gap: 6px; }
    .link-pill { background: #ecfdf5; color: #065f46; border-radius: 20px; padding: 2px 10px; font-size: 0.8em; }

    /* 活跃脉搏条 */
    .pulse-bars { display: flex; align-items: flex-end; gap: 2px; height: 36px; }
    .pulse-bar-wrap { flex: 1; display: flex; align-items: flex-end; }
    .pulse-bar { width: 100%; background: var(--primary-light); border-radius: 2px 2px 0 0; min-height: 2px; }

    /* 摘要内容区 */
    .summary-section { margin-bottom: 12px; }
    .summary-section-title {
      font-size: 0.8em; font-weight: 700; color: var(--primary);
      text-transform: uppercase; letter-spacing: 0.05em;
      border-bottom: 2px solid var(--primary); display: inline-block;
      margin-bottom: 6px; padding-bottom: 2px;
    }
    .summary-section ul { padding-left: 18px; }
    .summary-section li { font-size: 0.88em; color: var(--text-primary); margin-bottom: 3px; }
    .summary-section p { font-size: 0.88em; color: var(--text-secondary); }

    /* 分隔线 */
    .divider { border: none; border-top: 1px solid var(--border); margin: 16px 0; }

    /* 尾卡 */
    .footer-card { background: var(--text-primary); color: white; padding: 20px 24px;
                   border-radius: var(--radius) !important; text-align: center; }
    .footer-stats { display: flex; justify-content: center; gap: 32px; margin-bottom: 10px; flex-wrap: wrap; }
    .footer-stat { text-align: center; }
    .footer-stat-num { font-size: 1.8em; font-weight: 800; color: var(--accent-light); }
    .footer-stat-label { font-size: 0.78em; opacity: 0.7; }
    .footer-credit { font-size: 0.78em; opacity: 0.5; margin-top: 8px; }

    /* 无数据提示 */
    .no-data { color: var(--text-light); font-size: 0.85em; font-style: italic; }
  </style>"""

    # ---- HTML Body ----
    html_parts = [css]

    # === 报头 ===
    html_parts.append("""<div class="report">""")
    html_parts.append(f"""<div class="card masthead">
  <div class="masthead-title">🗞️ WEIXIN <span>DAILY</span></div>
  <div class="masthead-sub">你的群聊小报 · {date_str}</div>
  <div class="masthead-badge">第 {issue_no} 期</div>
</div>""")

    # === 逐个会话卡片 ===
    for i, sess in enumerate(session_summaries, 1):
        chat_name = _h(sess.get("chat_name", "未知会话"))
        chat_type = _h(sess.get("chat_type", "群聊"))
        summary_text = sess.get("summary", "")
        s = sess.get("session_stats", {}) or {}

        # 将 LLM 摘要中的 "me" 替换为用户真实名称（处理 **me**、[me]、me：等多种格式）
        import re
        summary_text = re.sub(r'\*\*me\*\*', f'**{my_display_name}**', summary_text)
        summary_text = re.sub(r'\[me\]', f'[{my_display_name}]', summary_text)
        summary_text = re.sub(r'\bme\b', my_display_name, summary_text)

        # 解析摘要
        parsed = _parse_summary_to_dict(summary_text)

        # 提取金句
        quote_text = ""
        for line in summary_text.split("\n"):
            line = line.strip()
            if line.startswith("**") and "：" in line:
                quote_text = line.strip("*：").strip()
                break
        if not quote_text:
            quote_text = _truncate(parsed.get("key_statements", [""])[0] if parsed.get("key_statements") else "", 100)

        # 头条/次条：优先使用有实质内容的字段，避免 LLM 废话占位
        _GENERIC_OVERVIEW_STARTS = (
            "好的", "以下是", "用简单的话", "这是一个", "根据您", "聊天记录分析",
            "结构化", "整理", "提供", "生成", "下面", "此处", "本群",
        )

        # 从 key_statements / notable / overview 找非废话内容作为头条
        key_stmts = parsed.get("key_statements", [])
        notable_items = parsed.get("notable", [])
        overview = parsed.get("overview", "")
        headline = ""
        for src in [key_stmts, notable_items, ([overview] if overview else [])]:
            for item in src:
                item_str = str(item).strip()
                if len(item_str) > 15 and not any(item_str.startswith(g) for g in _GENERIC_OVERVIEW_STARTS):
                    headline = _truncate(item_str, 60)
                    break
            if headline:
                break

        # 如果还是空的，直接从摘要原文第一段提取
        if not headline:
            for line in summary_text.split("\n"):
                line = line.strip()
                # 跳过标题、列表标记、废话开头
                if not line:
                    continue
                if line.startswith("#"):
                    continue
                if len(line) > 15 and not any(line.startswith(g) for g in _GENERIC_OVERVIEW_STARTS):
                    # 去掉列表标记
                    clean = re.sub(r"^[\-\*\d.。、]+", "", line).strip()
                    if len(clean) > 10:
                        headline = _truncate(clean, 60)
                        break
        if not headline:
            headline = "今日群聊摘要"

        # 次条：优先用 key_mentions，次用 notable；直接拼接，不截断不省略
        mentions = parsed.get("key_mentions", [])
        mention_strs = [str(m).strip() for m in mentions[:2] if m]
        subheadline = " / ".join(mention_strs) if mention_strs else ""
        # 如果次条为空，用 notable 的第一条
        if not subheadline or subheadline == " / ":
            notable_strs = [str(n).strip() for n in notable_items[:1] if n]
            subheadline = " / ".join(notable_strs)
        if not subheadline or subheadline == " / ":
            notable_strs = [str(n).strip() for n in notable_items[:2] if n]
            notable_strs = [_truncate(n, 30) for n in notable_strs]
            subheadline = " / ".join(notable_strs)

        # ---- Card Header ----
        card_parts = [f"""<div class="card session-card">
  <div class="card-header">
    <span class="session-name">📢 {chat_name}</span>
    <span class="chat-type-badge">{chat_type}</span>
  </div>
  <div class="card-body">"""]

        # ---- 头条 ----
        card_parts.append(f"""<div class="headline-block">
  <div class="headline">📰 头条：{_h(headline)}</div>
  <div class="subheadline">📌 次条：{_h(subheadline)}</div>
</div>""")

        # ---- 金句 ----
        if quote_text:
            card_parts.append(f"""<div class="golden-quote">
  💬 金句：「{_h(quote_text)}」
</div>""")

        # === 7 大统计模块 ===
        # DEBUG
        import sys as _sys
        _sys.stderr.write(f"DEBUG s type: {type(s).__name__}, s={repr(s)[:200]}\n")
        if not isinstance(s, dict):
            s = {}
        stats_html = _render_stats_modules(s)
        card_parts.append(f"<div class='stats-grid'>{stats_html}</div>")

        # === 摘要内容 ===
        summary_html = _render_summary_sections(parsed)
        card_parts.append(summary_html)

        card_parts.append("  </div><!-- card-body -->")
        card_parts.append("</div><!-- session-card -->")
        html_parts.append("\n".join(card_parts))

    # === 全局汇总尾卡 ===
    total_msgs = sum(
        (sess.get("session_stats") or {}).get("activity_pulse", {}).get("total", 0)
        for sess in session_summaries
    )
    total_speakers = sum(
        len((sess.get("session_stats") or {}).get("speaker_stats", {}).get("ranked", []))
        for sess in session_summaries
    )
    html_parts.append(f"""<div class="card footer-card">
  <div class="footer-stats">
    <div class="footer-stat">
      <div class="footer-stat-num">{len(session_summaries)}</div>
      <div class="footer-stat-label">个会话</div>
    </div>
    <div class="footer-stat">
      <div class="footer-stat-num">{total_msgs}</div>
      <div class="footer-stat-label">条消息</div>
    </div>
    <div class="footer-stat">
      <div class="footer-stat-num">{total_speakers}</div>
      <div class="footer-stat-label">人发言</div>
    </div>
  </div>
  <div class="footer-credit">🌙 {date_str} · 微信聊天记录总结器生成</div>
</div>""")

    html_parts.append("</div><!-- report -->")

    return "\n".join(html_parts)


def _render_stats_modules(s: dict) -> str:
    """渲染7大统计模块为 HTML 片段"""
    parts = []

    # 1. 发言排行榜
    speaker_html = _render_speaker_stats(s.get("speaker_stats", {}))
    parts.append(f'<div class="stat-card">{speaker_html}</div>')

    # 2. 群天气
    weather_html = _render_group_weather(s.get("group_weather", ""))
    parts.append(f'<div class="stat-card">{weather_html}</div>')

    # 3. 活跃脉搏
    pulse_html = _render_activity_pulse(s.get("activity_pulse", {}))
    parts.append(f'<div class="stat-card">{pulse_html}</div>')

    # 4. 热词
    hot_html = _render_hot_words(s.get("hot_words", {}))
    parts.append(f'<div class="stat-card">{hot_html}</div>')

    # 5. 媒体统计
    media_html = _render_media_stats(s.get("media_stats", {}))
    parts.append(f'<div class="stat-card">{media_html}</div>')

    # 6. 链接雷达
    link_html = _render_link_stats(s.get("link_stats", {}))
    parts.append(f'<div class="stat-card">{link_html}</div>')

    # 7. Emoji 风云榜
    emoji_html = _render_emoji_stats(s.get("emoji_stats", {}))
    parts.append(f'<div class="stat-card">{emoji_html}</div>')

    return "".join(parts)


def _render_speaker_stats(sp: dict) -> str:
    ranked = sp.get("ranked", [])
    content = ""
    if ranked:
        medals = ["🥇", "🥈", "🥉"]
        max_count = ranked[0][1] if ranked else 1
        for idx, (name, count) in enumerate(ranked[:5]):
            medal = medals[idx] if idx < 3 else f"{idx+1}."
            bar_pct = min(100, int(count / max_count * 100))
            safe_name = _h(name[:8]) + (".." if len(name) > 8 else "")
            content += f"""<div class="speaker-bar">
  <span class="medal">{medal}</span>
  <span class="name">{safe_name}</span>
  <div class="bar-wrap"><div class="bar-fill" style="width:{bar_pct}%"></div></div>
  <span class="count">{count}条</span>
</div>"""
    else:
        content = '<span class="no-data">暂无数据</span>'
    return f"<div class='stat-title'>🏆 发言排行</div><div class='stat-content'>{content}</div>"


def _render_group_weather(weather: str) -> str:
    if not weather:
        weather = "暂无数据"
    return f"<div class='stat-title'>🌤️ 群天气</div><div class='stat-content' style='font-size:0.85em'>{_h(weather)}</div>"


def _render_activity_pulse(pulse: dict) -> str:
    total = pulse.get("total", 0)
    if total == 0:
        return "<div class='stat-title'>📈 活跃脉搏</div><div class='stat-content'><span class='no-data'>暂无数据</span></div>"

    hours = pulse.get("hours", {})
    peak = pulse.get("peak_hour", 0)
    density = pulse.get("density", 0)
    max_h = max(hours.values()) if hours else 1

    bars = ""
    for h in range(24):
        count = hours.get(h, 0)
        bar_h = max(2, int(count / max_h * 36)) if max_h > 0 else 2
        title = f"{h}:00 - {count}条"
        bars += f"<div class='pulse-bar-wrap' title='{title}'><div class='pulse-bar' style='height:{bar_h}px'></div></div>"

    content = f"""<div style="font-size:0.82em;color:#6b7280;margin-bottom:6px">
  共{total}条 · 最热 {peak:02d}:00 · 均{density}条/时
</div>
<div class="pulse-bars">{bars}</div>
<div style="font-size:0.7em;color:#9ca3af;margin-top:4px">00  04  08  12  16  20  23时</div>"""
    return f"<div class='stat-title'>📈 活跃脉搏</div><div class='stat-content'>{content}</div>"


def _render_hot_words(hot: dict) -> str:
    words = hot.get("words", [])
    laugh = hot.get("laugh_count", 0)
    question = hot.get("question_count", 0)
    if not words:
        return "<div class='stat-title'>🔥 热词</div><div class='stat-content'><span class='no-data'>暂无数据</span></div>"
    tags = "".join(f"<span class='word-tag'>{_h(w)}×{c}</span>" for w, c in words[:6])
    extras = ""
    if laugh >= 3:
        extras += f"<span class='word-tag' style='background:#fef3c7'>😂×{laugh}</span>"
    if question >= 3:
        extras += f"<span class='word-tag' style='background:#eff6ff'>❓×{question}</span>"
    return f"<div class='stat-title'>🔥 热词</div><div class='stat-content'><div class='word-tags'>{tags}{extras}</div></div>"


def _render_media_stats(media: dict) -> str:
    total = media.get("total", 0)
    if total == 0:
        return "<div class='stat-title'>📦 媒体</div><div class='stat-content'><span class='no-data'>暂无媒体</span></div>"
    parts = []
    if media.get("images", 0) > 0:
        parts.append(f"<span class='media-badge'>📷 {media['images']}张</span>")
    if media.get("videos", 0) > 0:
        parts.append(f"<span class='media-badge'>🎬 {media['videos']}个</span>")
    if media.get("files", 0) > 0:
        parts.append(f"<span class='media-badge'>📎 {media['files']}份</span>")
    if media.get("voice", 0) > 0:
        parts.append(f"<span class='media-badge'>🎤 {media['voice']}条</span>")
    content = " ".join(parts) if parts else '<span class="no-data">暂无媒体</span>'
    return f"<div class='stat-title'>📦 媒体产出</div><div class='stat-content'><div class='media-badges'>{content}</div></div>"


def _render_link_stats(link: dict) -> str:
    total = link.get("total", 0)
    if total == 0:
        return "<div class='stat-title'>🔗 链接</div><div class='stat-content'><span class='no-data'>暂无链接</span></div>"
    cats = link.get("categories", {})
    pills = "".join(f"<span class='link-pill'>{_h(k)} {v}个</span>" for k, v in list(cats.items())[:4])
    return f"<div class='stat-title'>🔗 链接雷达</div><div class='stat-content'><div class='link-pills'>{pills}</div></div>"


def _render_emoji_stats(emoji: dict) -> str:
    total = emoji.get("total", 0)
    if total == 0:
        return "<div class='stat-title'>😀 Emoji</div><div class='stat-content'><span class='no-data'>暂无 Emoji</span></div>"
    top = emoji.get("top", [])[:6]
    chips = "".join(f"<span class='emoji-chip'>{_h(e)}×{c}</span>" for e, c in top)
    return f"<div class='stat-title'>😀 Emoji 风云榜</div><div class='stat-content'><div class='emoji-row'>{chips}</div></div>"


def _render_summary_sections(parsed: dict) -> str:
    """渲染摘要的各结构化章节"""
    sections_html = []
    section_defs = [
        ("overview", "📋 群聊概览"),
        ("action_items", "✅ 行动项"),
        ("decisions", "✔️ 决策结论"),
        ("key_mentions", "📎 重要提及"),
        ("deadlines", "⏰ 时间节点"),
        ("key_statements", "💬 关键发言"),
        ("open_questions", "🤔 悬而未决"),
        ("notable", "⚠️ 值得注意"),
    ]
    has_content = False
    for key, title in section_defs:
        items = parsed.get(key, [])
        if not items:
            continue
        has_content = True
        if isinstance(items, str):
            items = [items]
        lis = "".join(f"<li>{_h(str(item)[:200])}</li>" for item in items[:5])
        sections_html.append(f"""<div class="summary-section">
  <div class="summary-section-title">{title}</div>
  <ul>{lis}</ul>
</div>""")
    if not has_content:
        return ""
    return "<hr class='divider'>" + "\n".join(sections_html)


# =============================================================================
# 统一渲染入口
# =============================================================================

def render_report(
    account_purpose: str,
    session_summaries: list[dict],
    target_date,
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

        # 检测章节标题（兼容 ## xxx 和 ### xxx 格式）
        matched_section = None
        for kw, key in section_keywords.items():
            # 检查标题行是否包含当前 keyword（不区分大小写）
            if kw.lower() in stripped.lower():
                # 确认是标题行（包含 # 标记）
                if re.search(rf"#+\s*{re.escape(kw)}", stripped, re.I):
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
