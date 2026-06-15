# 微信聊天记录总结器 Skill

## 简介

这是一个让 AI Agent 读取本地微信聊天记录并生成结构化报告的工具。支持：
- 单聊/群聊摘要
- 每日自动汇总
- 工作群 → 正规报告格式
- 非工作群 → 娱乐报纸格式（含发言排行榜、热词、天气等统计）
- 多格式导出：Markdown / HTML / PDF / Word

## 使用限制

- **仅读取本机微信数据**，不会发送、修改、删除任何消息
- 请遵守微信用户协议，不要用于他人数据的违规采集

---

## 安装

```bash
cd C:\Users\tengxiao.wang\wechat_summarizer
pip install -r requirements.txt

# 复制并编辑配置
copy .env.example .env
# 编辑 .env，填入 ANTHROPIC_API_KEY 和 LLM_PROVIDER
```

---

## 注册账号

使用前必须先注册微信账号（指向 db_storage 目录）：

```
$ cd C:\Users\tengxiao.wang\wechat_summarizer
$ python main.py register --db-dir "C:\Users\xxx\WeChat Files\xxx\db_storage" --purpose "工作号"
```

---

## 可用命令

### register — 注册账号
```
python main.py register --db-dir "微信db_storage路径" --purpose "账号用途"
```

### list — 查看账号
```
python main.py list
```

### sessions — 查看会话列表
```
python main.py sessions --account-id wx_xxxxxxxx --limit 50
```

### summary — 总结指定会话
```
# 不限日期，看最近消息
python main.py summary --account-id wx_xxxxxxxx --username 对方username

# 指定日期
python main.py summary --account-id wx_xxxxxxxx --username 对方username --date 2026-06-15

# 导出为 Word
python main.py summary --account-id wx_xxxxxxxx --username 对方username --output report.docx
```

### daily — 生成每日汇总（自动判断工作/非工作风格）
```
# 生成今天日报
python main.py daily --account-id wx_xxxxxxxx

# 指定日期
python main.py daily --account-id wx_xxxxxxxx --date 2026-06-15

# 限制处理会话数
python main.py daily --account-id wx_xxxxxxxx --max-sessions 10

# 导出为 PDF
python main.py daily --account-id wx_xxxxxxxx --output daily_report.pdf
```

---

## LLM 模型配置

编辑 `.env` 文件：

```bash
# 选择 Provider：anthropic / openai / deepseek / kimi / minimax / dashscope / gemini / local
LLM_PROVIDER=anthropic

# Anthropic
ANTHROPIC_API_KEY=sk-ant-xxxxx
CLAUDE_MODEL=claude-sonnet-4-6

# DeepSeek（示例）
# LLM_PROVIDER=deepseek
# DEEPSEEK_API_KEY=sk-xxxxx
```

---

## Agent 使用示例

当用户说以下内容时，自动调用本 Skill：

| 用户说 | 调用命令 |
|--------|---------|
| "总结一下今天微信" | `daily --account-id <id>` |
| "今天项目群聊了什么" | `summary --account-id <id> --username 项目群username` |
| "帮我看看这个月微信花了多少钱" | （扩展能力，待实现） |
| "把今天的工作群导出成 PDF" | `daily --account-id <id> --output report.pdf` |
| "看看家人群今天聊了啥" | `summary --account-id <id> --username 家人群username` |

---

## 报告风格说明

Agent 调用 `daily` 命令时会自动：
1. 采集所有会话消息
2. 对每个会话生成结构化摘要
3. **LLM 判断每个会话是工作相关还是非工作相关**
4. 根据判断结果选择报告风格

**工作群** → 正规报告格式（行动项、决策、风险、待办清晰）
**非工作群** → 娱乐报纸格式（头条、次条、金句、发言排行榜、热词、群天气等）

---

## 状态目录

所有账号配置和数据存储在 `state/` 目录：
```
state/
├── account_registry.json   # 账号记忆
├── accounts/              # 各账号独立配置
│   └── wx_xxxxxxxx/
│       └── config.json
├── src/                  # wechat-cli 源码
│   └── wechat-cli/
└── venv/                # Python 虚拟环境
```

---

## 故障排除

| 问题 | 解决方法 |
|------|---------|
| "账号不存在" | 先运行 `register` 注册账号 |
| "命令不存在" | 检查 wechat-cli 是否正确安装到 `state/src/wechat-cli` |
| "LLM 调用失败" | 检查 `.env` 中的 API Key 和 Provider 配置 |
| "PDF 导出失败" | 安装 weasyprint：`pip install weasyprint` |
| "Word 导出失败" | 安装 python-docx：`pip install python-docx` |
