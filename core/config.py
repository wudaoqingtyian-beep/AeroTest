"""config.py —— 多环境配置加载（M2 支撑）

查找顺序（找到即用）：
    1. {config_dir}/envs/{env}.yaml
    2. {config_dir}/{env}.yaml
    3. {config_dir}/config.yaml 中名为 {env} 的顶层键
"""


def load_env_config(env: str, config_dir: str = "config") -> dict:
    import os
    import yaml

    candidates = [
        os.path.join(config_dir, "envs", f"{env}.yaml"),
        os.path.join(config_dir, f"{env}.yaml"),
    ]
    for path in candidates:
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
    # 兜底：config.yaml 的顶层键
    whole = os.path.join(config_dir, "config.yaml")
    if os.path.exists(whole):
        with open(whole, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if env in data:
            return data[env]
    raise FileNotFoundError(f"找不到环境配置: {env}（查找过 {candidates} 与 {whole}）")
