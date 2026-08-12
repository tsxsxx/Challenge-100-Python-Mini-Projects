"""
自动点击系统 — PySide6 实现
"""
import os
import time
import threading

import pyautogui
import keyboard
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QGroupBox, QLabel, QLineEdit,
    QPushButton, QComboBox, QRadioButton, QButtonGroup,
    QCheckBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QGridLayout, QVBoxLayout, QHBoxLayout,
    QMessageBox, QAbstractItemView,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont

from ClickEngine import ClickEngine, ClickTask

# 各组边框样式
GROUP_STYLE = "QGroupBox { border: 1px solid gray; padding-top: 20px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }"


class System(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("自动点击系统")
        self.resize(780, 540)

        # 点击引擎
        self.engine: ClickEngine | None = None

        # 运行计时
        self._start_time: float = 0.0
        self._run_timer = QTimer(self)
        self._run_timer.timeout.connect(self._tick)
        self._step_timer = QTimer(self)
        self._step_timer.setSingleShot(True)
        self._step_timer.timeout.connect(self._schedule_step)

        # 窗口状态
        self._closing = False

        # 快捷键
        self._setting_hotkey: str | None = None
        self._start_hotkey = "Ctrl+Shift+S"
        self._stop_hotkey = "Ctrl+Shift+X"

        self.create_widgets()
        self._register_hotkeys()

    # ==================== 主布局 ====================
    def create_widgets(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QGridLayout(central)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)

        # 列拉伸：第0列固定，第1列扩展
        main_layout.setColumnStretch(0, 0)
        main_layout.setColumnStretch(1, 1)
        # 行拉伸：第0行扩展，第1行自适应
        main_layout.setRowStretch(0, 1)
        main_layout.setRowStretch(1, 0)

        self._create_click_frame(main_layout)
        self._create_list_frame(main_layout)
        self._create_status_frame(main_layout)
        self._create_control_frame(main_layout)

    # ==================== 点击设置 ====================
    def _create_click_frame(self, parent_layout: QGridLayout):
        group = QGroupBox("点击设置")
        group.setStyleSheet(GROUP_STYLE)
        group.setFixedWidth(280)
        layout = QGridLayout(group)
        layout.setSpacing(4)
        layout.setContentsMargins(10, 22, 10, 8)

        # 第1行：X Y 拾取
        layout.addWidget(QLabel("X:"), 0, 0, Qt.AlignRight)
        self.x_entry = QLineEdit()
        self.x_entry.setFixedWidth(65)
        layout.addWidget(self.x_entry, 0, 1)

        layout.addWidget(QLabel("Y:"), 0, 2, Qt.AlignRight)
        self.y_entry = QLineEdit()
        self.y_entry.setFixedWidth(65)
        layout.addWidget(self.y_entry, 0, 3)

        self.pick_btn = QPushButton("拾取")
        self.pick_btn.setFixedWidth(50)
        self.pick_btn.clicked.connect(self._pick_position)
        layout.addWidget(self.pick_btn, 0, 4)

        # 第2行：点击方式
        layout.addWidget(QLabel("点击方式:"), 1, 0, Qt.AlignRight)
        self.click_method = QComboBox()
        self.click_method.addItems(["左键", "右键", "中键"])
        self.click_method.setFixedWidth(130)
        layout.addWidget(self.click_method, 1, 1, 1, 4)

        # 第3行：点击类型
        layout.addWidget(QLabel("点击类型:"), 2, 0, Qt.AlignRight)
        self.click_type = QComboBox()
        self.click_type.addItems(["单击", "双击", "按下", "释放"])
        self.click_type.setFixedWidth(130)
        layout.addWidget(self.click_type, 2, 1, 1, 4)

        # 第4行：时间间隔
        layout.addWidget(QLabel("间隔(秒):"), 3, 0, Qt.AlignRight)
        self.interval_entry = QLineEdit("1.0")
        self.interval_entry.setFixedWidth(80)
        layout.addWidget(self.interval_entry, 3, 1, 1, 4)

        # 第5-7行：点击次数
        layout.addWidget(QLabel("点击次数:"), 4, 0, Qt.AlignRight | Qt.AlignTop)
        count_widget = QWidget()
        count_layout = QVBoxLayout(count_widget)
        count_layout.setContentsMargins(0, 0, 0, 0)
        count_layout.setSpacing(2)

        self.count_group = QButtonGroup(self)

        fixed_row = QWidget()
        fixed_layout = QHBoxLayout(fixed_row)
        fixed_layout.setContentsMargins(0, 0, 0, 0)
        fixed_rb = QRadioButton("固定次数")
        self.count_group.addButton(fixed_rb, 0)  # id=0 → "fixed"
        fixed_layout.addWidget(fixed_rb)
        self.fixed_count_entry = QLineEdit("1")
        self.fixed_count_entry.setFixedWidth(60)
        fixed_layout.addWidget(self.fixed_count_entry)
        fixed_layout.addStretch()
        count_layout.addWidget(fixed_row)

        infinite_rb = QRadioButton("无限循环")
        self.count_group.addButton(infinite_rb, 1)  # id=1 → "infinite"
        count_layout.addWidget(infinite_rb)

        fixed_rb.setChecked(True)  # 默认固定次数
        count_layout.addStretch()
        layout.addWidget(count_widget, 4, 1, 1, 4)

        parent_layout.addWidget(group, 0, 0)

    def _get_count_mode(self) -> str:
        """将 QButtonGroup id 转为模式字符串"""
        checked_id = self.count_group.checkedId()
        if checked_id == 1:
            return "infinite"
        return "fixed"

    # ==================== 点击列表 ====================
    def _create_list_frame(self, parent_layout: QGridLayout):
        group = QGroupBox("点击列表")
        group.setStyleSheet(GROUP_STYLE)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(10, 22, 10, 8)
        layout.setSpacing(6)

        # 表格
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["序号", "坐标", "点击方式", "间隔时间"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 45)
        self.table.setColumnWidth(3, 70)
        layout.addWidget(self.table)

        # 操作按钮
        btn_widget = QWidget()
        btn_layout = QHBoxLayout(btn_widget)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(4)

        self.add_btn = QPushButton("添加")
        self.add_btn.clicked.connect(self._add_task)
        btn_layout.addWidget(self.add_btn)

        self.del_btn = QPushButton("删除")
        self.del_btn.clicked.connect(self._delete_task)
        btn_layout.addWidget(self.del_btn)

        self.up_btn = QPushButton("上移")
        self.up_btn.clicked.connect(self._move_up)
        btn_layout.addWidget(self.up_btn)

        self.down_btn = QPushButton("下移")
        self.down_btn.clicked.connect(self._move_down)
        btn_layout.addWidget(self.down_btn)

        btn_layout.addStretch()
        layout.addWidget(btn_widget)

        parent_layout.addWidget(group, 0, 1)

    # ==================== 运行状态 ====================
    def _create_status_frame(self, parent_layout: QGridLayout):
        group = QGroupBox("运行状态")
        group.setStyleSheet(GROUP_STYLE)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(12, 22, 12, 8)
        layout.setSpacing(4)

        self.status_label = QLabel("状态: 停止")
        self.status_label.setFont(QFont("Arial", 11))
        layout.addWidget(self.status_label)

        self.click_count_label = QLabel("已点击: 0")
        layout.addWidget(self.click_count_label)

        self.run_time_label = QLabel("运行时间: 00:00:00")
        layout.addWidget(self.run_time_label)

        layout.addStretch()
        parent_layout.addWidget(group, 1, 0)

    # ==================== 控制 ====================
    def _create_control_frame(self, parent_layout: QGridLayout):
        group = QGroupBox("控制")
        group.setStyleSheet(GROUP_STYLE)
        layout = QGridLayout(group)
        layout.setContentsMargins(12, 22, 12, 8)
        layout.setSpacing(6)

        # 开始 / 停止
        self.start_btn = QPushButton("开始")
        self.start_btn.setStyleSheet("QPushButton { background-color: green; color: white; }")
        self.start_btn.clicked.connect(self._start)
        layout.addWidget(self.start_btn, 0, 0)

        self.stop_btn = QPushButton("停止")
        self.stop_btn.setStyleSheet("QPushButton { background-color: red; color: white; }")
        self.stop_btn.clicked.connect(self._stop)
        layout.addWidget(self.stop_btn, 0, 1)

        # 窗口置顶
        self.topmost_check = QCheckBox("窗口置顶")
        self.topmost_check.toggled.connect(self.toggle_topmost)
        layout.addWidget(self.topmost_check, 1, 0, 1, 2)

        # 启动快捷键
        layout.addWidget(QLabel("启动快捷键:"), 2, 0, Qt.AlignRight)
        self.start_hotkey_entry = QLineEdit("Ctrl+Shift+S")
        self.start_hotkey_entry.setReadOnly(True)
        self.start_hotkey_entry.setFixedWidth(120)
        layout.addWidget(self.start_hotkey_entry, 2, 1)

        self.set_start_hotkey_btn = QPushButton("设置")
        self.set_start_hotkey_btn.setFixedWidth(50)
        self.set_start_hotkey_btn.clicked.connect(lambda: self._start_hotkey_capture("start"))
        layout.addWidget(self.set_start_hotkey_btn, 2, 2)

        # 停止快捷键
        layout.addWidget(QLabel("停止快捷键:"), 3, 0, Qt.AlignRight)
        self.stop_hotkey_entry = QLineEdit("Ctrl+Shift+X")
        self.stop_hotkey_entry.setReadOnly(True)
        self.stop_hotkey_entry.setFixedWidth(120)
        layout.addWidget(self.stop_hotkey_entry, 3, 1)

        self.set_stop_hotkey_btn = QPushButton("设置")
        self.set_stop_hotkey_btn.setFixedWidth(50)
        self.set_stop_hotkey_btn.clicked.connect(lambda: self._start_hotkey_capture("stop"))
        layout.addWidget(self.set_stop_hotkey_btn, 3, 2)

        parent_layout.addWidget(group, 1, 1)

    # ==================== 事件回调 ====================
    def _on_engine_click(self, count: int):
        self.click_count_label.setText(f"已点击: {count}")

    def _on_engine_status_change(self, status: str):
        if status == "stopped":
            self._stop_timer()
            self._cancel_step()
            self.start_btn.setEnabled(True)
            self.status_label.setText("状态: 停止")
            self.status_label.setStyleSheet("")

    # ==================== 窗口事件 ====================
    def toggle_topmost(self, checked: bool):
        self.setWindowFlag(Qt.WindowStaysOnTopHint, checked)
        self.show()  # setWindowFlag 后需要 show()

    def closeEvent(self, event):
        self._closing = True
        self._stop()
        os._exit(0)

    # ==================== 列表操作 ====================
    def _add_task(self):
        try:
            x = int(self.x_entry.text())
            y = int(self.y_entry.text())
        except ValueError:
            QMessageBox.warning(self, "输入错误", "X/Y 坐标必须为整数")
            return

        try:
            interval = float(self.interval_entry.text())
            if interval <= 0:
                raise ValueError
        except ValueError:
            QMessageBox.warning(self, "输入错误", "间隔(秒)必须为正数")
            return

        method = self.click_method.currentText()
        click_type = self.click_type.currentText()

        row = self.table.rowCount()
        self.table.insertRow(row)

        coord_str = f"({x}, {y})"
        method_str = f"{method}{click_type}"
        seq = row + 1

        # 显示列: 序号, 坐标, 点击方式, 间隔时间
        self.table.setItem(row, 0, QTableWidgetItem(str(seq)))
        self.table.setItem(row, 1, QTableWidgetItem(coord_str))
        self.table.setItem(row, 2, QTableWidgetItem(method_str))
        self.table.setItem(row, 3, QTableWidgetItem(f"{interval}s"))

        # 隐藏数据存储 method 和 click_type（用 UserRole）
        self.table.item(row, 0).setData(Qt.UserRole, method)
        self.table.item(row, 0).setData(Qt.UserRole + 1, click_type)

        self._renumber()

    def _delete_task(self):
        current = self.table.currentRow()
        if current < 0:
            QMessageBox.information(self, "提示", "请先选择要删除的行")
            return
        self.table.removeRow(current)
        self._renumber()

    def _move_up(self):
        current = self.table.currentRow()
        if current <= 0:
            return
        self._swap_rows(current, current - 1)
        self.table.selectRow(current - 1)

    def _move_down(self):
        current = self.table.currentRow()
        if current < 0 or current >= self.table.rowCount() - 1:
            return
        self._swap_rows(current, current + 1)
        self.table.selectRow(current + 1)

    def _swap_rows(self, r1: int, r2: int):
        """交换两行"""
        for col in range(4):
            item1 = self.table.takeItem(r1, col)
            item2 = self.table.takeItem(r2, col)
            self.table.setItem(r1, col, item2)
            self.table.setItem(r2, col, item1)
        self._renumber()

    def _renumber(self):
        for i in range(self.table.rowCount()):
            self.table.item(i, 0).setText(str(i + 1))

    # ==================== 坐标拾取 ====================
    def _pick_position(self):
        if getattr(self, "_pick_handler_id", None) is not None:
            return

        self.pick_btn.setText("拾取中...")
        self.pick_btn.setEnabled(False)
        self.status_label.setText("状态: 将鼠标移到目标位置，按 F8 拾取，按 Esc 取消")

        def on_key(event):
            if event.event_type != "down":
                return
            if event.name == "f8":
                x, y = pyautogui.position()
                self._cleanup_pick_hook()
                self._on_pick_done(x, y)
            elif event.name == "esc":
                self._cleanup_pick_hook()
                self._on_pick_cancel()

        self._pick_handler_id = keyboard.on_press(on_key)

    def _cleanup_pick_hook(self):
        if getattr(self, "_pick_handler_id", None) is not None:
            try:
                keyboard.unhook(self._pick_handler_id)
            except Exception:
                pass
            self._pick_handler_id = None

    def _on_pick_done(self, x: int, y: int):
        self.x_entry.setText(str(x))
        self.y_entry.setText(str(y))
        self._reset_pick_ui()
        self._add_task()

    def _on_pick_cancel(self):
        self._reset_pick_ui()

    def _reset_pick_ui(self):
        self.pick_btn.setText("拾取")
        self.pick_btn.setEnabled(True)
        self.status_label.setText("状态: 停止")

    # ==================== 开始 / 停止 ====================
    def _start(self):
        tasks = self._get_tasks_from_table()
        if not tasks:
            QMessageBox.warning(self, "无任务", "请先添加至少一个点击任务")
            return

        count_mode = self._get_count_mode()
        fixed_count = 1
        if count_mode == "fixed":
            try:
                fixed_count = int(self.fixed_count_entry.text())
                if fixed_count <= 0:
                    raise ValueError
            except ValueError:
                QMessageBox.warning(self, "输入错误", "固定次数必须为正整数")
                return

        self.engine = ClickEngine()
        self.engine.on_click = self._on_engine_click
        self.engine.on_status_change = self._on_engine_status_change
        self.engine.configure(tasks, count_mode=count_mode, fixed_count=fixed_count)
        self.engine.start()

        self.start_btn.setEnabled(False)
        self.status_label.setText("状态: 运行中")
        self.status_label.setStyleSheet("color: green;")
        self._start_timer()
        self._schedule_step()

    def _stop(self):
        if self.engine is not None:
            self.engine.stop()
        self._stop_timer()
        self._cancel_step()
        self.start_btn.setEnabled(True)
        self.status_label.setText("状态: 停止")
        self.status_label.setStyleSheet("")

    def _schedule_step(self):
        if self._closing or self.engine is None or not self.engine.is_running:
            return
        try:
            interval = self.engine.step()
        except Exception:
            self.engine.stop()
            self._stop_timer()
            self.start_btn.setEnabled(True)
            self.status_label.setText("状态: 停止")
            self.status_label.setStyleSheet("")
            return
        if self.engine.is_running and interval is not None:
            self._step_timer.start(int(interval * 1000))

    def _cancel_step(self):
        if self._step_timer.isActive():
            self._step_timer.stop()

    # ==================== 运行计时 ====================
    def _start_timer(self):
        self._start_time = time.time()
        self._run_timer.start(200)

    def _tick(self):
        if self._closing or self.engine is None or not self.engine.is_running:
            return
        elapsed = int(time.time() - self._start_time)
        h, r = divmod(elapsed, 3600)
        m, s = divmod(r, 60)
        self.run_time_label.setText(f"运行时间: {h:02d}:{m:02d}:{s:02d}")

    def _stop_timer(self):
        self._run_timer.stop()

    # ==================== 任务数据转换 ====================
    def _get_tasks_from_table(self) -> list[ClickTask]:
        tasks = []
        for row in range(self.table.rowCount()):
            seq = int(self.table.item(row, 0).text())
            coord_str = self.table.item(row, 1).text()      # "(x, y)"
            interval_str = self.table.item(row, 3).text()   # "1.0s"
            method = self.table.item(row, 0).data(Qt.UserRole) or "左键"
            click_type = self.table.item(row, 0).data(Qt.UserRole + 1) or "单击"

            coord_str = coord_str.strip("()")
            parts = coord_str.split(",")
            x = int(parts[0].strip())
            y = int(parts[1].strip())

            interval = float(interval_str.rstrip("s"))

            tasks.append(ClickTask(
                index=seq, x=x, y=y,
                method=method,
                click_type=click_type,
                interval=interval,
                note="",
            ))
        return tasks

    # ==================== 快捷键 ====================
    def _register_hotkeys(self):
        try:
            self._start_hotkey_id = keyboard.add_hotkey(self._start_hotkey, self._start)
            self._stop_hotkey_id = keyboard.add_hotkey(self._stop_hotkey, self._stop)
        except Exception:
            pass

    def _start_hotkey_capture(self, which: str):
        if self._setting_hotkey is not None:
            return

        self._setting_hotkey = which
        if which == "start":
            self.start_hotkey_entry.setReadOnly(False)
            self.start_hotkey_entry.setText("按下快捷键...")
            self.set_start_hotkey_btn.setText("等待中...")
            self.set_start_hotkey_btn.setEnabled(False)
        else:
            self.stop_hotkey_entry.setReadOnly(False)
            self.stop_hotkey_entry.setText("按下快捷键...")
            self.set_stop_hotkey_btn.setText("等待中...")
            self.set_stop_hotkey_btn.setEnabled(False)

        self._capture_thread = threading.Thread(target=self._capture_hotkey, daemon=True)
        self._capture_thread.start()

    def _capture_hotkey(self):
        try:
            record = keyboard.record(until="enter")
            combo = "+".join(sorted(set(
                e.name.replace("ctrl", "Ctrl").replace("shift", "Shift").replace("alt", "Alt")
                for e in record
                if e.event_type == "down" and e.name not in ("enter",)
            )))
            if not combo:
                combo = "未设置"
        except Exception:
            combo = "未设置"

        self._on_hotkey_captured(combo)

    def _on_hotkey_captured(self, combo: str):
        which = self._setting_hotkey
        self._setting_hotkey = None

        try:
            if hasattr(self, "_start_hotkey_id"):
                keyboard.remove_hotkey(self._start_hotkey_id)
        except Exception:
            pass
        try:
            if hasattr(self, "_stop_hotkey_id"):
                keyboard.remove_hotkey(self._stop_hotkey_id)
        except Exception:
            pass

        if which == "start":
            self._start_hotkey = combo
            self.start_hotkey_entry.setText(combo)
            self.start_hotkey_entry.setReadOnly(True)
            self.set_start_hotkey_btn.setText("设置")
            self.set_start_hotkey_btn.setEnabled(True)
        else:
            self._stop_hotkey = combo
            self.stop_hotkey_entry.setText(combo)
            self.stop_hotkey_entry.setReadOnly(True)
            self.set_stop_hotkey_btn.setText("设置")
            self.set_stop_hotkey_btn.setEnabled(True)

        self._register_hotkeys()
