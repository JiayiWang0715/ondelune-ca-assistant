"""读取 config/ 下的品牌、产品、场景、模型配置。"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "config"


@dataclass
class Config:
    brand: dict
    products: dict
    scenarios: dict
    models: dict
    exemplars: dict | None = None   # v2（D4）：人工范例库

    @property
    def product_list(self) -> list[dict]:
        return self.products["products"]

    @property
    def sku_index(self) -> dict[str, dict]:
        return {p["sku"]: p for p in self.product_list}

    def tier_rank(self, tier: str) -> int:
        return self.scenarios["tiers"].get(tier, {"rank": 0})["rank"]


def load_config(config_dir: Path | str = CONFIG_DIR) -> Config:
    d = Path(config_dir)
    with open(d / "brand.yaml", encoding="utf-8") as f:
        brand = yaml.safe_load(f)
    with open(d / "products.json", encoding="utf-8") as f:
        products = json.load(f)
    with open(d / "scenarios.yaml", encoding="utf-8") as f:
        scenarios = yaml.safe_load(f)
    with open(d / "models.yaml", encoding="utf-8") as f:
        models = yaml.safe_load(f)
    ex_path = d.parent / "data" / "exemplars.yaml"
    exemplars = None
    if ex_path.exists():
        with open(ex_path, encoding="utf-8") as f:
            exemplars = yaml.safe_load(f)
    return Config(brand=brand, products=products, scenarios=scenarios, models=models, exemplars=exemplars)
