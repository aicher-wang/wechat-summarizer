"""会话统计数据提取 — 规则计算，不调 LLM"""
import re
from collections import Counter
from datetime import datetime
from typing import Any


# =============================================================================
# 通用消息解析器（同时支持结构化 dict 和预格式化字符串）
# =============================================================================

def _parse_message(msg) -> tuple[str, str, str]:
    """
    解析任意消息格式，返回 (sender, content, time_str)。
    支持：
      - 结构化 dict：msg.get("sender"), msg.get("content"), msg.get("time")
      - 预格式化字符串："[2026-06-15 13:42] sender: content" 或 "sender: content"
    """
    if isinstance(msg, str):
        # 预格式化字符串解析
        content = msg.strip()
        sender = ""
        time_str = ""
        # 格式: "[时间] sender: content" 或 "sender: content"
        m = re.match(r"\[([^\]]+)\]\s*([^:\s]+)\s*:\s*", content)
        if m:
            time_str = m.group(1)
            sender = m.group(2).strip()
            content = content[m.end():].strip()
        elif ": " in content:
            # Fallback: "sender: content"
            parts = content.split(": ", 1)
            sender = parts[0].strip()
            content = parts[1].strip() if len(parts) > 1 else ""
        return sender, content, time_str

    sender = str(msg.get("sender") or msg.get("from") or msg.get("nickname") or "")
    content = str(msg.get("content") or msg.get("text") or msg.get("message") or "")
    time_str = str(msg.get("time") or msg.get("datetime") or "")
    return sender, content, time_str

# =============================================================================
# 活跃脉搏（消息时间分布）
# =============================================================================

def compute_activity_pulse(messages: list) -> dict[str, Any]:
    """
    计算群活跃脉搏（消息时间分布）。
    返回每小时消息数量分布。
    """
    if not messages:
        return {"hours": {}, "peak_hour": None, "total": 0, "density": 0}

    hour_counter = Counter()
    total = 0

    for msg in messages:
        _, _, msg_time = _parse_message(msg)
        if msg_time:
            try:
                # 支持 "2026-06-15 13:42" 或 "2026-06-15T13:42" 格式
                dt = datetime.fromisoformat(msg_time.replace(" ", "T"))
                hour_counter[dt.hour] += 1
                total += 1
            except (ValueError, TypeError):
                pass

    if not hour_counter:
        return {"hours": {}, "peak_hour": None, "total": 0, "density": 0}

    peak_hour = hour_counter.most_common(1)[0][0] if hour_counter else None

    # 计算活跃度密度（每小时平均消息数）
    active_hours = len(hour_counter)
    density = round(total / active_hours, 1) if active_hours > 0 else 0

    return {
        "hours": dict(hour_counter),
        "peak_hour": peak_hour,
        "total": total,
        "active_hours": active_hours,
        "density": density,
    }


def format_activity_pulse(pulse: dict) -> str:
    """格式化为可视化的活跃脉搏条"""
    hours = pulse.get("hours", {})
    if not hours:
        return "无时间数据"

    total = pulse.get("total", 0)
    peak_hour = pulse.get("peak_hour", 0)
    density = pulse.get("density", 0)

    # 归一化到最大 10 格
    max_count = max(hours.values()) if hours else 1
    blocks = [f"{h:02d}时" for h in range(24)]
    bar = ""
    for h in range(24):
        count = hours.get(h, 0)
        bar_chars = min(10, round(count / max_count * 10)) if max_count > 0 else 0
        bar += "█" * bar_chars + "░" * (10 - bar_chars)
        bar += " "

    # 翻译时间
    peak_str = f"{peak_hour:02d}:00" if peak_hour is not None else "未知"

    return (
        f"📈 今日群活跃脉搏（共 {total} 条消息）\n"
        f"   ██ 最热时段：{peak_str}（密度 {density} 条/小时）\n"
        f"   时间分布：{bar}\n"
        f"   00  01  02  03  04  05  06  07  08  09  10  11\n"
        f"   12  13  14  15  16  17  18  19  20  21  22  23"
    )


# =============================================================================
# 发言排行榜
# =============================================================================

def compute_speaker_stats(messages: list, my_wxid: str = "", my_display_name: str = "我") -> dict[str, Any]:
    """
    计算发言统计。
    返回发言次数排行 + 最少发言。
    my_wxid / my_display_name: 用于将"me"替换为用户的真实昵称。
    """
    if not messages:
        return {"ranked": [], "top_speaker": None, "quietest": None, "total": 0}

    sender_counter = Counter()
    for msg in messages:
        sender, _, _ = _parse_message(msg)
        if sender and sender not in ("未知", "", "系统"):
            # 将"me"或自己的wxid替换为显示名
            if sender in ("me", my_wxid):
                sender = my_display_name
            sender_counter[sender] += 1

    if not sender_counter:
        return {"ranked": [], "top_speaker": None, "quietest": None, "total": 0}

    ranked = sender_counter.most_common()
    total_senders = len(ranked)
    total_messages = sum(sender_counter.values())

    return {
        "ranked": ranked,  # [(name, count), ...]
        "top_speaker": ranked[0] if ranked else None,
        "quietest": ranked[-1] if len(ranked) > 3 else None,
        "total_senders": total_senders,
        "total_messages": total_messages,
    }


def format_speaker_stats(stats: dict) -> str:
    """格式化发言排行榜"""
    ranked = stats.get("ranked", [])
    if not ranked:
        return "无发言数据"

    lines = ["📊 今日发言排行榜："]
    medals = ["🥇", "🥈", "🥉"]

    for i, (name, count) in enumerate(ranked[:5]):
        medal = medals[i] if i < 3 else f"  {i+1}."
        # 名字太长截断
        display_name = name[:8] + ".." if len(name) > 8 else name
        bar_len = min(10, count)
        bar = "█" * bar_len + "░" * (10 - bar_len)
        lines.append(f"   {medal} {display_name:<10} {bar} {count}条")

    if len(ranked) > 5:
        lines.append(f"   ...  共 {stats['total_senders']} 人发言")

    # 潜水达人
    quietest = stats.get("quietest")
    if quietest and quietest[1] == 1:
        name = quietest[0]
        display_name = name[:8] + ".." if len(name) > 8 else name
        lines.append(f"   🏊 潜水达人：{display_name}（仅 1 条）")

    return "\n".join(lines)


# =============================================================================
# 今日热词
# =============================================================================

def compute_hot_words(messages: list, top_n: int = 10) -> dict[str, Any]:
    """提取高频词"""
    all_text_parts = []
    for msg in messages:
        _, content, _ = _parse_message(msg)
        if content:
            all_text_parts.append(content)

    all_text = " ".join(all_text_parts)
    words = re.findall(r"[\u4e00-\u9fff]{2,}|[\w]{3,}", all_text.lower())

    # 停用词
    stopwords = {
        "的", "了", "是", "在", "我", "有", "和", "就", "不", "人", "都", "一",
        "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着",
        "没有", "看", "好", "自己", "这", "什么", "那", "他", "她", "它",
        "我们", "你们", "他们", "这个", "那个", "怎么", "为什么", "哪个",
        "这些", "那些", "可以", "已经", "现在", "时候", "这样", "那样",
        "一直", "一下", "一点", "但是", "因为", "所以", "如果", "虽然",
        "还是", "或者", "而且", "然后", "其实", "他们", "她们", "只是",
        "真的", "可能", "应该", "需要", "知道", "觉得", "希望", "还有",
        "什么", "怎么", "多少", "这里", "那里", "这么", "那么",
        "哈哈", "哈哈哈", "哈哈哈哈", "哈哈哈哈哈哈",
    }

    filtered = [w for w in words if w.lower() not in stopwords and len(w) >= 2]
    counter = Counter(filtered)
    top = counter.most_common(top_n)

    # 检测"哈哈哈"类
    laugh_count = sum(1 for w in words if w in {"哈哈", "哈哈哈", "哈哈哈哈", "哈哈哈哈哈哈"})
    question_count = all_text.count("？") + all_text.count("?")

    return {
        "words": top,  # [(word, count), ...]
        "laugh_count": laugh_count,
        "question_count": question_count,
        "total": len(filtered),
    }


def format_hot_words(word_stats: dict) -> str:
    """格式化热词"""
    words = word_stats.get("words", [])
    if not words:
        return "📊 今日热词：无数据"

    laugh = word_stats.get("laugh_count", 0)
    question = word_stats.get("question_count", 0)

    lines = ["📊 今日热词 TOP10："]
    for word, count in words[:10]:
        bar_len = min(8, count)
        bar = "█" * bar_len
        lines.append(f"   {word:<8} {bar} {count}")

    extras = []
    if laugh >= 5:
        extras.append(f"😂 '哈哈哈'系出现 {laugh} 次")
    if question >= 3:
        extras.append(f"❓ 今日共提 {question} 个问题")

    if extras:
        lines.append("   " + " | ".join(extras))

    return "\n".join(lines)


# =============================================================================
# Emoji 风云榜
# =============================================================================

def compute_emoji_stats(messages: list) -> dict[str, Any]:
    """统计 Emoji 使用"""
    all_text_parts = []
    for msg in messages:
        _, content, _ = _parse_message(msg)
        if content:
            all_text_parts.append(content)

    all_text = " ".join(all_text_parts)

    # 匹配常见 emoji（Unicode 范围）
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags
        "\U00002702-\U000027B0"  # dingbats
        "\U000024C2-\U0001F251"
        "\U0001F900-\U0001F9FF"  # supplemental symbols
        "\U0001FA00-\U0001FA6F"  # chess symbols
        "\U0001FA70-\U0001FAFF"  # symbols and pictographs extended
        "\U00002600-\U000026FF"  # misc symbols
        "]+"
    )

    emojis = emoji_pattern.findall(all_text)
    counter = Counter(emojis)
    top = counter.most_common(10)
    total = sum(counter.values())

    return {
        "top": top,  # [(emoji, count), ...]
        "total": total,
        "unique_types": len(counter),
    }


def format_emoji_stats(emoji_stats: dict) -> str:
    """格式化 Emoji 统计"""
    top = emoji_stats.get("top", [])
    total = emoji_stats.get("total", 0)
    unique = emoji_stats.get("unique_types", 0)

    if not top:
        return ""

    emoji_bar = " ".join(f"{e}×{c}" for e, c in top[:7])
    return f"😀 Emoji 风云榜：共 {total} 个（{unique} 种），{emoji_bar}"


# =============================================================================
# 今日图片/视频/文件
# =============================================================================

def compute_media_stats(messages: list) -> dict[str, Any]:
    """统计图片、视频、文件"""
    images = 0
    videos = 0
    files = 0
    voice = 0
    locations = 0
    links = 0

    # 微信消息类型的简单判断（通过内容关键词）
    for msg in messages:
        _, content, _ = _parse_message(msg)
        msg_type = ""
        if isinstance(msg, dict):
            msg_type = str(msg.get("msg_type") or msg.get("type") or "").lower()

        if "图片" in content or msg_type in ("3", "image", "img"):
            images += 1
        elif "视频" in content or msg_type in ("43", "video"):
            videos += 1
        elif "文件" in content or msg_type in ("6", "file", "document"):
            files += 1
        elif "语音" in content or msg_type in ("34", "voice"):
            voice += 1
        elif "位置" in content or msg_type in ("location",):
            locations += 1
        elif content.startswith("http") or "url" in msg_type:
            links += 1

    total = images + videos + files + voice + locations

    return {
        "images": images,
        "videos": videos,
        "files": files,
        "voice": voice,
        "locations": locations,
        "links": links,
        "total": total,
    }


def format_media_stats(media_stats: dict) -> str:
    """格式化媒体统计"""
    total = media_stats.get("total", 0)
    if total == 0:
        return ""

    parts = []
    if media_stats.get("images", 0) > 0:
        parts.append(f"📷 图片 {media_stats['images']}张")
    if media_stats.get("videos", 0) > 0:
        parts.append(f"🎬 视频 {media_stats['videos']}个")
    if media_stats.get("files", 0) > 0:
        parts.append(f"📎 文件 {media_stats['files']}份")
    if media_stats.get("voice", 0) > 0:
        parts.append(f"🎤 语音 {media_stats['voice']}条")
    if media_stats.get("locations", 0) > 0:
        parts.append(f"📍 位置 {media_stats['locations']}个")
    if media_stats.get("links", 0) > 0:
        parts.append(f"🔗 链接 {media_stats['links']}条")

    if not parts:
        return ""
    return "📦 今日媒体产出：" + " / ".join(parts)


# =============================================================================
# 链接雷达
# =============================================================================

def compute_link_stats(messages: list) -> dict[str, Any]:
    """统计链接类型"""
    all_text_parts = []
    for msg in messages:
        _, content, _ = _parse_message(msg)
        if content:
            all_text_parts.append(content)

    all_text = " ".join(all_text_parts)

    # 提取 URL
    url_pattern = re.compile(
        r"https?://[^\s<>\[\]\"\'（）\(\)《》【】，。、！!?？]+"
    )
    urls = url_pattern.findall(all_text)

    categories = Counter()
    for url in urls:
        url_lower = url.lower()
        if "mp.weixin.qq.com" in url_lower or "weixin.sogou.com" in url_lower:
            categories["公众号文章"] += 1
        elif "xiaohongshu.com" in url_lower or "redoc" in url_lower:
            categories["小红书"] += 1
        elif "douyin.com" in url_lower or "v.douyin" in url_lower:
            categories["抖音/视频"] += 1
        elif "b23.tv" in url_lower or "bilibili.com" in url_lower:
            categories["B站视频"] += 1
        elif "ele.me" in url_lower or "meituan" in url_lower or "大众点评" in url_lower:
            categories["美食/外卖"] += 1
        elif "maps.qq.com" in url_lower or "map" in url_lower or "ditu" in url_lower:
            categories["地图/位置"] += 1
        elif "github.com" in url_lower:
            categories["GitHub"] += 1
        elif any(k in url_lower for k in ["pdf", "doc", "docx", "xlsx", "pptx"]):
            categories["文档"] += 1
        elif "juejin" in url_lower:
            categories["掘金"] += 1
        else:
            categories["其他链接"] += 1

    return {
        "total": len(urls),
        "categories": dict(categories.most_common()),
    }


def format_link_stats(link_stats: dict) -> str:
    """格式化链接统计"""
    total = link_stats.get("total", 0)
    if total == 0:
        return ""

    cats = link_stats.get("categories", {})
    if not cats:
        return f"🔗 共分享 {total} 个链接"

    parts = [f"{k} {v}个" for k, v in list(cats.items())[:5]]
    return f"🔗 链接雷达（共 {total} 个）：" + " / ".join(parts)


# =============================================================================
# 群话题天气
# =============================================================================

def compute_group_weather(messages: list, stats: dict) -> str:
    """根据统计数据生成群话题天气描述"""
    pulse = compute_activity_pulse(messages)
    speakers = compute_speaker_stats(messages)
    hot_words = compute_hot_words(messages, top_n=5)
    media = compute_media_stats(messages)

    total = pulse.get("total", 0)
    density = pulse.get("density", 0)
    ranked = speakers.get("ranked", [])
    top_speaker_count = ranked[0][1] if ranked else 0
    laugh_count = hot_words.get("laugh_count", 0)
    question_count = hot_words.get("question_count", 0)

    # 判断天气
    # 活跃度
    if density >= 10:
        activity = "🔥 极度活跃"
    elif density >= 5:
        activity = "⛈️ 相当热闹"
    elif density >= 2:
        activity = "🌤️ 正常活跃"
    elif density >= 1:
        activity = "☁️ 略显平静"
    else:
        activity = "🌙 异常安静"

    # 判断主导情绪（通过关键词）
    keywords = [w for w, _ in hot_words.get("words", [])]

    if laugh_count >= total * 0.15:
        emotion = "情绪：😂 笑声不断"
    elif question_count >= 5:
        emotion = "情绪：🤔 问题很多"
    elif any(k in keywords for k in ["谢谢", "感谢", "棒", "厉害", "赞"]):
        emotion = "情绪：🥰 氛围融洽"
    elif any(k in keywords for k in ["加班", "赶", "急", "催", " deadline"]):
        emotion = "情绪：😰 有点紧张"
    else:
        emotion = "情绪：💬 正常交流"

    # 判断是否一边倒
    distribution = "📊 暂无数据"
    if ranked:
        top_ratio = top_speaker_count / total if total > 0 else 0
        if top_ratio > 0.4:
            distribution = f"📢 {ranked[0][0]} 发言占比 {top_ratio:.0%}，较一边倒"
        elif len(ranked) > 5:
            distribution = f"📊 {len(ranked)} 人参与，讨论均衡"
        else:
            distribution = f"📊 {len(ranked)} 人参与"

    weather_desc = f"{activity} | {emotion} | {distribution}"

    return weather_desc


# =============================================================================
# 统一汇总：一次调用计算所有统计
# =============================================================================

def compute_all_stats(messages: list, my_wxid: str = "", my_display_name: str = "我") -> dict[str, Any]:
    """
    对消息列表计算所有统计数据。
    用于填充报纸风格的各统计模块。
    my_wxid / my_display_name: 用于将"me"替换为用户的真实昵称。
    """
    pulse = compute_activity_pulse(messages)
    speakers = compute_speaker_stats(messages, my_wxid=my_wxid, my_display_name=my_display_name)
    hot_words = compute_hot_words(messages)
    emoji_stats = compute_emoji_stats(messages)
    media_stats = compute_media_stats(messages)
    link_stats = compute_link_stats(messages)
    group_weather = compute_group_weather(messages, {"pulse": pulse, "speakers": speakers})

    return {
        "activity_pulse": pulse,
        "speaker_stats": speakers,
        "hot_words": hot_words,
        "emoji_stats": emoji_stats,
        "media_stats": media_stats,
        "link_stats": link_stats,
        "group_weather": group_weather,
    }


def format_all_stats(stats: dict) -> list[str]:
    """
    将所有统计格式化为多行字符串列表，
    用于直接插入报纸报告的 sidebar。
    """
    lines = []
    w = stats.get("group_weather", "")
    if w:
        lines.append(w)

    p = stats.get("activity_pulse", {})
    if p.get("total", 0) > 0:
        peak = p.get("peak_hour")
        density = p.get("density", 0)
        peak_str = f"{peak:02d}:00" if peak is not None else "?"
        lines.append(f"⏰ 最热时段：{peak_str}（均 {density} 条/小时）")

    s = stats.get("speaker_stats", {})
    ranked = s.get("ranked", [])
    if ranked:
        top_name = ranked[0][0][:6]
        top_count = ranked[0][1]
        lines.append(f"🗣️ 话痨冠军：{top_name}（{top_count}条）")

    h = stats.get("hot_words", {})
    laugh = h.get("laugh_count", 0)
    question = h.get("question_count", 0)
    extras = []
    if laugh >= 5:
        extras.append(f"😂 哈哈哈×{laugh}")
    if question >= 3:
        extras.append(f"❓ 提问×{question}")
    if extras:
        lines.append("  " + " | ".join(extras))

    m = stats.get("media_stats", {})
    if m.get("total", 0) > 0:
        parts = []
        if m.get("images", 0) > 0:
            parts.append(f"📷{m['images']}")
        if m.get("videos", 0) > 0:
            parts.append(f"🎬{m['videos']}")
        if m.get("files", 0) > 0:
            parts.append(f"📎{m['files']}")
        if parts:
            lines.append("  " + " ".join(parts))

    l = stats.get("link_stats", {})
    if l.get("total", 0) > 0:
        lines.append(f"🔗 链接 {l['total']} 个")

    return lines
