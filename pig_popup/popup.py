"""弹窗核心逻辑：必须点击「我是猪」图片按钮才能关闭的确认窗口。"""
import os
import random
import sys
import tkinter as tk

try:
    from PIL import Image, ImageTk
except ImportError:
    print("缺少 Pillow，请先安装：pip install pillow", file=sys.stderr)
    sys.exit(1)

# 存活的弹窗集合，全部关闭后程序退出
_live_popups = set()
_root = None

WIDTH, HEIGHT = 320, 170
SPAWN_PER_CANCEL = 2


def resource_path(name):
    """定位资源文件，兼容 PyInstaller 打包后的 _MEIPASS 路径。"""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def init(root: tk.Tk):
    """绑定根窗口，用于全部弹窗关闭后退出程序。"""
    global _root
    _root = root


def _clamp(x, y, sw, sh):
    """把窗口位置限制在屏幕范围内。"""
    x = max(0, min(x, sw - WIDTH))
    y = max(0, min(y, sh - HEIGHT))
    return x, y


class PigPopup:
    """单个「我是猪」确认弹窗。

    行为：
    - 点「我是猪」→ 关闭本窗口
    - 点「取消」或点 X → 保留本窗口，额外弹出 SPAWN_PER_CANCEL 个新窗口
    """

    def __init__(self, x=None, y=None):
        self.win = tk.Toplevel()
        self.win.title("郑重确认")
        self.win.geometry(f"{WIDTH}x{HEIGHT}")
        self.win.resizable(False, False)
        self.win.attributes("-topmost", True)  # 强制置顶，无法被忽略
        self.win.protocol("WM_DELETE_WINDOW", self._on_cancel)  # 拦截 X 按钮

        sw, sh = (self.win.winfo_screenwidth(), self.win.winfo_screenheight())
        if x is None or y is None:
            x, y = (sw - WIDTH) // 2, (sh - HEIGHT) // 2  # 首个窗口居中
        else:
            x, y = _clamp(x + random.randint(-200, 200), y + random.randint(-150, 150), sw, sh)
        self.win.geometry(f"+{x}+{y}")

        # 猪图片（替代「猪」字），两处各用一份尺寸，持有引用防止被 GC
        self._pig_label_photo = ImageTk.PhotoImage(
            Image.open(resource_path("pig.png")).resize((40, 40)))
        self._pig_btn_photo = ImageTk.PhotoImage(
            Image.open(resource_path("pig.png")).resize((36, 36)))

        row = tk.Frame(self.win)
        row.pack(pady=(35, 15))
        tk.Label(row, text="请大声承认：你是", font=("Microsoft YaHei", 14)).pack(side="left")
        tk.Label(row, image=self._pig_label_photo).pack(side="left")

        tk.Button(self.win, text="我是", image=self._pig_btn_photo, compound="right",
                  font=("Microsoft YaHei", 11), cursor="hand2",
                  command=self._on_confirm).pack(side="left", padx=25)
        tk.Button(self.win, text="取消", width=10, font=("Microsoft YaHei", 11),
                  command=self._on_cancel).pack(side="right", padx=25)

        _live_popups.add(self)

    def _on_confirm(self):
        """点「我是猪」→ 关闭本窗口，全部关完后退出程序。"""
        if not self.win.winfo_exists():
            return  # 窗口已被销毁
        _live_popups.discard(self)
        self.win.destroy()
        _check_exit()

    def _on_cancel(self):
        """点「取消」或点 X → 保留本窗口，再弹 SPAWN_PER_CANCEL 个新窗口。"""
        try:
            x, y = self.win.winfo_x(), self.win.winfo_y()
        except tk.TclError:
            return  # 窗口已被销毁，直接放弃
        for _ in range(SPAWN_PER_CANCEL):
            PigPopup(x=x, y=y)


def _check_exit():
    if _root is not None and not _live_popups:
        try:
            _root.destroy()
        except tk.TclError:
            pass
