"""生成"我爱一条柴"群的一周日报（2026-06-09 ~ 2026-06-15）"""
import sys, re, json
from datetime import date, timedelta
sys.path.insert(0, '.')

import accounts, collector, stats, summarizer, classifier, report_renderer

ACCOUNT_ID = "wx_93c00354"
USERNAME = "22557542875@chatroom"
TARGET_DATES = [date(2026, 6, 9) + timedelta(days=i) for i in range(7)]

# ---- 获取当前用户信息 ----
account = accounts.get_account(ACCOUNT_ID)
db_dir = account["db_dir"]
wxid_match = re.search(r'(wxid_[a-zA-Z0-9]+)', db_dir)
MY_WXID = wxid_match.group(1) if wxid_match else ""

MY_DISPLAY_NAME = "我"
try:
    result = collector.run_wechat_cli(
        account["command_prefix"],
        ["contacts", "--query", MY_WXID, "--format", "json"]
    )
    if result["ok"] and result["data"]:
        MY_DISPLAY_NAME = result["data"][0].get("nick_name", "我") or result["data"][0].get("remark", "我")
except:
    pass
print(f"当前用户: {MY_DISPLAY_NAME} ({MY_WXID})")

# ---- 逐日采集汇总 ----
all_raw_messages = []
all_messages_text = []
session_summaries = []
total_msgs = 0

for d in TARGET_DATES:
    print(f"[{d}] 采集...")
    data = collector.collect_session_data(ACCOUNT_ID, USERNAME, date_filter=d)
    raw_msgs = data.get("raw_messages", [])
    msgs_text = data["messages_text"]
    metadata = data["metadata"]
    chat_name = data["chat_name"]
    n = len(raw_msgs)
    total_msgs += n
    print(f"    {n} 条消息")
    if n == 0:
        continue
    all_raw_messages.extend(raw_msgs)
    all_messages_text.append(msgs_text)

# ---- 整体风格判断 ----
combined_text = "\n".join(all_messages_text)
print(f"\n[共 {total_msgs} 条消息] LLM 判断风格...")
classification_result = classifier.classify_session(
    chat_name=chat_name,
    messages_preview=combined_text[:800],
    keywords="",
    metadata={},
)
style = classification_result["style"]
print(f"    风格: {'[娱乐报纸]' if style == 'newspaper' else '[工作报告]'}")

# ---- 按日生成摘要 ----
print("\n生成每日摘要...")
daily_summaries = []
for d in TARGET_DATES:
    data = collector.collect_session_data(ACCOUNT_ID, USERNAME, date_filter=d)
    msgs_text = data["messages_text"]
    metadata = data["metadata"]
    n = len(data.get("raw_messages", []))
    if n == 0:
        daily_summaries.append(None)
        continue
    s = summarizer.summarize_session(
        chat_name=chat_name,
        chat_type="群聊",
        messages_text=msgs_text,
        metadata=metadata,
        time_range=d.strftime("%Y-%m-%d"),
    )
    daily_summaries.append(s)
    print(f"    {d}: {len(s)} 字")

# ---- 整体统计 ----
print("\n计算统计...")
full_stats = stats.compute_all_stats(all_raw_messages, my_wxid=MY_WXID, my_display_name=MY_DISPLAY_NAME)
print(f"    总发言: {total_msgs}条 / {full_stats['speaker_stats']['total_senders']}人")
print(f"    活跃时段: {full_stats['activity_pulse']['peak_hour']}点")

# ---- 周报摘要 ----
print("\n生成周报摘要...")
week_summary = summarizer.summarize_session(
    chat_name=chat_name,
    chat_type="群聊",
    messages_text=combined_text,
    metadata={},
    time_range=f"2026-06-09 至 2026-06-15",
)

# ---- 渲染报告 ----
print("\n渲染报告...")

# 构建 session_summaries（含每日摘要）
week_session_stats = full_stats
week_md = week_summary

# 按日统计
daily_counts = []
for d in TARGET_DATES:
    data = collector.collect_session_data(ACCOUNT_ID, USERNAME, date_filter=d)
    daily_counts.append(len(data.get("raw_messages", [])))

# 生成每日摘要卡片内容
daily_cards_html = ""
for d, s, cnt in zip(TARGET_DATES, daily_summaries, daily_counts):
    if s is None or cnt == 0:
        continue
    # 替换 me
    import re as re_mod
    s = re_mod.sub(r'\*\*me\*\*', f'**{MY_DISPLAY_NAME}**', s)
    s = re_mod.sub(r'\[me\]', f'[{MY_DISPLAY_NAME}]', s)
    s = re_mod.sub(r'\bme\b', MY_DISPLAY_NAME, s)
    # 解析摘要
    parsed = report_renderer._parse_summary_to_dict(s)
    sections = report_renderer._render_summary_sections(parsed)
    daily_cards_html += f"""
<div class="day-card">
  <div class="day-card-header">{d.strftime('%m月%d日')} <span class="day-count">{cnt}条</span></div>
  <div class="day-overview">{report_renderer._h(parsed.get('overview', ''))}</div>
  {sections}
</div>"""

# 整体卡片
import re as re_mod
week_md_clean = re_mod.sub(r'\*\*me\*\*', f'**{MY_DISPLAY_NAME}**', week_md)
week_md_clean = re_mod.sub(r'\[me\]', f'[{MY_DISPLAY_NAME}]', week_md_clean)
week_md_clean = re_mod.sub(r'\bme\b', MY_DISPLAY_NAME, week_md_clean)
parsed_week = report_renderer._parse_summary_to_dict(week_md_clean)
week_sections = report_renderer._render_summary_sections(parsed_week)

# 发言排行
top_speakers = full_stats['speaker_stats']['ranked'][:7]
speaker_bars = ""
for name, count in top_speakers:
    max_count = top_speakers[0][1]
    pct = int(count / max_count * 100)
    medal = "🥇" if name == top_speakers[0][0] else ("🥈" if name == top_speakers[1][0] else "🥉") if top_speakers.index((name, count)) < 3 else ""
    speaker_bars += f"""<div class="speaker-bar">
  <span class="medal">{medal}</span>
  <span class="name">{report_renderer._h(name)}</span>
  <div class="bar-wrap"><div class="bar-fill" style="width:{pct}%"></div></div>
  <span class="count">{count}条</span>
</div>"""

# 活跃时段柱状图
hours = full_stats['activity_pulse']['hours']
max_hour_count = max(hours.values()) if hours else 1
hour_bars = ""
for h in sorted(hours.keys()):
    c = hours[h]
    pct = int(c / max_hour_count * 100)
    hour_bars += f"""<div class="hour-bar-wrap">
  <div class="hour-label">{h}点</div>
  <div class="hour-bar"><div class="hour-fill" style="height:{pct}%"></div></div>
  <div class="hour-count">{c}</div>
</div>"""

# Emoji 统计
emoji_data = full_stats.get('emoji_stats', {})
emoji_top = emoji_data.get('top', [])[:6]
emoji_chips = "".join(f"<span class='emoji-chip'>{e}×{c}</span>" for e, c in emoji_top)

# 热词
hot_words = full_stats.get('hot_words', {}).get('words', [])[:10]
hot_word_tags = "".join(f"<span class='word-tag'>{report_renderer._h(w)}</span>" for w, c in hot_words)

html_content = f"""<!DOCTYPE html>
<html lang='zh-CN'>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<title>{chat_name} 周报 2026-06-09~15</title>
<style>
:root {{
  --primary: #4f46e5;
  --primary-light: #818cf8;
  --accent: #f59e0b;
  --accent-light: #fcd34d;
  --bg-page: #f0f2f5;
  --bg-card: #ffffff;
  --text-primary: #1f2937;
  --text-secondary: #6b7280;
  --border: #e5e7eb;
  --shadow: 0 4px 6px -1px rgba(0,0,0,0.07), 0 2px 4px -1px rgba(0,0,0,0.04);
  --radius: 16px;
  --radius-sm: 10px;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: -apple-system, "Microsoft YaHei", "PingFang SC", sans-serif; background: var(--bg-page); color: var(--text-primary); line-height: 1.6; }}
.report {{ max-width: 900px; margin: 30px auto; padding: 0 16px 40px; }}
.card {{ background: var(--bg-card); border-radius: var(--radius); box-shadow: var(--shadow); overflow: hidden; margin-bottom: 20px; }}

/* 报头 */
.masthead {{ background: linear-gradient(135deg, #1e3a5f 0%, #4f46e5 50%, #7c3aed 100%); color: white; padding: 36px 32px; text-align: center; border-radius: var(--radius) !important; margin-bottom: 24px; }}
.masthead-title {{ font-size: 2em; font-weight: 800; margin-bottom: 8px; }}
.masthead-sub {{ font-size: 0.95em; opacity: 0.85; letter-spacing: 0.1em; }}
.masthead-badge {{ display: inline-block; background: rgba(255,255,255,0.15); border: 1px solid rgba(255,255,255,0.3); border-radius: 20px; padding: 4px 16px; font-size: 0.8em; margin-top: 12px; }}

/* 卡片 */
.session-card {{ padding: 0; }}
.card-header {{ background: linear-gradient(90deg, var(--primary) 0%, var(--primary-light) 100%); color: white; padding: 16px 24px; font-size: 1.1em; font-weight: 700; }}
.card-body {{ padding: 20px 24px; }}

/* 头条块 */
.headline-block {{ background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%); border-left: 4px solid var(--accent); border-radius: var(--radius-sm); padding: 14px 18px; margin-bottom: 16px; }}
.headline {{ font-size: 1.05em; font-weight: 700; color: #92400e; margin-bottom: 4px; }}
.subheadline {{ font-size: 0.88em; color: #b45309; }}

/* 统计网格 */
.stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; margin-bottom: 16px; }}
.stat-card {{ background: #f9fafb; border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 14px; }}
.stat-title {{ font-size: 0.8em; font-weight: 700; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px; }}

/* 发言排行 */
.speaker-bar {{ display: flex; align-items: center; gap: 8px; margin-bottom: 5px; }}
.speaker-bar .medal {{ font-size: 0.9em; }}
.speaker-bar .name {{ font-size: 0.85em; font-weight: 600; min-width: 70px; }}
.speaker-bar .bar-wrap {{ flex: 1; height: 8px; background: var(--border); border-radius: 4px; overflow: hidden; }}
.speaker-bar .bar-fill {{ height: 100%; background: var(--primary); border-radius: 4px; }}
.speaker-bar .count {{ font-size: 0.8em; color: var(--text-secondary); min-width: 30px; text-align: right; }}

/* 活跃时段 */
.hour-bars {{ display: flex; align-items: flex-end; gap: 4px; height: 60px; }}
.hour-bar-wrap {{ flex: 1; display: flex; flex-direction: column; align-items: center; gap: 2px; }}
.hour-bar {{ width: 100%; height: 45px; background: var(--border); border-radius: 3px; display: flex; align-items: flex-end; }}
.hour-fill {{ width: 100%; background: var(--primary); border-radius: 3px; }}
.hour-label {{ font-size: 0.65em; color: var(--text-secondary); }}
.hour-count {{ font-size: 0.65em; color: var(--text-secondary); }}

/* Emoji */
.emoji-row {{ display: flex; flex-wrap: wrap; gap: 6px; }}
.emoji-chip {{ background: #ede9fe; color: #5b21b6; border-radius: 12px; padding: 2px 8px; font-size: 0.8em; }}

/* 热词 */
.word-tag {{ background: #dbeafe; color: #1e40af; border-radius: 12px; padding: 3px 10px; font-size: 0.8em; margin: 2px; display: inline-block; }}

/* 每日卡片 */
.day-card {{ background: #f9fafb; border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 14px 18px; margin-bottom: 12px; }}
.day-card-header {{ font-weight: 700; color: var(--primary); margin-bottom: 6px; font-size: 0.95em; }}
.day-count {{ background: var(--primary); color: white; border-radius: 10px; padding: 1px 8px; font-size: 0.75em; margin-left: 8px; }}
.day-overview {{ font-size: 0.88em; color: var(--text-secondary); margin-bottom: 8px; }}

/* 摘要章节 */
.summary-section {{ margin-bottom: 12px; }}
.summary-section-title {{ font-size: 0.85em; font-weight: 700; color: var(--primary); margin-bottom: 4px; }}
.summary-section ul {{ list-style: none; padding-left: 0; }}
.summary-section li {{ font-size: 0.85em; color: var(--text-secondary); padding: 2px 0; border-bottom: 1px solid var(--border); }}
.summary-section li:last-child {{ border-bottom: none; }}
.divider {{ border: none; border-top: 1px solid var(--border); margin: 12px 0; }}

/* 页脚 */
.footer-card {{ text-align: center; padding: 20px; color: var(--text-secondary); font-size: 0.8em; }}
.footer-card .footer-stats {{ display: flex; justify-content: center; gap: 24px; margin-bottom: 8px; }}
.footer-stats strong {{ color: var(--primary); }}
</style>
</head>
<body>
<div class="report">

<!-- 报头 -->
<div class="card masthead">
  <div class="masthead-title">🗞️ WEIXIN WEEKLY</div>
  <div class="masthead-sub">你的群聊小报 · 2026年6月9日~15日</div>
  <div class="masthead-badge">第 24期</div>
</div>

<!-- 整体概览卡片 -->
<div class="card session-card">
  <div class="card-header">📢 {report_renderer._h(chat_name)} · 本周汇总</div>
  <div class="card-body">
    <div class="headline-block">
      <div class="headline">📰 本周概览</div>
      <div class="subheadline">{report_renderer._h(parsed_week.get('overview', '本周群聊活跃'))}</div>
    </div>

    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-title">🏆 发言排行</div>
        <div class="stat-content">{speaker_bars}</div>
      </div>
      <div class="stat-card">
        <div class="stat-title">⏰ 活跃时段</div>
        <div class="stat-content">
          <div class="hour-bars">{hour_bars}</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-title">😀 Emoji 风云</div>
        <div class="stat-content"><div class="emoji-row">{emoji_chips}</div></div>
      </div>
      <div class="stat-card">
        <div class="stat-title">🔥 热词</div>
        <div class="stat-content">{hot_word_tags}</div>
      </div>
    </div>

    {week_sections}
  </div>
</div>

<!-- 每日明细 -->
<div class="card session-card">
  <div class="card-header">📅 每日明细</div>
  <div class="card-body">
    {daily_cards_html}
  </div>
</div>

<!-- 页脚 -->
<div class="card footer-card">
  <div class="footer-stats">
    <span>总消息 <strong>{total_msgs}</strong> 条</span>
    <span>参与人数 <strong>{full_stats['speaker_stats']['total_senders']}</strong> 人</span>
    <span>活跃天数 <strong>{sum(1 for c in daily_counts if c > 0)}</strong> 天</span>
  </div>
  <div>由 WeChat Summarizer 生成 · 2026-06-16</div>
</div>

</div>
</body>
</html>"""

html_path = "C:/Users/tengxiao.wang/Desktop/我爱一条柴_周报_2026-06-09~15.html"
with open(html_path, "w", encoding="utf-8") as f:
    f.write(html_content)
print(f"\nHTML 已保存: {html_path}")
print(f"字符数: {len(html_content)}")
