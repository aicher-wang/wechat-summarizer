"""会话类型分类器 — 规则 + LLM 混合判断工作/非工作"""
import re
from typing import Literal

import config
import llm


ReportStyle = Literal["work", "newspaper"]

# 工作群高频特征词
WORK_INDICATORS = {
    "收到", "好的", "请查收", "已收到", "收到回复", "确认一下", "辛苦了",
    "领导", "老板", "同事", "客户", "会议室", "会议纪要", "待办", "todo",
    " deadline", "截止", "进度", "周报", "月报", "日报", "汇报", "方案",
    "合同", "报价", "预算", "审批", "通过", "驳回", "修改", "更新",
    "发布", "上线", "版本", "bug", "需求", "设计稿", "开发", "测试",
    "安排", "协调", "对接", "跟进", "推进", "落实", "执行",
    "各位", "大家", "@all", "@所有人", "收到请回复",
    "报表", "数据", "分析", "总结", "计划", "目标", "KPI", "OKR",
    "HR", "BP", "招聘", "面试", "入职", "离职", "转正", "晋升",
    "邮件", "微信", "电话", "会议", "日程", "邀约",
}

# 闲聊群高频特征词
NON_WORK_INDICATORS = {
    "哈哈", "哈哈哈", "笑死", "笑死我", "笑喷", "笑疯了",
    "吃瓜", "八卦", "吐槽", "无语", "绝了", "厉害", "牛", "顶",
    "卧槽", "我靠", "卧槽了", "妈呀", "天哪",
    "救命", "SOS", "救命啊", "帮帮我",
    "好饿", "好累", "好困", "好无聊", "烦", "累死了",
    "去哪", "干嘛呢", "在吗", "约吗", "走起", "集合",
    "推荐", "求推荐", "安利好物", "种草", "拔草",
    "打卡", "晒图", "自拍", "照片", "好看", "帅", "美",
    "回家", "出门", "路上", "堵车", "地铁", "公交",
    "早安", "晚安", "午安", "吃了吗", "睡了吗",
    "电视剧", "电影", "综艺", "综艺", "游戏", "追星",
    "考研", "考公", "上岸", "学霸", "期末",
    "减肥", "健身", "跑步", "瑜伽", "养生",
    "今天", "明天", "周末", "放假", "开学", "暑假",
    "奶茶", "咖啡", "火锅", "烧烤", "外卖", "餐厅",
}

# 工作群名称特征
WORK_NAME_PATTERNS = [
    r"工作", r"项目", r"业务", r"客户", r"技术", r"研发", r"测试",
    r"运营", r"市场", r"销售", r"商务", r"财务", r"法务",
    r"HR[ ·]?", r"招聘", r"面试", r"培训", r"考核",
    r"会议", r"周会", r"例会", r"日报", r"周报", r"月报",
    r"项目组", r"工作组", r"沟通群", r"交流群", r"对接群",
    r"部门", r"团队", r"小组", r"汇报",
]

# 闲聊群名称特征
NON_WORK_NAME_PATTERNS = [
    r"家人", r"家庭", r"亲戚", r"老乡", r"同学", r"校友",
    r"朋友", r"闺蜜", r"兄弟", r"损友", r"基友",
    r"吃喝", r"美食", r"旅游", r"旅行", r"出游",
    r"八卦", r"吃瓜", r"闲聊", r"吹水", r"摸鱼",
    r"业主", r"小区", r"家长", r"班级", r"学校",
    r"游戏", r"电竞", r"追星", r"影视", r"音乐",
    r"健身", r"跑步", r"减肥", r"养生", r"情感",
    r"育儿", r"宝妈", r"奶爸", r"亲子",
]


def _rule_based_classify(chat_name: str, messages_text: str, keywords: str) -> dict:
    """
    基于规则的快速预判，返回风格和置信度。
    """
    work_score = 0
    non_work_score = 0
    reasons = []

    # 1. 分析群聊名称
    name_is_work = any(re.search(p, chat_name, re.IGNORECASE) for p in WORK_NAME_PATTERNS)
    name_is_non_work = any(re.search(p, chat_name, re.IGNORECASE) for p in NON_WORK_NAME_PATTERNS)

    if name_is_work:
        work_score += 3
        reasons.append("群名含工作相关词汇")
    if name_is_non_work:
        non_work_score += 3
        reasons.append("群名含闲聊相关词汇")

    # 2. 分析消息内容
    text_lower = messages_text.lower()

    # 工作词计数
    for word in WORK_INDICATORS:
        if word.lower() in text_lower:
            work_score += 1

    # 闲聊词计数（权重更高，因为更具有区分度）
    for word in NON_WORK_INDICATORS:
        if word.lower() in text_lower:
            non_work_score += 1.5

    # 3. 分析关键词
    if keywords:
        kw_lower = keywords.lower()
        for word in WORK_INDICATORS:
            if word.lower() in kw_lower:
                work_score += 0.5
        for word in NON_WORK_INDICATORS:
            if word.lower() in kw_lower:
                non_work_score += 0.5

    # 4. 特殊模式检测
    # 工作群常见模式
    if re.search(r"收到请回复|@all|@所有人", text_lower):
        work_score += 2
    if re.search(r"^\d+[:-]\d+\s*【|^\d+[:-]\d+\s*会议", text_lower, re.MULTILINE):
        work_score += 1

    # 闲聊群常见模式
    if re.search(r"哈哈+", text_lower) or re.search(r"笑死", text_lower):
        non_work_score += 2
    if re.search(r"吃瓜|八卦", text_lower):
        non_work_score += 2

    # 5. 判断阈值
    # 强信号：规则得分差值 >= 3 则直接确定
    score_diff = work_score - non_work_score

    if score_diff >= 3:
        return {
            "style": "work",
            "confidence": min(0.9, 0.5 + score_diff * 0.1),
            "reasoning": f"规则判断：{reasons[0] if reasons else '工作特征明显'}" if reasons else "规则判断：工作特征明显",
            "rule_based": True,
        }
    elif non_work_score - work_score >= 3:
        return {
            "style": "newspaper",
            "confidence": min(0.9, 0.5 + (non_work_score - work_score) * 0.1),
            "reasoning": f"规则判断：{reasons[0] if reasons else '闲聊特征明显'}" if reasons else "规则判断：闲聊特征明显",
            "rule_based": True,
        }

    # 边界情况：交给 LLM
    return {
        "style": None,  # 无法确定
        "confidence": 0.0,
        "reasoning": f"规则得分工作{work_score} vs 闲聊{non_work_score}，需LLM判断",
        "rule_based": False,
        "work_score": work_score,
        "non_work_score": non_work_score,
    }


def classify_session(
    chat_name: str,
    messages_preview: str,
    keywords: str,
    metadata: dict = None,
) -> dict:
    """
    混合判断会话类型风格：规则预判 + LLM 辅助。

    1. 先用规则快速预判（高效、精准）
    2. 规则不确定时，再用 LLM 判断
    3. 综合两者结果

    返回：
        {
            "style": "work" 或 "newspaper",
            "confidence": 0.0 ~ 1.0,
            "reasoning": str,  # 判断理由
        }
    """
    metadata = metadata or {}
    msg_count = metadata.get("msg_count", 0)

    # 消息预览截断
    preview = (messages_preview or "")[:500].strip()
    if not preview:
        preview = "（无可用消息内容）"

    # Step 1: 规则预判
    rule_result = _rule_based_classify(chat_name, messages_preview, keywords)

    if rule_result["style"] and rule_result["rule_based"]:
        # 规则已能确定，直接返回
        return {
            "style": rule_result["style"],
            "confidence": rule_result["confidence"],
            "reasoning": rule_result["reasoning"],
            "raw_response": f"[规则] {rule_result['reasoning']}",
        }

    # Step 2: LLM 辅助判断
    prompt = f"""你是一个聊天记录类型判断助手。请根据以下信息，判断这个微信会话更接近"工作相关"还是"非工作相关"。

【会话名称】：{chat_name}
【消息预览（前500字）】：
{preview}

【高频关键词】：{keywords}
【消息数量】：{msg_count} 条

【辅助参考】（规则预判得分，仅供参考）：
- 工作特征得分：{rule_result.get('work_score', 0)}
- 闲聊特征得分：{rule_result.get('non_work_score', 0)}

【判断标准】：
- 工作相关：讨论项目、业务、客户、会议、任务、决策、工作安排、合同、报价等，有明确的汇报线和职责分工
- 非工作相关：家人日常、朋友闲聊、兴趣话题、聚会、美食、旅行、八卦、同学群、兴趣群等
- 重要：即使群名或参与者头衔看似"工作"（如HR、BP），也要看实际聊天内容是否在聊工作，还是在闲聊吃瓜
- 边界情况：优先看消息内容本身的语气和话题，而非仅凭群名或头衔判断

【输出格式】：
先给出你的判断理由（1-2句话），然后明确输出分类结果：
WORK：如果高度确信是工作相关
NEWSPAPER：如果高度确信是非工作相关

请直接输出判断理由和结果。"""

    try:
        result_text = llm.complete(prompt, max_tokens=200)
    except Exception as e:
        # LLM 失败时用规则得分决断
        if rule_result.get('work_score', 0) >= rule_result.get('non_work_score', 0):
            return {
                "style": "work",
                "confidence": 0.3,
                "reasoning": f"LLM失败，规则判断：工作特征{rule_result.get('work_score', 0)} vs 闲聊{rule_result.get('non_work_score', 0)}",
                "raw_response": f"[规则 fallback] {e}",
            }
        else:
            return {
                "style": "newspaper",
                "confidence": 0.3,
                "reasoning": f"LLM失败，规则判断：闲聊特征更强",
                "raw_response": f"[规则 fallback] {e}",
            }

    result_text = result_text.strip()

    # 解析 LLM 结果
    if "WORK" in result_text.upper() and "NEWSPAPER" not in result_text.upper():
        llm_style: ReportStyle = "work"
    elif "NEWSPAPER" in result_text.upper():
        llm_style = "newspaper"
    else:
        # LLM 模糊时用规则
        llm_style = "newspaper"  # 默认娱乐

    # 提取推理
    lines = result_text.split("\n")
    reasoning = lines[0].strip() if lines else "无法提取判断理由"

    return {
        "style": llm_style,
        "confidence": 0.7,
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
