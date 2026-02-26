from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
import logging
from pathlib import Path
from typing import Any
import re
import subprocess
import warnings

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib import font_manager

from app.services.expense_service import ExpenseService


logger = logging.getLogger(__name__)


class AnalyticsService:
    def __init__(self, expense_service: ExpenseService, output_dir: str, font_candidates: str | None = None):
        self.expense_service = expense_service
        self.output_dir = Path(output_dir)
        logging.getLogger("matplotlib").setLevel(logging.WARNING)
        warnings.filterwarnings("ignore", message=r"Glyph .* missing from font\(s\)")
        self._configure_fonts(font_candidates)

    def _configure_fonts(self, font_candidates: str | None) -> None:
        candidates = [name.strip() for name in (font_candidates or "").split(",") if name.strip()]
        self._register_system_candidate_fonts(candidates)
        installed_names = [font.name for font in font_manager.fontManager.ttflist]

        selected = None
        for name in candidates:
            lowered = name.lower()
            exact = next((inst for inst in installed_names if inst.lower() == lowered), None)
            if exact:
                selected = exact
                break
            partial = next((inst for inst in installed_names if lowered in inst.lower()), None)
            if partial:
                selected = partial
                break

        if not selected:
            selected = self._pick_font_from_fc_list()

        if selected:
            plt.rcParams["font.family"] = "sans-serif"
            plt.rcParams["font.sans-serif"] = [selected, "DejaVu Sans"]
            logger.info("Analytics chart font selected: %s", selected)
        else:
            plt.rcParams["font.family"] = "sans-serif"
            plt.rcParams["font.sans-serif"] = ["DejaVu Sans"]
            logger.warning("No configured CJK font found; fallback to DejaVu Sans")

        plt.rcParams["axes.unicode_minus"] = False

    def _pick_font_from_fc_list(self) -> str | None:
        try:
            output = subprocess.check_output(["fc-list", ":lang=zh", "file", "family"], text=True)
        except Exception:
            return None

        for line in output.splitlines():
            if not line.strip() or ":" not in line:
                continue
            path_part = line.split(":", 1)[0].strip()
            font_path = Path(path_part)
            if not font_path.exists():
                continue
            try:
                font_manager.fontManager.addfont(str(font_path))
                name = font_manager.FontProperties(fname=str(font_path)).get_name()
                if name:
                    logger.info("Analytics font selected from fc-list: %s", name)
                    return name
            except Exception:
                continue
        return None

    def _register_system_candidate_fonts(self, candidates: list[str]) -> None:
        candidate_tokens = [re.sub(r"\s+", "", name).lower() for name in candidates]
        system_fonts = font_manager.findSystemFonts(fontext="ttf") + font_manager.findSystemFonts(fontext="otf")
        for root in [Path("/usr/share/fonts"), Path.home() / ".local/share/fonts"]:
            if root.exists():
                system_fonts.extend([str(path) for path in root.rglob("*.ttc")])

        for font_path in system_fonts:
            normalized = re.sub(r"\s+", "", Path(font_path).name).lower()
            if any(token and token in normalized for token in candidate_tokens):
                try:
                    font_manager.fontManager.addfont(font_path)
                except Exception:
                    continue

    async def analyze_expenses(self, user_id: str, limit: int = 200, days: int = 0) -> dict[str, Any]:
        records = await self._get_records(user_id=user_id, limit=limit, days=days)
        if not records:
            return {"count": 0, "total": 0.0, "message": "暂无消费数据"}

        total = round(sum(item.amount for item in records), 2)
        count = len(records)
        average = round(total / count, 2)
        max_record = max(records, key=lambda row: row.amount)

        by_category: dict[str, float] = defaultdict(float)
        for item in records:
            by_category[item.category] += float(item.amount)

        sorted_category = sorted(by_category.items(), key=lambda pair: pair[1], reverse=True)
        top_category, top_value = sorted_category[0]

        return {
            "count": count,
            "total": total,
            "average": average,
            "top_expense": {
                "amount": float(max_record.amount),
                "category": max_record.category,
                "description": max_record.description,
                "spent_at": max_record.spent_at.isoformat(),
            },
            "top_category": {"name": top_category, "amount": round(top_value, 2)},
            "by_category": {name: round(value, 2) for name, value in sorted_category},
        }

    async def visualize_expenses(
        self,
        user_id: str,
        chart_types: list[str] | None = None,
        limit: int = 200,
        days: int = 0,
    ) -> dict[str, Any]:
        records = await self._get_records(user_id=user_id, limit=limit, days=days)
        if not records:
            return {"count": 0, "charts": [], "message": "暂无消费数据，无法生成图表"}

        selected = set(chart_types or ["all"])
        if "all" in selected:
            selected = {"category_bar", "category_pie", "daily_trend", "top_expenses"}

        charts: list[dict[str, Any]] = []
        folder = self.output_dir / user_id
        folder.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if "category_bar" in selected:
            charts.append(self._draw_category_bar(records, folder / f"{timestamp}_category_bar.png"))
        if "category_pie" in selected:
            charts.append(self._draw_category_pie(records, folder / f"{timestamp}_category_pie.png"))
        if "daily_trend" in selected:
            charts.append(self._draw_daily_trend(records, folder / f"{timestamp}_daily_trend.png"))
        if "top_expenses" in selected:
            charts.append(self._draw_top_expenses(records, folder / f"{timestamp}_top_expenses.png"))

        return {
            "count": len(records),
            "charts": charts,
            "output_dir": str(folder),
        }

    async def _get_records(self, user_id: str, limit: int, days: int):
        safe_limit = max(1, min(limit, 1000))
        rows = await self.expense_service.query_expenses(user_id=user_id, limit=safe_limit)
        if days > 0:
            cutoff = datetime.utcnow() - timedelta(days=days)
            rows = [row for row in rows if row.spent_at >= cutoff]
        return rows

    def _draw_category_bar(self, records, output: Path) -> dict[str, Any]:
        by_category: dict[str, float] = defaultdict(float)
        for row in records:
            by_category[row.category] += float(row.amount)
        names = list(by_category.keys())
        values = [by_category[name] for name in names]

        plt.figure(figsize=(8, 5))
        plt.bar(names, values)
        plt.title("Expense by Category")
        plt.xlabel("Category")
        plt.ylabel("Amount")
        plt.tight_layout()
        plt.savefig(output)
        plt.close()
        return {"type": "category_bar", "path": str(output)}

    def _draw_category_pie(self, records, output: Path) -> dict[str, Any]:
        by_category: dict[str, float] = defaultdict(float)
        for row in records:
            by_category[row.category] += float(row.amount)

        plt.figure(figsize=(7, 7))
        plt.pie(by_category.values(), labels=by_category.keys(), autopct="%1.1f%%", startangle=90)
        plt.title("Expense Category Share")
        plt.tight_layout()
        plt.savefig(output)
        plt.close()
        return {"type": "category_pie", "path": str(output)}

    def _draw_daily_trend(self, records, output: Path) -> dict[str, Any]:
        by_day: dict[str, float] = defaultdict(float)
        for row in records:
            by_day[row.spent_at.strftime("%Y-%m-%d")] += float(row.amount)
        days = sorted(by_day.keys())
        values = [by_day[d] for d in days]

        plt.figure(figsize=(9, 5))
        plt.plot(days, values, marker="o")
        plt.title("Daily Expense Trend")
        plt.xlabel("Date")
        plt.ylabel("Amount")
        plt.xticks(rotation=35)
        plt.tight_layout()
        plt.savefig(output)
        plt.close()
        return {"type": "daily_trend", "path": str(output)}

    def _draw_top_expenses(self, records, output: Path) -> dict[str, Any]:
        top_rows = sorted(records, key=lambda row: row.amount, reverse=True)[:10]
        labels = [f"{row.description or row.category} ({row.spent_at:%m-%d})" for row in top_rows]
        values = [float(row.amount) for row in top_rows]

        plt.figure(figsize=(10, 6))
        plt.barh(labels[::-1], values[::-1])
        plt.title("Top Expenses")
        plt.xlabel("Amount")
        plt.tight_layout()
        plt.savefig(output)
        plt.close()
        return {"type": "top_expenses", "path": str(output)}
