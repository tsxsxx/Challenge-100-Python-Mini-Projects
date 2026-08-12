"""
点击执行引擎 — 单线程，由 System 通过 QTimer 驱动
"""
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

import pyautogui

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.01


@dataclass
class ClickTask:
    """单次点击任务"""
    index: int
    x: int
    y: int
    method: str          # "左键" | "右键" | "中键"
    click_type: str      # "单击" | "双击" | "按下" | "释放"
    interval: float      # 间隔（秒）
    note: str = ""


class ClickEngine:
    """单线程点击引擎，每次 step() 执行一个点击并返回下次等待秒数"""

    def __init__(self):
        self._stop_event = threading.Event()
        self.tasks: list[ClickTask] = []
        self.count_mode = "fixed"
        self.fixed_count = 1
        self._total_clicks = 0
        self._running = False
        self._round = 0
        self._task_index = 0

        self.on_click: Optional[Callable[[int], None]] = None
        self.on_status_change: Optional[Callable[[str], None]] = None

    # ---- 配置 ----
    def configure(self, tasks, count_mode="fixed", fixed_count=1):
        self.tasks = list(tasks)
        self.count_mode = count_mode
        self.fixed_count = fixed_count

    # ---- 生命周期 ----
    def start(self):
        self._stop_event.clear()
        self._total_clicks = 0
        self._round = 0
        self._task_index = 0
        self._running = True

    def stop(self):
        self._stop_event.set()
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running and not self._stop_event.is_set()

    @property
    def total_clicks(self) -> int:
        return self._total_clicks

    # ---- 单步执行 ----
    def step(self) -> Optional[float]:
        if not self._running or self._stop_event.is_set():
            self._finish()
            return None

        try:
            interval = self._do_step()
        except Exception:
            self._finish()
            return None

        if not self._running:
            self._finish()
            return None

        return interval

    def _do_step(self) -> Optional[float]:
        if self.count_mode == "fixed":
            return self._step_fixed()
        else:
            return self._step_infinite()

    def _step_fixed(self) -> Optional[float]:
        if self._round >= self.fixed_count:
            self._release_all()
            self._running = False
            return None

        if self._task_index >= len(self.tasks):
            self._task_index = 0
            self._round += 1
            if self._round >= self.fixed_count:
                self._release_all()
                self._running = False
                return None

        task = self.tasks[self._task_index]
        self._do_click(task.x, task.y, task.method, task.click_type)
        self._total_clicks += 1
        self._notify_click()

        interval = max(task.interval, 0.01)
        self._task_index += 1
        return interval

    def _step_infinite(self) -> float:
        if self._task_index >= len(self.tasks):
            self._task_index = 0

        task = self.tasks[self._task_index]
        self._do_click(task.x, task.y, task.method, task.click_type)
        self._total_clicks += 1
        self._notify_click()

        interval = max(task.interval, 0.01)
        self._task_index += 1
        return interval

    # ---- 点击实现 ----
    def _do_click(self, x: int, y: int, method: str, click_type: str):
        btn = {"左键": "left", "右键": "right", "中键": "middle"}.get(method, "left")

        if click_type == "单击":
            pyautogui.click(x, y, button=btn)
        elif click_type == "双击":
            # 不用 pyautogui.doubleClick()，其底层 MOUSEEVENTF_LEFTCLICK
            # 组合标志在重复执行时失效。改为两次独立 click + 50ms 间隔
            pyautogui.click(x, y, button=btn)
            time.sleep(0.05)
            pyautogui.click(x, y, button=btn)
        elif click_type == "按下":
            pyautogui.mouseDown(x, y, button=btn)
        elif click_type == "释放":
            pyautogui.mouseUp(x, y, button=btn)

    def _release_all(self):
        """释放所有按键"""
        for btn in ("left", "right", "middle"):
            try:
                pyautogui.mouseUp(button=btn)
            except Exception:
                pass

    # ---- 内部辅助 ----
    def _finish(self):
        self._running = False
        self._notify_status("stopped")

    def _notify_click(self):
        if self.on_click:
            try:
                self.on_click(self._total_clicks)
            except Exception:
                pass

    def _notify_status(self, status: str):
        if self.on_status_change:
            try:
                self.on_status_change(status)
            except Exception:
                pass
