# 微信聊天记录总结器

基于本地微信数据库 + LLM 的聊天记录分析工具，支持工作群/非工作群自动风格适配、发言统计、热词分析、多格式导出。

## 功能特性

- **智能风格适配**：自动判断会话类型，工作群输出正规报告，非工作群输出娱乐报纸
- **结构化摘要**：行动项、决策、待办、风险自动提取
- **7 大统计模块**：发言排行、群天气、活跃脉搏、热词、媒体产出、链接雷达、Emoji 风云榜
- **多模型支持**：Anthropic / OpenAI / DeepSeek / Kimi / MiniMax / 通义千问 / Gemini / 本地模型
- **多格式导出**：Markdown / HTML / PDF / Word

## 项目结构

```
wechat_summarizer/
├── agent.py           # Agent 接口（供 AI Agent 调用）
├── main.py           # CLI 入口
├── config.py         # 配置（路径、提示词模板）
├── accounts.py       # 账号注册与管理
├── collector.py      # 消息采集
├── summarizer.py     # LLM 摘要生成
├── classifier.py     # LLM 风格判断
├── report_renderer.py # 双风格渲染器
├── stats.py          # 统计模块
├── exporter.py       # 多格式导出
├── llm.py           # 多模型适配层
├── SKILL.md         # Claude Code Skill 定义
├── requirements.txt
└── .env.example
```

## 快速开始

### 1. 安装

```bash
git clone <your-repo-url>
cd wechat_summarizer
pip install -r requirements.txt
```

### 2. 配置

```bash
cp .env.example .env
# 编辑 .env，填入 LLM_PROVIDER 和对应的 API Key
```

### 3. 注册账号

```bash
python main.py register \
  --db-dir "C:\Users\xxx\WeChat Files\xxx\db_storage" \
  --purpose "工作号"
```

### 4. 使用

```bash
# 查看会话列表
python main.py sessions --account-id wx_xxxxxxxx

# 总结指定会话
python main.py summary --account-id wx_xxxxxxxx --username 对方username

# 生成每日汇总（自动判断风格）
python main.py daily --account-id wx_xxxxxxxx

# 导出为 PDF
python main.py daily --account-id wx_xxxxxxxx --output report.pdf
```

## Agent 使用

```python
from agent import WechatSummarizerAgent

agent = WechatSummarizerAgent()

# 自然语言入口
result = agent.daily_report(account_id="wx_xxxxxxxx")

# 直接调用
result = agent.summarize_session(username="群username", date_str="2026-06-15")
result = agent.get_sessions()
```

## LLM 模型配置

编辑 `.env`：

```bash
LLM_PROVIDER=anthropic       # anthropic / openai / deepseek / kimi / minimax / dashscope / gemini / local
ANTHROPIC_API_KEY=sk-ant-xxxxx
CLAUDE_MODEL=claude-sonnet-4-6
```

## Claude Code Skill

将 `SKILL.md` 放到 `~/.claude/skills/wechat-summary/` 即可通过 `/wechat-summary` 命令调用。

## 报告风格示例

### 工作报告

```
====================================================
  微信工作群报告
====================================================
  日期：2026年6月15日
  汇总会话数：3 个
====================================================

──────────────────────────────────────────────────
  【1】项目A沟通群（群聊）
──────────────────────────────────────────────────

  📋 概况：今天主要讨论了技术方案选型，B方案已确认。

  ✅ 行动项（共 3 项）
  • 张明：周五前发出修订版报价单
  • 李华：联系供应商确认交期

  ✔️ 决策结论
  • 合同签署时间确定为下周三
```

### 娱乐报纸

```
  ╔══════════════════════════════════════════════════╗
  ║        🗞️  WEIXIN DAILY · 你的群聊小报           ║
  ║              2026年6月15日 · 第 061526 期              ║
  ╚══════════════════════════════════════════════════╝

  ┃  📰 头条：周六去哪儿吃饭？妈妈连发5条语音搞定了
  ┃  💬 金句：「现在还记得当时的情景呢」——爸爸
  ┃  🏆 发言排行榜
  ┃    🥇 妈妈        ██████████ 23条
  ┃    🥈 爸爸        ████████ 17条
  ┃  🌤️ 极度活跃 | 情绪：😂 笑声不断
  ┃  🔥 热词：吃饭×12
```

## 依赖说明

| 格式 | 扩展名 | 依赖 |
|------|--------|------|
| Markdown | `.md` | 无 |
| HTML | `.html` | 无 |
| PDF | `.pdf` | `pip install weasyprint` |
| Word | `.docx` | `pip install python-docx` |

## 免责声明

- 本工具仅读取本机微信本地数据库，**不会**发送、修改、删除任何消息
- 请遵守微信用户协议，不要用于他人数据的违规采集
- 报告结果基于本地数据，不代表微信官方立场

## License

MIT
