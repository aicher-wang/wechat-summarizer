"""账号管理与隔离"""
import json
import secrets
import subprocess
import platform
from pathlib import Path
from datetime import datetime
from typing import Optional

import config


def get_state_dir() -> Path:
    """获取状态目录，不存在则创建"""
    state = Path(config.STATE_DIR)
    state.mkdir(parents=True, exist_ok=True)
    return state


def get_accounts_dir() -> Path:
    """获取账号配置目录"""
    accounts = Path(config.ACCOUNTS_DIR)
    accounts.mkdir(parents=True, exist_ok=True)
    return accounts


def get_registry_path() -> Path:
    """获取账号记忆文件路径"""
    return get_state_dir() / "account_registry.json"


def generate_account_id(prefix: str = "wx") -> str:
    """生成随机账号 ID"""
    safe = "".join(c for c in prefix if c.isalnum() or c in "_-").strip("_-") or "wx"
    return f"{safe}_{secrets.token_hex(4)}"


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def load_registry() -> dict:
    """加载账号记忆"""
    path = get_registry_path()
    if not path.exists():
        return {"version": 1, "updated_at": now(), "accounts": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        return {"version": 1, "updated_at": now(), "accounts": {}}


def save_registry(registry: dict) -> Path:
    """保存账号记忆"""
    path = get_registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    registry["updated_at"] = now()
    path.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        import os
        os.chmod(path, 0o600)
    except OSError:
        pass
    return path


def ensure_account_config_path(config_path: str) -> str:
    """确保 config.json 在账号目录内，禁止回退到全局状态"""
    if not config_path:
        raise ValueError("缺少 config_path，不允许回退到全局状态")
    p = Path(config_path).expanduser().resolve()
    root = get_accounts_dir().resolve()
    if root not in p.parents and p.parent != root:
        raise ValueError(f"config_path 必须位于 {root} 内")
    if p.name != "config.json":
        raise ValueError("config_path 必须指向 config.json")
    return str(p)


def build_wechat_cli_command(config_path: str) -> str:
    """构建 wechat-cli 命令"""
    sys = platform.system()
    state_dir = get_state_dir()

    if sys == "Windows":
        python_exe = str(state_dir / "venv" / "Scripts" / "python.exe")
        entry_py = str(state_dir / "src" / "wechat-cli" / "entry.py")
        return f'"{python_exe}" "{entry_py}" --config "{config_path}"'
    else:
        return f"{state_dir}/bin/wechat-cli --config {config_path}"


def isolated_subprocess_env() -> dict:
    """构建隔离的子进程环境变量"""
    import os
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return env


# ===== 账号注册 CRUD =====

def register_account(
    db_dir: str,
    purpose: str = "",
    account_id: Optional[str] = None,
    bundle_id: str = "",
    app_path: str = "",
    wechat_process: str = "",
) -> dict:
    """注册一个新账号，返回账号记录"""
    registry = load_registry()
    accounts = registry.setdefault("accounts", {})

    if not account_id:
        account_id = generate_account_id()

    if account_id in accounts and not (Path(db_dir) / "all_keys.json").exists():
        raise ValueError(f"account_id 已存在：{account_id}")

    account_dir = get_accounts_dir() / account_id
    account_dir.mkdir(parents=True, exist_ok=True)
    config_path = account_dir / "config.json"

    cfg = {
        "db_dir": str(Path(db_dir).expanduser().resolve()),
        "keys_file": "all_keys.json",
        "decrypted_dir": "decrypted",
        "decoded_image_dir": "decoded_images",
    }
    if bundle_id:
        cfg["bundle_id"] = bundle_id
    if app_path:
        cfg["app_path"] = str(Path(app_path).expanduser())
    if wechat_process:
        cfg["wechat_process"] = wechat_process
    elif platform.system() == "Darwin":
        cfg["wechat_process"] = "WeChat"

    config_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    command_prefix = build_wechat_cli_command(str(config_path))

    record = {
        "account_id": account_id,
        "purpose": purpose,
        "db_dir": str(Path(db_dir).expanduser().resolve()),
        "config_path": str(config_path),
        "command_prefix": command_prefix,
        "platform": platform.system(),
        "enabled": True,
        "created_at": now(),
        "updated_at": now(),
    }
    accounts[account_id] = record
    save_registry(registry)
    return record


def list_accounts() -> list[dict]:
    """列出所有已注册账号"""
    registry = load_registry()
    accounts = registry.get("accounts", {})
    if not isinstance(accounts, dict):
        return []
    return [
        {**record, "command_prefix": build_wechat_cli_command(record.get("config_path", ""))}
        for record in accounts.values()
        if isinstance(record, dict) and record.get("enabled", True)
    ]


def get_account(account_id: str) -> Optional[dict]:
    """获取指定账号记录"""
    registry = load_registry()
    record = registry.get("accounts", {}).get(account_id)
    if not record:
        return None
    return {
        **record,
        "command_prefix": build_wechat_cli_command(record.get("config_path", "")),
    }


def update_account_purpose(account_id: str, purpose: str) -> dict:
    """更新账号用途标签"""
    registry = load_registry()
    record = registry.get("accounts", {}).get(account_id)
    if not record:
        raise KeyError(f"账号不存在：{account_id}")
    record["purpose"] = purpose
    record["updated_at"] = now()
    save_registry(registry)
    return record
