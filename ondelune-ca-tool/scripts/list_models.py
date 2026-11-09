"""列出某个供应商当前可用的模型 id（读取 .env 里的 key）。

  python3 scripts/list_models.py hf_qwen      # 列出 Hugging Face 上可用的模型，并筛出 Qwen
  python3 scripts/list_models.py deepseek
"""
import json
import os
import sys
import urllib.request
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
name = sys.argv[1] if len(sys.argv) > 1 else "hf_qwen"
p = yaml.safe_load(open(ROOT / "config/models.yaml", encoding="utf-8"))["providers"][name]
req = urllib.request.Request(p["base_url"].rstrip("/") + "/models",
                             headers={"Authorization": f"Bearer {os.environ[p['api_key_env']]}"})
ids = [m["id"] for m in json.load(urllib.request.urlopen(req, timeout=30))["data"]]
if name.startswith("hf"):
    ids = [i for i in ids if any(k in i.lower() for k in ("qwen", "deepseek", "kimi", "moonshot"))]
print("\n".join(sorted(ids)))
