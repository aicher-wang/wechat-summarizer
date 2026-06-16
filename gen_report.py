"""针对单个群生成完整报纸风格报告（含7大统计模块）"""
import sys
import re
import json
import subprocess
sys.path.insert(0, '.')

import accounts
import collector
import stats
import summarizer
import classifier
import report_renderer
from datetime import date

ACCOUNT_ID = "wx_93c00354"
USERNAME = "19439331521@chatroom"
TARGET_DATE = date(2026, 6, 15)

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
    if result["ok"]:
        data_list = result["data"]
        if isinstance(data_list, list) and data_list:
            MY_DISPLAY_NAME = data_list[0].get("nick_name", "我")
            if not MY_DISPLAY_NAME:
                MY_DISPLAY_NAME = data_list[0].get("remark", "我")
except Exception:
    pass
print(f"    当前用户: {MY_DISPLAY_NAME} ({MY_WXID})")

print("[1/5] 采集消息...")
data = collector.collect_session_data(ACCOUNT_ID, USERNAME, date_filter=TARGET_DATE)
raw_messages = data.get("raw_messages", [])
messages_text = data["messages_text"]
metadata = data["metadata"]
chat_name = data["chat_name"]
print(f"    采集到 {len(raw_messages)} 条消息")

print("[2/5] LLM 判断会话风格...")
# 用 LLM 分类器判断工作/非工作
classification_result = classifier.classify_session(
    chat_name=chat_name,
    messages_preview=messages_text[:500],
    keywords=metadata.get("keywords", ""),
    metadata=metadata,
)
style = classification_result["style"]
reasoning = classification_result["reasoning"]
print(f"    风格: {'[娱乐报纸]' if style == 'newspaper' else '[工作报告]'}")
print(f"    理由: {reasoning}")

print("[3/5] 生成结构化摘要...")
summary = summarizer.summarize_session(
    chat_name=chat_name,
    chat_type="群聊",
    messages_text=messages_text,
    metadata=metadata,
    time_range=TARGET_DATE.strftime("%Y-%m-%d"),
)
# 打印摘要内容前500字用于调试
print(f"    摘要（前500字）: {summary[:500]}")
print(f"    摘要生成完成")

print("[4/5] 计算统计...")
session_stats = stats.compute_all_stats(raw_messages, my_wxid=MY_WXID, my_display_name=MY_DISPLAY_NAME)
print(f"    发言: {session_stats['speaker_stats']['total_messages']}条 / {session_stats['speaker_stats']['total_senders']}人")
print(f"    活跃时段: {session_stats['activity_pulse']['peak_hour']}点")

print("[5/5] 渲染报告...")
session_summaries = [{
    "chat_name": chat_name,
    "chat_type": "群聊",
    "summary": summary,
    "metadata": metadata,
    "session_stats": session_stats,
}]

classification = {
    "global_style": style,
    "work_sessions": 1 if style == "work" else 0,
    "non_work_sessions": 1 if style == "newspaper" else 0,
    "session_styles": [style],
}

# 根据分类选择渲染器
if style == "work":
    report = report_renderer.render_work_report(
        account_purpose="主号",
        session_summaries=session_summaries,
        target_date=TARGET_DATE,
        classification=classification,
        my_display_name=MY_DISPLAY_NAME,
    )
    fmt_label = "工作报告"
else:
    report = report_renderer.render_newspaper_report_cards(
        account_purpose="主号",
        session_summaries=session_summaries,
        target_date=TARGET_DATE,
        classification=classification,
        my_display_name=MY_DISPLAY_NAME,
    )
    fmt_label = "娱乐报纸"

# 保存 HTML
html_content = f"""<!DOCTYPE html>
<html lang='zh-CN'>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<title>{chat_name} 日报 {TARGET_DATE}</title>
{report}
</body>
</html>"""

html_path = "C:/Users/tengxiao.wang/Desktop/汤臣一品业主群_日报_2026-06-15.html"
with open(html_path, "w", encoding="utf-8") as f:
    f.write(html_content)
print(f"\nHTML 已保存: {html_path}")
print(f"格式: {fmt_label}，字符数: {len(report)}")
