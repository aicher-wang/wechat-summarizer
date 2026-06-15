"""微信聊天记录总结器 — 主入口"""
import argparse
import sys
from datetime import date, datetime
from pathlib import Path

import config
import accounts
import collector
import summarizer
import exporter
import classifier
import report_renderer
import stats


def cmd_register(args: argparse.Namespace) -> int:
    """注册新账号"""
    account = accounts.register_account(
        db_dir=args.db_dir,
        purpose=args.purpose,
        account_id=args.account_id or None,
        wechat_process=args.wechat_process or "",
    )
    print(f"[+] 账号注册成功：{account['account_id']}")
    print(f"    用途：{account['purpose'] or '（未设置）'}")
    print(f"    db_dir：{account['db_dir']}")
    print(f"    config：{account['config_path']}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """列出所有账号"""
    accts = accounts.list_accounts()
    if not accts:
        print("暂无已注册的账号。使用 register 子命令注册第一个账号。")
        return 0
    print(f"| account_id | purpose | platform | enabled |")
    print(f"|---|---|---|---|")
    for a in accts:
        print(f"| {a['account_id']} | {a.get('purpose','')} | {a.get('platform','')} | {a.get('enabled', True)} |")
    return 0


def cmd_sessions(args: argparse.Namespace) -> int:
    """查看会话列表"""
    try:
        sessions = collector.get_sessions(args.account_id, limit=args.limit)
    except Exception as e:
        print(f"获取会话列表失败：{e}", file=sys.stderr)
        return 1

    print(f"共 {len(sessions)} 个会话：\n")
    for i, s in enumerate(sessions, 1):
        name = s.get("chat") or s.get("name") or s.get("display_name") or "未命名"
        username = s.get("username") or s.get("userName") or s.get("wxid") or ""
        last_msg = str(s.get("last_message") or s.get("content") or "")[:40]
        is_group = "【群】" if "chatroom" in username.lower() else "【单聊】"
        print(f"{i:2d}. {is_group} {name}")
        print(f"    username: {username}  |  最近消息: {last_msg}")
    return 0


def cmd_summary(args: argparse.Namespace) -> int:
    """总结指定会话"""
    account = accounts.get_account(args.account_id)
    if not account:
        print(f"账号不存在：{args.account_id}", file=sys.stderr)
        return 1

    # 采集会话数据（含元数据）
    try:
        target_date = None
        time_range = ""

        if args.date:
            target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
            time_range = args.date
            messages = collector.get_history_by_date(args.account_id, args.username, target_date)
            m = collector.extract_metadata(messages)
        else:
            messages = collector.get_history(args.account_id, args.username, limit=args.limit)
            m = collector.extract_metadata(messages)
            time_range = f"最近 {args.limit or config.DEFAULT_HISTORY_LIMIT} 条消息"

        # 格式化消息
        lines = []
        for msg in messages:
            line = collector.format_message_for_summary(msg)
            if line:
                lines.append(line)
        messages_text = "\n".join(lines)

    except Exception as e:
        print(f"采集失败：{e}", file=sys.stderr)
        return 1

    if not messages_text.strip():
        print("无有效消息内容。")
        return 0

    # 获取会话名称和类型
    is_group = "chatroom" in args.username.lower()
    chat_type = "群聊" if is_group else "单聊"
    chat_name = args.username

    try:
        sessions = collector.get_sessions(args.account_id, limit=200)
        for s in sessions:
            uname = str(s.get("username") or s.get("userName") or "")
            if uname == args.username:
                chat_name = str(s.get("chat") or s.get("name") or args.username)
                break
    except Exception:
        pass

    # 调用 LLM
    try:
        report = summarizer.summarize_session(
            chat_name=chat_name,
            chat_type=chat_type,
            messages_text=messages_text,
            metadata=m,
            time_range=time_range,
        )
    except Exception as e:
        print(f"LLM 总结失败：{e}", file=sys.stderr)
        return 1

    print("\n" + "=" * 60)
    print(report)
    print("=" * 60)

    if args.output:
        exporter.export_report(report, args.output, title=f"会话摘要：{chat_name}")
        fmt = exporter.detect_format(args.output)
        print(f"[+] 报告已保存：{args.output}（{fmt.upper()} 格式）")
    return 0


def cmd_daily(args: argparse.Namespace) -> int:
    """
    生成每日汇总报告。

    流程：
      1. 采集所有会话的消息 + 元数据
      2. 对每个会话单独生成结构化摘要
      3. LLM 判断全局报告风格（工作 / 非工作）
      4. 根据风格选择渲染器（正规报告 / 娱乐报纸）
      5. 导出
    """
    # ---- ① 确定目标日期 ----
    if args.date:
        target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
    else:
        target_date = date.today()

    # ---- ② 获取账号 ----
    account = accounts.get_account(args.account_id)
    if not account:
        print(f"账号不存在：{args.account_id}", file=sys.stderr)
        return 1

    account_purpose = account.get("purpose", "")

    # ---- ③ 获取会话列表 ----
    try:
        sessions = collector.get_sessions(args.account_id, limit=args.session_limit)
    except Exception as e:
        print(f"获取会话列表失败：{e}", file=sys.stderr)
        return 1

    if not sessions:
        print("无会话记录。")
        return 0

    # 限制处理数量
    if args.max_sessions:
        sessions = sessions[:args.max_sessions]

    print(f"[步骤1/5] 正在采集 {len(sessions)} 个会话的消息（目标日期：{target_date}）...")

    # ---- ④ 采集每个会话的完整数据 ----
    session_data_list = []
    for i, s in enumerate(sessions, 1):
        username = str(s.get("username") or s.get("userName") or "")
        chat_name = str(s.get("chat") or s.get("name") or s.get("display_name") or username)
        is_group = "【群】" if "chatroom" in username.lower() else "【单聊】"
        print(f"  [{i}/{len(sessions)}] {is_group} {chat_name}")

        try:
            data = collector.collect_session_data(
                args.account_id, username, date_filter=target_date
            )
            session_data_list.append(data)
        except Exception as e:
            print(f"    采集失败：{e}")
            session_data_list.append({
                "chat_name": chat_name,
                "chat_type": "群聊" if "chatroom" in username.lower() else "单聊",
                "username": username,
                "messages_text": f"（读取失败：{e}）",
                "metadata": {},
            })

    # ---- ⑤ 对每个会话生成结构化摘要 + 统计 ----
    print(f"\n[步骤2/5] 正在对 {len(session_data_list)} 个会话生成摘要和统计...")
    session_summaries = []
    for i, sess_data in enumerate(session_data_list, 1):
        chat_name = sess_data["chat_name"]
        chat_type = sess_data["chat_type"]
        messages_text = sess_data["messages_text"]
        m = sess_data["metadata"]
        raw_messages = sess_data.get("raw_messages", [])
        time_range = target_date.strftime("%Y-%m-%d")

        print(f"  [{i}/{len(session_data_list)}] 总结：{chat_name}")

        # 生成摘要
        try:
            summary = summarizer.summarize_session(
                chat_name=chat_name,
                chat_type=chat_type,
                messages_text=messages_text,
                metadata=m,
                time_range=time_range,
            )
        except Exception as e:
            summary = f"（摘要生成失败：{e}）"
            print(f"    摘要失败：{e}")

        # 计算统计（规则计算，不调 LLM）
        try:
            session_stats = stats.compute_all_stats(raw_messages)
        except Exception:
            session_stats = {}

        session_summaries.append({
            "chat_name": chat_name,
            "chat_type": sess_data["chat_type"],
            "summary": summary,
            "metadata": m,
            "session_stats": session_stats,
        })

    # ---- ⑥ LLM 判断报告风格 ----
    print(f"\n[步骤3/5] LLM 正在判断报告风格（工作/非工作）...")
    classification = classifier.classify_for_daily(
        account_purpose=account_purpose,
        session_data_list=session_data_list,
    )
    global_style = classification["global_style"]
    style_desc = "📋 工作报告" if global_style == "work" else "🗞️ 娱乐报纸"
    print(f"  判断结果：{style_desc}")
    print(f"  推理：工作会话 {classification['work_sessions']} 个，非工作会话 {classification['non_work_sessions']} 个")

    # ---- ⑦ 根据风格渲染报告 ----
    print(f"\n[步骤4/5] 正在渲染报告（{style_desc}）...")
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

    # ---- ⑧ 输出 ----
    print("\n" + "=" * 60)
    print(report)
    print("=" * 60)

    # ---- ⑨ 导出 ----
    date_str = target_date.strftime("%Y%m%d")
    output_path = args.output or str(config.EXPORTS_DIR / f"wechat_daily_{date_str}.md")
    title = f"微信日报 {target_date.strftime('%Y年%m月%d日')}"
    exporter.export_report(report, output_path, title=title)
    fmt = exporter.detect_format(output_path)
    print(f"\n[步骤5/5] 报告已保存：{output_path}（{fmt.upper()} 格式）")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="微信聊天记录总结器（信息特征驱动 + 智能风格适配）")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # register
    p_reg = sub.add_parser("register", help="注册新账号")
    p_reg.add_argument("--db-dir", required=True, help="微信 db_storage 目录路径")
    p_reg.add_argument("--purpose", default="", help="账号用途说明，如'工作号'、'私人号'")
    p_reg.add_argument("--account-id", help="自定义账号 ID，不填则自动生成")
    p_reg.add_argument("--wechat-process", default="", help="微信进程名（Windows 多开时指定）")
    p_reg.set_defaults(func=cmd_register)

    # list
    sub.add_parser("list", help="列出已注册账号").set_defaults(func=cmd_list)

    # sessions
    p_sess = sub.add_parser("sessions", help="查看会话列表")
    p_sess.add_argument("--account-id", required=True, help="账号 ID")
    p_sess.add_argument("--limit", type=int, default=50, help="显示数量")
    p_sess.set_defaults(func=cmd_sessions)

    # summary
    p_sum = sub.add_parser("summary", help="总结指定会话")
    p_sum.add_argument("--account-id", required=True, help="账号 ID")
    p_sum.add_argument("--username", required=True, help="微信 username（可从 sessions 获取）")
    p_sum.add_argument("--date", help="指定日期，YYYY-MM-DD，默认不限日期")
    p_sum.add_argument("--limit", type=int, default=100, help="消息条数（不限日期时）")
    p_sum.add_argument("--output", help="输出文件路径")
    p_sum.set_defaults(func=cmd_summary)

    # daily
    p_daily = sub.add_parser("daily", help="生成每日汇总（自动判断工作/非工作风格）")
    p_daily.add_argument("--account-id", required=True, help="账号 ID")
    p_daily.add_argument("--date", help="目标日期，YYYY-MM-DD，默认今天")
    p_daily.add_argument("--session-limit", type=int, default=100, help="最多读取会话数")
    p_daily.add_argument("--max-sessions", type=int, default=0, help="最多 LLM 总结的会话数，0 表示不限")
    p_daily.add_argument("--output", help="输出文件路径")
    p_daily.set_defaults(func=cmd_daily)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    # 创建必要目录
    config.STATE_DIR.mkdir(parents=True, exist_ok=True)
    config.ACCOUNTS_DIR.mkdir(parents=True, exist_ok=True)
    config.EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
