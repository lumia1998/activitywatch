import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple

from aw_core.config import load_config_toml
from aw_core.dirs import get_data_dir
from PIL import Image, ImageDraw, ImageFont

from .data import (
    build_activity_from_summary,
    build_input_stats,
    build_input_stats_by_top_apps,
    build_input_trend,
    build_summary_range,
)


@dataclass
class ReportConfig:
    enabled: bool
    hour: int
    minute: int
    days: int
    mode: str
    output_dir: str


_DEFAULT_CONFIG = """
[aw-pywebview.report]
enabled = false
# 24 小时制
hour = 0
minute = 0
# 统计近 N 天
days = 1
# daily_24h: 昨天 00:00-24:00
# today_so_far: 今天 00:00-现在
mode = "daily_24h"
# 输出目录，留空则使用默认 data 目录
output_dir = ""
""".strip()

COLORS = {
    "bg_paper": "#fdfbf7",
    "ink_primary": "#5d4037",
    "ink_secondary": "#8d6e63",
    "yellow": "#fff9c4",
    "pink": "#ffccbc",
    "blue": "#b3e5fc",
    "green": "#c8e6c9",
    "purple": "#e1bee7",
    "orange": "#ff7043",
    "white": "#ffffff",
    "grid": "#eeeeee",
}


def load_report_config() -> ReportConfig:
    config = load_config_toml("aw-pywebview", _DEFAULT_CONFIG)
    section = config.get("aw-pywebview", {})
    report = section.get("report", {})

    enabled = bool(report.get("enabled", False))
    hour = int(report.get("hour", 0))
    minute = int(report.get("minute", 0))
    days = int(report.get("days", 1))
    mode = str(report.get("mode", "daily_24h"))
    output_dir = report.get("output_dir", "")

    if not output_dir:
        output_dir = os.path.join(get_data_dir("aw-pywebview"), "reports")

    return ReportConfig(
        enabled=enabled,
        hour=hour,
        minute=minute,
        days=days,
        mode=mode,
        output_dir=output_dir,
    )


def _ensure_dir(path: str) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)


def _format_duration(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def _load_font(size: int, style: str = "regular") -> ImageFont.FreeTypeFont:
    fonts = {
        "regular": "C:/Windows/Fonts/msyh.ttc",
        "handwriting": "C:/Windows/Fonts/simkai.ttf",
        "bold": "C:/Windows/Fonts/msyhbd.ttc",
    }
    path = fonts.get(style, fonts["regular"])
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        try:
            return ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", size)
        except:
            return ImageFont.load_default()


def _build_summary_for_mode(cfg: ReportConfig) -> Dict[str, object]:
    now = datetime.now().astimezone()

    if cfg.mode == "today_so_far":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return build_summary_range(start, now)

    end = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start = end - timedelta(days=cfg.days)
    return build_summary_range(start, end)


def _parse_datetime(value: str) -> datetime:
    if not value:
        return datetime.now().astimezone()
    if value.endswith("Z"):
        value = value.replace("Z", "+00:00")
    return datetime.fromisoformat(value)


def _sum_input(item: Dict[str, int]) -> int:
    return int(item.get("presses", 0)) + int(item.get("clicks", 0)) + int(
        item.get("scroll", 0)
    )


def _extract_duration(summary: Dict[str, object]) -> float:
    result = summary.get("result", {}) if isinstance(summary, dict) else {}
    return float(result.get("window", {}).get("duration", 0))


def _build_report_json(summary: Dict[str, object], output_dir: str) -> str:
    _ensure_dir(output_dir)

    time_range = summary.get("time_range", {})
    start_dt = _parse_datetime(time_range.get("start"))
    end_dt = _parse_datetime(time_range.get("end"))

    input_total = build_input_stats(start_dt, end_dt)

    data = {
        "time_range": time_range,
        "duration": _extract_duration(summary),
        "input_total": input_total,
        "top_apps": build_activity_from_summary(summary, limit=6),
        "input_top_apps": build_input_stats_by_top_apps(
            summary=summary,
            start=start_dt,
            end=end_dt,
            top_n=6,
        ),
    }

    filename = f"aw-report-{datetime.now().strftime('%Y%m%d')}.json"
    output_path = os.path.join(output_dir, filename)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return output_path


def draw_dashed_line(draw, start, end, fill, width=1, dash=(5, 5)):
    x1, y1 = start
    x2, y2 = end
    dx = x2 - x1
    dy = y2 - y1
    dist = (dx**2 + dy**2)**0.5
    if dist == 0:
        return

    dash_len = sum(dash)
    num_dashes = int(dist / dash_len)

    for i in range(num_dashes):
        s_pct = (i * dash_len) / dist
        e_pct = (i * dash_len + dash[0]) / dist
        if e_pct > 1:
            e_pct = 1

        draw.line(
            [(x1 + dx * s_pct, y1 + dy * s_pct), (x1 + dx * e_pct, y1 + dy * e_pct)],
            fill=fill,
            width=width,
        )


def draw_dashed_rectangle(draw, box, color, width=1, dash=(5, 5)):
    x0, y0, x1, y1 = box
    draw_dashed_line(draw, (x0, y0), (x1, y0), color, width, dash)
    draw_dashed_line(draw, (x1, y0), (x1, y1), color, width, dash)
    draw_dashed_line(draw, (x1, y1), (x0, y1), color, width, dash)
    draw_dashed_line(draw, (x0, y1), (x0, y0), color, width, dash)


def draw_sticker(
    image,
    box,
    text,
    font,
    bg_color,
    text_color,
    rotation=-2,
    shadow_color=None,
    shadow_offset=(5, 5),
):
    w, h = box[2] - box[0], box[3] - box[1]
    # Create a larger temp image to avoid clipping after rotation
    pad = 40
    temp = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
    tdraw = ImageDraw.Draw(temp)

    inner_box = (pad, pad, pad + w, pad + h)
    if shadow_color:
        tdraw.rectangle(
            (inner_box[0] + shadow_offset[0], inner_box[1] + shadow_offset[1],
             inner_box[2] + shadow_offset[0], inner_box[3] + shadow_offset[1]),
            fill=shadow_color,
        )

    tdraw.rectangle(inner_box, fill=bg_color, outline=COLORS["ink_primary"], width=3)
    draw_dashed_rectangle(
        tdraw,
        (inner_box[0] + 5, inner_box[1] + 5, inner_box[2] - 5, inner_box[3] - 5),
        COLORS["ink_secondary"],
        width=1,
        dash=(8, 8),
    )

    # Center text
    tw = tdraw.textlength(text, font=font)
    th = font.size
    tdraw.text(
        (pad + (w - tw) / 2, pad + (h - th) / 2 - 5),
        text,
        fill=text_color,
        font=font,
    )

    rotated = temp.rotate(rotation, resample=Image.BICUBIC, expand=True)
    image.alpha_composite(rotated, (box[0] - pad, box[1] - pad))


def generate_report_image(summary: Dict[str, object], output_dir: str) -> str:
    _ensure_dir(output_dir)

    width, height = 1000, 1400
    # Use RGBA for transparency support in sub-drawings
    base_image = Image.new("RGBA", (width, height), COLORS["bg_paper"])
    draw = ImageDraw.Draw(base_image)

    # 1. Background Dot Grid
    spacing = 25
    for x in range(0, width, spacing):
        for y in range(0, height, spacing):
            draw.ellipse((x - 1, y - 1, x + 1, y + 1), fill="#dddddd")

    # 2. Main Container (Stacked Paper Effect)
    margin = 50
    cw, ch = width - margin * 2, height - margin * 2
    cx, cy = margin, margin

    # Shadows
    draw.rectangle((cx + 8, cy + 8, cx + cw + 8, cy + ch + 8), fill=COLORS["blue"])
    draw.rectangle((cx + 16, cy + 16, cx + cw + 16, cy + ch + 16), fill=COLORS["pink"])
    # Main white page
    draw.rectangle((cx, cy, cx + cw, cy + ch), fill=COLORS["white"], outline=COLORS["ink_primary"], width=3)
    # Stitching
    draw_dashed_rectangle(draw, (cx + 12, cy + 12, cx + cw - 12, cy + ch - 12), COLORS["ink_secondary"], width=2, dash=(12, 12))

    # Fonts
    title_font = _load_font(48, "bold")
    hand_font_lg = _load_font(32, "handwriting")
    hand_font_md = _load_font(24, "handwriting")
    hand_font_sm = _load_font(18, "handwriting")
    label_font = _load_font(20, "bold")
    value_font = _load_font(28, "bold")

    # 3. Header Sticker
    time_range = summary.get("time_range", {})
    date_str = f"{time_range.get('start', '')[:10]}"
    
    draw_sticker(
        base_image,
        (200, 100, 800, 220),
        "ActivityWatch 日报",
        title_font,
        COLORS["white"],
        COLORS["orange"],
        rotation=-1.5,
        shadow_color=COLORS["blue"],
    )
    
    # Date Badge
    draw.rectangle((720, 190, 880, 230), fill=COLORS["yellow"], outline=COLORS["ink_primary"], width=1)
    draw.text((735, 195), date_str, fill=COLORS["ink_primary"], font=hand_font_md)

    # 4. Summary Stamps
    result = summary.get("result", {})
    duration = result.get("window", {}).get("duration", 0)
    apps = build_activity_from_summary(summary, limit=10)
    
    start_dt = _parse_datetime(time_range.get("start"))
    end_dt = _parse_datetime(time_range.get("end"))
    input_stats_all = build_input_stats(start_dt, end_dt)
    total_inputs = _sum_input(input_stats_all)

    stamps_data = [
        ("有效时长", _format_duration(duration), COLORS["orange"]),
        ("应用总数", f"{len(apps)}", COLORS["green"]),
        ("总输入量", f"{total_inputs}", COLORS["blue"]),
        ("最活跃应用", apps[0]["app"] if apps else "None", COLORS["purple"]),
    ]

    stamp_w, stamp_h = 200, 140
    start_x, start_y = 120, 280
    gap = 20

    for i, (label, value, color) in enumerate(stamps_data):
        ix = i % 2
        iy = i // 2
        sx = start_x + ix * (stamp_w + 350)
        sy = start_y + iy * (stamp_h + gap)
        
        # Stamp Box
        draw.rounded_rectangle((sx, sy, sx + stamp_w, sy + stamp_h), radius=12, fill=COLORS["white"], outline=COLORS["ink_primary"], width=2)
        # Inner dotted
        draw_dashed_rectangle(draw, (sx+6, sy+6, sx+stamp_w-6, sy+stamp_h-6), "#e0e0e0", width=1, dash=(4, 4))
        
        # Label & Value
        draw.text((sx + 20, sy + 25), label, fill=COLORS["ink_secondary"], font=hand_font_md)
        # Handle long text for "most active app"
        v_font = value_font
        if len(value) > 10: v_font = _load_font(18, "bold")
        draw.text((sx + 20, sy + 65), value, fill=color, font=v_font)

    # Highlight Time (Center)
    trend = build_input_trend(start_dt, end_dt, bucket_count=24)
    peak_hour = "00:00"
    if trend:
        max_idx = 0
        max_count = -1
        for i, t in enumerate(trend):
            if t["count"] > max_count:
                max_count = t["count"]
                max_idx = i
        
        # Calculate actual hour
        peak_dt = start_dt + timedelta(hours=(max_idx * (end_dt - start_dt).total_seconds() / 3600 / 24))
        peak_hour = f"{peak_dt.hour:02d}:00"
    
    hx, hy = 360, 280
    hw, hh = 280, 300
    draw.rectangle((hx, hy, hx + hw, hy + hh), fill=COLORS["yellow"], outline=COLORS["ink_primary"], width=2)
    # Highlight decor
    draw.rectangle((hx + 100, hy - 10, hx + 180, hy + 10), fill="rgba(255,255,255,0.6)")
    draw.text((hx + 40, hy + 50), "✨ Highlight Time", fill=COLORS["ink_secondary"], font=hand_font_md)
    draw.text((hx + 50, hy + 110), peak_hour, fill=COLORS["ink_primary"], font=_load_font(64, "bold"))
    draw.text((hx + 45, hy + 210), "(此刻，世界色彩斑斓)", fill=COLORS["ink_secondary"], font=hand_font_sm)

    # 5. Trend Chart Section
    chart_y = 620
    draw.text((cx + 50, chart_y), "📊 24H 活跃轨迹", fill=COLORS["ink_primary"], font=label_font)
    
    chart_box = (cx + 50, chart_y + 40, cx + cw - 50, chart_y + 240)
    draw.rectangle(chart_box, fill="#ffffff", outline=COLORS["ink_primary"], width=1)
    # Lined paper effect inside chart
    for ly in range(chart_box[1] + 20, chart_box[3], 20):
        draw.line((chart_box[0], ly, chart_box[2], ly), fill="#f0f0f0", width=1)

    if trend:
        max_val = max(t["count"] for t in trend) or 1
        t_w = (chart_box[2] - chart_box[0]) / len(trend)
        t_h = chart_box[3] - chart_box[1]
        for idx, bucket in enumerate(trend):
            val = bucket["count"]
            bh = int((t_h - 40) * (val / max_val)) + 2
            x0 = int(chart_box[0] + idx * t_w + 2)
            x1 = int(x0 + t_w - 4)
            y0 = chart_box[3] - bh
            # Crayon bar look: rounded top
            draw.rounded_rectangle((x0, y0, x1, chart_box[3]), radius=5, fill=COLORS["green"] if idx % 2 == 0 else COLORS["blue"])
            # X-axis label
            if idx % 4 == 0:
                # Calculate bucket hour
                b_dt = start_dt + timedelta(hours=(idx * (end_dt - start_dt).total_seconds() / 3600 / 24))
                draw.text((x0, chart_box[3] + 5), f"{b_dt.hour}", fill=COLORS["ink_secondary"], font=hand_font_sm)

    # 6. Top Apps (Topic Style)
    topics_y = 920
    draw.text((cx + 50, topics_y), "📝 Top 应用排行", fill=COLORS["ink_primary"], font=label_font)
    
    app_list = apps[:6]
    for i, app in enumerate(app_list):
        ay = topics_y + 50 + i * 60
        # Checkbox
        draw.rectangle((cx + 60, ay + 5, cx + 85, ay + 30), outline=COLORS["ink_primary"], width=2)
        # Tick
        draw.line((cx + 62, ay + 15, cx + 70, ay + 25), fill=COLORS["orange"], width=3)
        draw.line((cx + 70, ay + 25, cx + 83, ay + 8), fill=COLORS["orange"], width=3)
        
        # Title with highlighter effect
        tw = draw.textlength(app["app"], font=hand_font_lg)
        draw.rectangle((cx + 105, ay + 20, cx + 105 + tw, ay + 35), fill=COLORS["pink"])
        draw.text((cx + 100, ay), app["app"], fill=COLORS["ink_primary"], font=hand_font_lg)
        
        # Duration
        draw.text((cx + cw - 200, ay + 5), _format_duration(app["duration"]), fill=COLORS["ink_secondary"], font=hand_font_md)

    # 7. Input Share (User Card Style)
    share_y = topics_y
    share_x = cx + cw / 2 + 50
    draw.text((share_x, share_y), "🎨 输入分布", fill=COLORS["ink_primary"], font=label_font)
    
    input_stats = build_input_stats_by_top_apps(summary=summary, start=start_dt, end=end_dt, top_n=5)
    if input_stats:
        max_total = max(_sum_input(item) for item in input_stats) or 1
        for i, item in enumerate(input_stats):
            iy = share_y + 50 + i * 80
            # Card
            card_box = (share_x, iy, cx + cw - 50, iy + 70)
            draw.rounded_rectangle(card_box, radius=8, fill=COLORS["white"], outline=COLORS["ink_primary"], width=1)
            
            # Progress bar
            total = _sum_input(item)
            ratio = total / max_total
            bar_w = (card_box[2] - card_box[0] - 40)
            draw.rectangle((card_box[0] + 20, iy + 45, card_box[0] + 20 + int(bar_w * ratio), iy + 60), fill=COLORS["purple"])
            
            draw.text((card_box[0] + 20, iy + 10), item["app"], fill=COLORS["ink_primary"], font=hand_font_md)
            draw.text((card_box[2] - 100, iy + 10), f"{total}", fill=COLORS["ink_secondary"], font=hand_font_sm)

    # 8. Footer
    draw.line((cx + 50, cy + ch - 80, cx + cw - 50, cy + ch - 80), fill=COLORS["ink_secondary"], width=2, joint="curve")
    footer_text = "Generated by ActivityWatch Report System"
    tw = draw.textlength(footer_text, font=hand_font_md)
    draw.text(((width - tw) / 2, cy + ch - 60), footer_text, fill=COLORS["ink_secondary"], font=hand_font_md)

    filename = f"aw-report-{datetime.now().strftime('%Y%m%d')}.png"
    output_path = os.path.join(output_dir, filename)
    
    # Convert to RGB before saving to PNG (optional, but base is RGBA now)
    final_image = base_image.convert("RGB")
    final_image.save(output_path)
    return output_path


def generate_report_by_config(cfg: ReportConfig) -> str:
    summary = _build_summary_for_mode(cfg)
    if "error" in summary:
        return ""

    generate_report_image(summary, cfg.output_dir)
    _build_report_json(summary, cfg.output_dir)

    return os.path.join(
        cfg.output_dir, f"aw-report-{datetime.now().strftime('%Y%m%d')}.png"
    )
