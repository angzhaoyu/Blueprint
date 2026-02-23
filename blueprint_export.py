"""
blueprint_export.py
从蓝图 project.json 导出为 tasks/ 目录结构，兼容 StateManager

用法:
    python blueprint_export.py <蓝图项目目录> [输出目录]
    python blueprint_export.py ./blueprint/程序1
    python blueprint_export.py ./blueprint/程序1 ./tasks
"""

import json
import shutil
import sys
from pathlib import Path

try:
    from PIL import Image as PILImage
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


def get_image_size(path):
    """获取图片宽高"""
    if HAS_PIL:
        try:
            with PILImage.open(str(path)) as img:
                return img.size   # (w, h)
        except Exception:
            pass
    return 0, 0


def sanitize_name(name):
    """
    去除下划线和空格，确保和 StateManager 的 split('_') 解析兼容
    states  → key 只有 1 段（不能含下划线）
    change  → key 固定 3 段：from_to_seq
    """
    return name.replace("_", "").replace(" ", "").strip()


def export_blueprint(project_dir, output_dir=None):
    """
    读取蓝图 project.json，导出：
      tasks/
        pop-states/     弹出页面 身份图片 + json
        pop-change/     弹出页面 链接 json
        page-states/    普通页面 身份图片 + json
        page-change/    普通页面 链接 json
        states.txt      配置文件
    """
    project_dir = Path(project_dir).resolve()
    config_path = project_dir / "project.json"

    if not config_path.exists():
        print(f"❌ 找不到: {config_path}")
        return False

    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if output_dir is None:
        output_dir = project_dir.parent / "tasks"
    else:
        output_dir = Path(output_dir).resolve()

    # ---------- 创建目录 ----------
    for d in ("pop-states", "pop-change", "page-states", "page-change"):
        (output_dir / d).mkdir(parents=True, exist_ok=True)

    pages = data.get("pages", {})
    page_order = data.get("page_order", list(pages.keys()))

    # ---------- page_id → 安全英文名 ----------
    id_to_en = {}
    used_names = set()
    for pid in page_order:
        p = pages[pid]
        raw = p.get("name_en", "") or pid
        en = sanitize_name(raw)
        if not en:
            en = pid.replace("_", "")
        # 防重名
        base = en
        i = 2
        while en in used_names:
            en = f"{base}{i}"
            i += 1
        used_names.add(en)
        id_to_en[pid] = en

    # ---------- 收集 txt 各节内容 ----------
    txt = {
        "pop-states":  [],
        "pop-change":  [],
        "page-states": [],
        "page-change": [],
    }

    for pid in page_order:
        p = pages[pid]
        en_name = id_to_en[pid]
        cn_name = p.get("name_cn", "")
        is_popup = p.get("is_popup", False)
        image_rel = p.get("image", "")
        boxes = p.get("boxes", [])

        prefix = "pop" if is_popup else "page"
        src_img = project_dir / image_rel
        img_w, img_h = get_image_size(src_img)

        # ====== 身份框 → states ======
        identity_boxes = [b for b in boxes if b.get("box_type") == "identity"]
        if identity_boxes:
            states_dir = f"{prefix}-states"

            # 复制图片
            dst_img = output_dir / states_dir / f"{en_name}.png"
            if src_img.exists():
                shutil.copy2(src_img, dst_img)
                print(f"  📷 {src_img.name} → {states_dir}/{en_name}.png")

            # 生成 LabelMe JSON（所有身份框合在一个 json）
            shapes = []
            for b in identity_boxes:
                shapes.append({
                    "label": "state",
                     "text": "", 
                    "points": b["points"],
                    "group_id": None,
                    "shape_type": "rectangle",
                    "flags": {}
                })

            labelme = {
                "version": "0.4.29",
                "flags": {},
                "shapes": shapes,
                "imagePath": f"{en_name}.png",
                "imageData": None,
                "imageHeight": img_h,
                "imageWidth": img_w,
            }
            json_path = output_dir / states_dir / f"{en_name}.json"
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(labelme, f, ensure_ascii=False, indent=2)

            # txt 行
            comment = f" #{cn_name}" if cn_name else ""
            txt[states_dir].append(
                f'{en_name} = "tasks/{states_dir}/{en_name}"{comment}'
            )

        # ====== 链接框 → change ======
        link_boxes = [b for b in boxes if b.get("box_type") == "link"]
        if not link_boxes:
            continue

        change_dir = f"{prefix}-change"

        # 按目标页面分组
        target_groups = {}
        for b in link_boxes:
            tp = b.get("target_page")
            if not tp or tp not in pages:
                continue
            target_en = id_to_en[tp]
            if target_en not in target_groups:
                target_groups[target_en] = []
            target_groups[target_en].append(b)

        for target_en, grouped in target_groups.items():
            for idx, b in enumerate(grouped, 1):
                seq = f"{idx:02d}"
                change_name = f"{en_name}_{target_en}_{seq}"

                # 复制图片，文件名与 json 一致
                dst_change_img = output_dir / change_dir / f"{change_name}.png"
                if src_img.exists():
                    shutil.copy2(src_img, dst_change_img)
                    print(f"  📷 {src_img.name} → {change_dir}/{change_name}.png")

                labelme = {
                    "version": "0.4.29",
                    "flags": {},
                    "shapes": [
                        {
                            "label": b.get("label", change_name),
                            "text": "",
                            "points": b["points"],
                            "group_id": None,
                            "shape_type": "rectangle",
                            "flags": {}
                        }
                    ],
                    "imagePath": f"{change_name}.png",
                    "imageData": None,
                    "imageHeight": img_h,
                    "imageWidth": img_w,
                }
                json_path = output_dir / change_dir / f"{change_name}.json"
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(labelme, f, ensure_ascii=False, indent=2)

                txt[change_dir].append(
                    f'{change_name} = "tasks/{change_dir}/{change_name}"'
                )
                
    # ====== 生成 states.txt ======
    txt_path = output_dir / "states.txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        for section in ("pop-states", "pop-change", "page-states", "page-change"):
            f.write(f"#{section}\n")
            for line in txt[section]:
                f.write(f"{line}\n")
            f.write("\n")

    # ====== 统计 ======
    print(f"\n✅ 导出完成 → {output_dir}")
    print(f"   states.txt: {txt_path}")
    total = 0
    for section, lines in txt.items():
        if lines:
            print(f"   {section}: {len(lines)} 条")
            total += len(lines)
    print(f"   共计: {total} 条")
    return True


# ==================== 入口 ====================
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法:")
        print("  python blueprint_export.py <蓝图项目目录>")
        print("  python blueprint_export.py <蓝图项目目录> <输出目录>")
        print()
        print("例:")
        print("  python blueprint_export.py ./blueprint/幸福小渔村")
        print("  python blueprint_export.py ./blueprint/幸福小渔村 ./tasks")
        sys.exit(1)
    # python blueprint_export.py XYC2 ./XYC2
    proj = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else None
    export_blueprint(proj, out)