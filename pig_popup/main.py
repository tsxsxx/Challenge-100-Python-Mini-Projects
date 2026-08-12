"""入口：启动关不掉的「我是猪」弹窗。"""
import tkinter as tk

import popup


def main():
    root = tk.Tk()
    root.withdraw()  # 隐藏根窗口，只显示弹窗
    popup.init(root)
    popup.PigPopup()
    root.mainloop()


if __name__ == "__main__":
    main()
