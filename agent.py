"""
微信聊天记录总结器 — Agent 接口

供外部 AI Agent 以工具调用方式使用，不需要懂命令行。

使用方式（作为 Tool / Function Calling）：
    from agent import WechatSummarizerAgent
    agent = WechatSummarizerAgent()
    result = agent.run("总结今天的工作群")
    print(result)

或者直接调用各个工具方法：
    agent.list_accounts()
    agent.get_sessions(account_id="wx_xxxx")
    agent.summarize_session(account_id="wx_xxxx", username="xxx")
    agent.daily_report(account_id="wx_xxxx")
"""
import sys
from pathlib import Path
from datetime import date
from typing import Optional

# 确保项目根目录在 Python 路径
_PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_PROJECT_ROOT))

import config
import accounts
import collector
import summarizer
import exporter
import classifier
import report_renderer
import stats


class WechatSummarizerAgent:
    """
    微信聊天记录总结器 Agent。
    封装为可被外部 AI Agent 直接调用的工具接口。
    """

    def __init__(self, account_id: Optional[str] = None):
        """
        初始化 Agent。

        参数：
            account_id: 可选，指定默认账号。不指定则使用第一个已注册的账号。
        """
        self.account_id = account_id or self._get_default_account_id()

    def _get_default_account_id(self) -> Optional[str]:
        accts = accounts.list_accounts()
        if not accts:
            return None
        return accts[0].get("account_id")

    # =========================================================================
    # 基础工具
    # =========================================================================

    def list_accounts(self) -> dict:
        """列出所有已注册的账号"""
        accts = accounts.list_accounts()
        return {
            "ok": True,
            "accounts": [
                {
                    "account_id": a["account_id"],
                    "purpose": a.get("purpose", ""),
                    "platform": a.get("platform", ""),
                }
                for a in accts
            ],
        }

    def get_sessions(self, account_id: str = None, limit: int = 50) -> dict:
        """获取会话列表"""
        aid = account_id or self.account_id
        if not aid:
            return {"ok": False, "error": "未指定账号，且无可用账号"}
        try:
            sessions = collector.get_sessions(aid, limit=limit)
            return {
                "ok": True,
                "account_id": aid,
                "count": len(sessions),
                "sessions": [
                    {
                        "name": s.get("chat") or s.get("name") or s.get("display_name") or "?",
                        "username": s.get("username") or s.get("userName") or s.get("wxid") or "",
                        "is_group": "chatroom" in (s.get("username") or "").lower(),
                        "last_message": str(s.get("last_message") or s.get("content") or "")[:60],
                    }
                    for s in sessions
                ],
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def summarize_session(
        self,
        username: str,
        account_id: str = None,
        date_str: str = None,
        limit: int = 100,
        output_path: str = None,
    ) -> dict:
        """
        总结指定会话。

        参数：
            username: 微信 username（从 get_sessions 获取）
            account_id: 账号 ID，默认用初始化的账号
            date_str: 可选，格式 YYYY-MM-DD，只看该日期消息
            limit: 消息条数
            output_path: 可选，导出路径（含扩展名自动判断格式）

        返回：
            {"ok": True, "report": "...", "saved_to": "..."}
        """
        aid = account_id or self.account_id
        if not aid:
            return {"ok": False, "error": "未指定账号"}

        target_date = None
        if date_str:
            from datetime import datetime
            try:
                target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                return {"ok": False, "error": f"日期格式错误：{date_str}，应为 YYYY-MM-DD"}

        try:
            messages = collector.get_history_by_date(aid, username, target_date) if target_date \
                else collector.get_history(aid, username, limit=limit)
        except Exception as e:
            return {"ok": False, "error": f"采集失败：{e}"}

        lines = []
        for msg in messages:
            line = collector.format_message_for_summary(msg)
            if line:
                lines.append(line)
        messages_text = "\n".join(lines)

        if not messages_text.strip():
            return {"ok": True, "report": "（无有效消息内容）", "saved_to": None}

        m = collector.extract_metadata(messages)
        is_group = "chatroom" in username.lower()
        chat_type = "群聊" if is_group else "单聊"
        time_range = date_str or f"最近 {limit} 条消息"

        # 获取会话名
        chat_name = username
        try:
            sessions = collector.get_sessions(aid, limit=200)
            for s in sessions:
                uname = str(s.get("username") or s.get("userName") or "")
                if uname == username:
                    chat_name = str(s.get("chat") or s.get("name") or username)
                    break
        except Exception:
            pass

        # 判断报告风格
        style = "work"
        if is_group:
            try:
                classification = classifier.classify_session(
                    chat_name=chat_name,
                    messages_preview=messages_text[:500],
                    keywords=m.get("keywords", ""),
                    metadata=m,
                )
                style = classification["style"]
            except Exception:
                pass

        try:
            report = summarizer.summarize_session(
                chat_name=chat_name,
                chat_type=chat_type,
                messages_text=messages_text,
                metadata=m,
                time_range=time_range,
                style=style,
            )
        except Exception as e:
            return {"ok": False, "error": f"LLM 总结失败：{e}"}

        saved_to = None
        if output_path:
            try:
                exporter.export_report(report, output_path, title=f"会话摘要：{chat_name}")
                saved_to = output_path
            except Exception as e:
                return {"ok": False, "error": f"导出失败：{e}", "report": report}

        return {"ok": True, "report": report, "saved_to": saved_to}

    def daily_report(
        self,
        account_id: str = None,
        date_str: str = None,
        max_sessions: int = 0,
        output_path: str = None,
    ) -> dict:
        """
        生成每日汇总报告（自动判断工作/非工作风格）。

        参数：
            account_id: 账号 ID
            date_str: 可选，格式 YYYY-MM-DD，默认今天
            max_sessions: 最多处理会话数，0=不限
            output_path: 可选，导出路径

        返回：
            {"ok": True, "report": "...", "style": "work|newspaper", "saved_to": "..."}
        """
        aid = account_id or self.account_id
        if not aid:
            return {"ok": False, "error": "未指定账号"}

        from datetime import datetime
        target_date = date.today()
        if date_str:
            try:
                target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                return {"ok": False, "error": f"日期格式错误：{date_str}"}

        account = accounts.get_account(aid)
        if not account:
            return {"ok": False, "error": f"账号不存在：{aid}"}
        account_purpose = account.get("purpose", "")

        try:
            sessions = collector.get_sessions(aid, limit=100)
        except Exception as e:
            return {"ok": False, "error": f"获取会话列表失败：{e}"}

        if max_sessions > 0:
            sessions = sessions[:max_sessions]

        # 采集每个会话
        session_data_list = []
        for s in sessions:
            username = str(s.get("username") or s.get("userName") or "")
            chat_name = str(s.get("chat") or s.get("name") or s.get("display_name") or username)
            try:
                data = collector.collect_session_data(aid, username, date_filter=target_date)
                session_data_list.append(data)
            except Exception:
                pass

        if not session_data_list:
            return {"ok": True, "report": "（当日无有效消息）", "style": None, "saved_to": None}

        # 逐个生成摘要
        session_summaries = []
        for sess_data in session_data_list:
            try:
                summary = summarizer.summarize_session(
                    chat_name=sess_data["chat_name"],
                    chat_type=sess_data["chat_type"],
                    messages_text=sess_data["messages_text"],
                    metadata=sess_data["metadata"],
                    time_range=date_str or target_date.strftime("%Y-%m-%d"),
                )
            except Exception:
                summary = "（摘要生成失败）"
            session_summaries.append({
                "chat_name": sess_data["chat_name"],
                "chat_type": sess_data["chat_type"],
                "summary": summary,
                "metadata": sess_data["metadata"],
                "session_stats": sess_data.get("session_stats", {}),
            })

        # 判断风格
        classification = classifier.classify_for_daily(
            account_purpose=account_purpose,
            session_data_list=session_data_list,
        )
        global_style = classification["global_style"]

        # 渲染报告
        if global_style == "work":
            report = report_renderer.render_work_report(
                account_purpose=account_purpose,
                session_summaries=session_summaries,
                target_date=target_date,
                classification=classification,
            )
        else:
            report = report_renderer.render_newspaper_report(
                account_purpose=account_purpose,
                session_summaries=session_summaries,
                target_date=target_date,
                classification=classification,
            )

        saved_to = None
        if output_path:
            try:
                exporter.export_report(report, output_path, title=f"微信日报 {target_date}")
                saved_to = output_path
            except Exception as e:
                return {"ok": False, "error": f"导出失败：{e}", "report": report}

        return {
            "ok": True,
            "report": report,
            "style": global_style,
            "style_desc": "📋 工作报告" if global_style == "work" else "🗞️ 娱乐报纸",
            "session_count": len(session_data_list),
            "saved_to": saved_to,
        }

    # =========================================================================
    # 自然语言入口（供 Agent 直接调用）
    # =========================================================================

    def run(self, instruction: str, account_id: str = None) -> dict:
        """
        自然语言入口。解析用户指令并执行对应操作。

        支持的指令模式：
            "总结今天微信" / "生成日报" / "daily"
            "看看[群名]" / "总结[群名]" / "summary"
            "列出账号" / "list accounts"
            "查看会话列表" / "sessions"

        参数：
            instruction: 自然语言指令
            account_id: 可选，指定账号

        返回：
            {"ok": True, "report": "...", "action": "daily|summarize|sessions|..."}
        """
        instruction = instruction.lower().strip()
        aid = account_id or self.account_id

        if not aid:
            return {"ok": False, "error": "未注册账号，请先运行 register 命令"}

        # 判断指令类型
        if any(k in instruction for k in ["总结今天", "日报", "daily", "今日汇总", "微信日报"]):
            return self.daily_report(account_id=aid)

        elif any(k in instruction for k in ["会话列表", "sessions", "查看会话", "有哪些群"]):
            result = self.get_sessions(account_id=aid)
            result["action"] = "sessions"
            return result

        elif any(k in instruction for k in ["列出账号", "list", "有哪些账号"]):
            result = self.list_accounts()
            result["action"] = "list"
            return result

        elif any(k in instruction for k in ["总结", "summary", "看看", "这个群"]):
            # 尝试提取 username（简化处理，需要外部配合提供 username）
            return {
                "ok": False,
                "error": "summary 命令需要指定 username，请先用 get_sessions 查看会话列表",
                "action": "need_username",
            }

        else:
            return {
                "ok": False,
                "error": f"无法解析指令：{instruction}。支持的指令：总结今天微信、查看会话列表、列出账号。",
                "action": "unknown",
            }


# =========================================================================
# 独立运行（调试用）
# =========================================================================

if __name__ == "__main__":
    agent = WechatSummarizerAgent()
    if len(sys.argv) > 1:
        result = agent.run(" ".join(sys.argv[1:]))
        print(result)
    else:
        print("用法：python agent.py <自然语言指令>")
        print("示例：python agent.py 总结今天微信")
        print("       python agent.py 查看会话列表")
