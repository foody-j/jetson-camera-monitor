#!/usr/bin/env python3
"""
대기 화면
"""

import tkinter as tk
from datetime import datetime

class StandbyScreen:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("SFLAB")
        self.root.attributes('-fullscreen', True)
        self.root.configure(bg='black')

        # ESC로 종료
        self.root.bind('<Escape>', lambda e: self.root.destroy())

        # 메인 프레임
        main_frame = tk.Frame(self.root, bg='black')
        main_frame.place(relx=0.5, rely=0.5, anchor='center')

        # 로고
        title_label = tk.Label(
            main_frame,
            text="SFLAB",
            font=('Arial', 120, 'bold'),
            bg='black',
            fg='#4A90D9'
        )
        title_label.pack(pady=(0, 80))

        # 시간 표시
        self.time_label = tk.Label(
            main_frame,
            text="",
            font=('Arial', 32),
            bg='black',
            fg='#666666'
        )
        self.time_label.pack()

        self.update_display()

    def update_display(self):
        now = datetime.now()
        self.time_label.config(text=now.strftime("%Y-%m-%d  %H:%M:%S"))
        self.root.after(1000, self.update_display)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    print("[대기화면] 시작 - ESC로 종료")
    app = StandbyScreen()
    app.run()
