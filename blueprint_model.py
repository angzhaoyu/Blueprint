"""
蓝图数据模型 - 持久化 + 页面/框管理
"""
import json
import shutil
from pathlib import Path


class Box:
    def __init__(self, label="", points=None, box_type="identity", target_page=None):
        self.label = label
        self.points = points or [[0, 0], [0, 0]]
        self.box_type = box_type          # "identity" | "link"
        self.target_page = target_page    # 仅 link 使用

    def to_dict(self):
        d = {"label": self.label, "points": self.points, "box_type": self.box_type}
        if self.box_type == "link":
            d["target_page"] = self.target_page
        return d

    @classmethod
    def from_dict(cls, data):
        return cls(
            label=data.get("label", ""),
            points=data.get("points", [[0, 0], [0, 0]]),
            box_type=data.get("box_type", "identity"),
            target_page=data.get("target_page"),
        )


class Page:
    def __init__(self, page_id, name_cn="", name_en="", is_popup=False, image_path=""):
        self.page_id = page_id
        self.name_cn = name_cn
        self.name_en = name_en
        self.is_popup = is_popup
        self.image_path = image_path
        self.boxes = []

    @property
    def display_name(self):
        return self.name_cn or self.name_en or self.page_id

    def to_dict(self):
        return {
            "name_cn": self.name_cn,
            "name_en": self.name_en,
            "is_popup": self.is_popup,
            "image": self.image_path,
            "boxes": [b.to_dict() for b in self.boxes],
        }

    @classmethod
    def from_dict(cls, page_id, data):
        p = cls(page_id,
                name_cn=data.get("name_cn", ""),
                name_en=data.get("name_en", ""),
                is_popup=data.get("is_popup", False),
                image_path=data.get("image", ""))
        p.boxes = [Box.from_dict(b) for b in data.get("boxes", [])]
        return p


class BlueprintProject:
    def __init__(self, name, project_dir):
        self.name = name
        self.project_dir = Path(project_dir)
        self.pages = {}
        self._page_order = []

    @property
    def config_path(self):
        return self.project_dir / "project.json"

    @property
    def images_dir(self):
        return self.project_dir / "images"

    # ---------- 创建 / 保存 / 加载 ----------
    def create(self):
        self.project_dir.mkdir(parents=True, exist_ok=True)
        self.images_dir.mkdir(exist_ok=True)
        self.save()

    def save(self):
        data = {
            "project_name": self.name,
            "page_order": self._page_order,
            "pages": {pid: self.pages[pid].to_dict() for pid in self._page_order},
        }
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, project_dir):
        project_dir = Path(project_dir)
        with open(project_dir / "project.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        proj = cls(data["project_name"], project_dir)
        proj._page_order = data.get("page_order", [])
        for pid in proj._page_order:
            if pid in data.get("pages", {}):
                proj.pages[pid] = Page.from_dict(pid, data["pages"][pid])
        return proj

    # ---------- 自动 ID ----------
    def _gen_id(self):
        i = 1
        while f"page_{i:03d}" in self.pages:
            i += 1
        return f"page_{i:03d}"

    # ---------- 导入 ----------
    def import_image(self, source_path):
        src = Path(source_path)
        pid = self._gen_id()
        dest = f"{pid}{src.suffix}"
        shutil.copy2(src, self.images_dir / dest)
        page = Page(pid, name_en=pid, image_path=f"images/{dest}")
        self.pages[pid] = page
        self._page_order.append(pid)
        return page

    def import_screenshot(self, pixmap):
        pid = self._gen_id()
        dest = f"{pid}.png"
        pixmap.save(str(self.images_dir / dest), "PNG")
        page = Page(pid, name_en=pid, image_path=f"images/{dest}")
        self.pages[pid] = page
        self._page_order.append(pid)
        return page

    # ---------- 重命名 ----------
    def rename_page_image(self, page_id, new_en):
        page = self.pages.get(page_id)
        if not page or not new_en:
            return
        old = self.project_dir / page.image_path
        if not old.exists():
            return
        new_name = f"{new_en}{old.suffix}"
        new_path = self.images_dir / new_name
        if old == new_path:
            return
        if new_path.exists():
            new_name = f"{new_en}_{page_id}{old.suffix}"
            new_path = self.images_dir / new_name
        old.rename(new_path)
        page.image_path = f"images/{new_name}"

    # ---------- 删除 ----------
    def remove_page(self, page_id):
        if page_id not in self.pages:
            return
        img = self.project_dir / self.pages[page_id].image_path
        if img.exists():
            img.unlink()
        del self.pages[page_id]
        self._page_order.remove(page_id)

    def get_image_abs_path(self, page_id):
        if page_id in self.pages:
            return str(self.project_dir / self.pages[page_id].image_path)
        return None

    def get_page_names(self):
        return {pid: self.pages[pid].display_name for pid in self._page_order}