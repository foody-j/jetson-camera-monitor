#!/usr/bin/env python3
"""
대기 화면 - 카메라/시스템 점검 중 표시
"""

import tkinter as tk
from datetime import datetime
import time

class StandbyScreen:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("SFLAB 모니터링 시스템")
        self.root.attributes('-fullscreen', True)
        self.root.configure(bg='white')

        # ESC로 종료
        self.root.bind('<Escape>', lambda e: self.root.destroy())

        # 메인 프레임
        main_frame = tk.Frame(self.root, bg='white')
        main_frame.place(relx=0.5, rely=0.5, anchor='center')

        # 로고/타이틀
        title_label = tk.Label(
            main_frame,
            text="SFLAB",
            font=('Arial', 80, 'bold'),
            bg='white',
            fg='#2E7D32'
        )
        title_label.pack(pady=(0, 20))

        # 서브타이틀
        subtitle_label = tk.Label(
            main_frame,
            text="튀김 AI 모니터링 시스템",
            font=('Arial', 36),
            bg='white',
            fg='#333333'
        )
        subtitle_label.pack(pady=(0, 60))

        # 상태 메시지
        self.status_label = tk.Label(
            main_frame,
            text="시스템 점검 중...",
            font=('Arial', 28),
            bg='white',
            fg='#666666'
        )
        self.status_label.pack(pady=(0, 40))

        # 로딩 애니메이션 (점)
        self.dot_label = tk.Label(
            main_frame,
            text="●  ○  ○",
            font=('Arial', 24),
            bg='white',
            fg='#2E7D32'
        )
        self.dot_label.pack(pady=(0, 60))

        # 시간 표시
        self.time_label = tk.Label(
            main_frame,
            text="",
            font=('Arial', 24),
            bg='white',
            fg='#999999'
        )
        self.time_label.pack()

        # 하단 안내
        bottom_label = tk.Label(
            self.root,
            text="문의: 관리자",
            font=('Arial', 16),
            bg='white',
            fg='#AAAAAA'
        )
        bottom_label.pack(side='bottom', pady=30)

        self.dot_state = 0
        self.update_display()

    def update_display(self):
        # 시간 업데이트
        now = datetime.now()
        self.time_label.config(text=now.strftime("%Y-%m-%d  %H:%M:%S"))

        # 로딩 애니메이션
        dots = ["●  ○  ○", "○  ●  ○", "○  ○  ●"]
        self.dot_state = (self.dot_state + 1) % 3
        self.dot_label.config(text=dots[self.dot_state])

        self.root.after(500, self.update_display)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    print("[대기화면] 시작 - ESC로 종료")
    app = StandbyScreen()
    app.run()
