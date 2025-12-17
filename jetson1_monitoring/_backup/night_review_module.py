#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
야간 감지 사진 아침 리뷰 모듈 (백업용)

기능:
- 지정된 시간(예: 08:00)에 전날 야간 감지 사진 슬라이드쇼
- 10분 후 자동 종료 또는 수동 닫기
- 확인 후 아카이브/삭제 선택 가능

사용법:
    나중에 JETSON1_INTEGRATED.py에 통합할 때:
    1. config.json에 night_review 설정 추가
    2. NightReviewManager 인스턴스 생성
    3. 주기적으로 check_review_time() 호출

작성일: 2025-12-17
상태: 개발 대기 (백업)
"""

import os
import glob
import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta
from PIL import Image, ImageTk
import threading
import time


class NightReviewManager:
    """야간 감지 사진 리뷰 관리자"""

    def __init__(self, parent_app, config):
        """
        Args:
            parent_app: 부모 Tkinter 앱 (JETSON1_INTEGRATED의 self)
            config: 설정 딕셔너리
        """
        self.app = parent_app
        self.config = config

        # 설정 로드
        self.enabled = config.get('night_review_enabled', False)
        self.review_time = config.get('night_review_time', '08:00')  # HH:MM
        self.review_duration_min = config.get('night_review_duration_min', 10)
        self.auto_archive = config.get('night_review_auto_archive', True)
        self.snapshot_dir = os.path.expanduser(config.get('snapshot_dir', '~/Detection'))

        # 상태
        self.review_window = None
        self.review_shown_today = False
        self.current_images = []
        self.current_index = 0
        self.review_start_time = None

        # 리뷰 체크 날짜 (하루에 한 번만)
        self.last_check_date = None

    def check_review_time(self):
        """리뷰 시간인지 체크 - 메인 루프에서 주기적으로 호출"""
        if not self.enabled:
            return

        now = datetime.now()
        today = now.date()

        # 오늘 이미 리뷰했으면 스킵
        if self.last_check_date == today and self.review_shown_today:
            return

        # 날짜가 바뀌면 리셋
        if self.last_check_date != today:
            self.last_check_date = today
            self.review_shown_today = False

        # 리뷰 시간 체크
        try:
            review_hour, review_min = map(int, self.review_time.split(':'))
            review_datetime = now.replace(hour=review_hour, minute=review_min, second=0, microsecond=0)
            review_end = review_datetime + timedelta(minutes=self.review_duration_min)

            # 리뷰 시간 범위 내인지
            if review_datetime <= now <= review_end and not self.review_shown_today:
                self.show_review()

        except ValueError as e:
            print(f"[야간리뷰] 시간 파싱 오류: {e}")

    def get_night_images(self):
        """전날 야간 감지 이미지 목록 가져오기"""
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
        today = datetime.now().strftime("%Y%m%d")

        images = []

        # 전날 폴더에서 야간 시간대 이미지 (18:00 ~ 23:59)
        yesterday_dir = os.path.join(self.snapshot_dir, yesterday)
        if os.path.exists(yesterday_dir):
            for img_path in sorted(glob.glob(os.path.join(yesterday_dir, "*.jpg"))):
                filename = os.path.basename(img_path)
                # 파일명: HHMMSS.jpg
                try:
                    hour = int(filename[:2])
                    if hour >= 18:  # 18시 이후 (저녁/야간)
                        images.append(img_path)
                except:
                    pass

        # 오늘 폴더에서 새벽 시간대 이미지 (00:00 ~ 07:00)
        today_dir = os.path.join(self.snapshot_dir, today)
        if os.path.exists(today_dir):
            for img_path in sorted(glob.glob(os.path.join(today_dir, "*.jpg"))):
                filename = os.path.basename(img_path)
                try:
                    hour = int(filename[:2])
                    if hour < 7:  # 7시 이전 (새벽)
                        images.append(img_path)
                except:
                    pass

        return images

    def show_review(self):
        """리뷰 창 표시"""
        self.current_images = self.get_night_images()

        if not self.current_images:
            print("[야간리뷰] 야간 감지 이미지 없음")
            self.review_shown_today = True
            return

        print(f"[야간리뷰] {len(self.current_images)}장의 야간 감지 이미지 발견")

        self.current_index = 0
        self.review_start_time = datetime.now()
        self.review_shown_today = True

        # 리뷰 창 생성
        self._create_review_window()

        # 자동 종료 타이머
        self._start_auto_close_timer()

    def _create_review_window(self):
        """리뷰 창 UI 생성"""
        if self.review_window is not None:
            return

        self.review_window = tk.Toplevel(self.app.root)
        self.review_window.title("🌙 야간 감지 리뷰")
        self.review_window.geometry("800x650")
        self.review_window.configure(bg='#2C2C2C')

        # 헤더
        header_frame = tk.Frame(self.review_window, bg='#1E1E1E')
        header_frame.pack(fill='x', padx=10, pady=10)

        self.header_label = tk.Label(
            header_frame,
            text=f"🌙 야간 감지 리뷰 ({len(self.current_images)}건)",
            font=('NanumGothic', 18, 'bold'),
            fg='white',
            bg='#1E1E1E'
        )
        self.header_label.pack(side='left', padx=10)

        self.timer_label = tk.Label(
            header_frame,
            text="",
            font=('NanumGothic', 12),
            fg='#888888',
            bg='#1E1E1E'
        )
        self.timer_label.pack(side='right', padx=10)

        # 이미지 표시 영역
        self.image_frame = tk.Frame(self.review_window, bg='black')
        self.image_frame.pack(fill='both', expand=True, padx=10, pady=5)

        self.image_label = tk.Label(self.image_frame, bg='black')
        self.image_label.pack(fill='both', expand=True)

        # 정보 표시
        self.info_label = tk.Label(
            self.review_window,
            text="",
            font=('NanumGothic', 12),
            fg='#CCCCCC',
            bg='#2C2C2C'
        )
        self.info_label.pack(pady=5)

        # 네비게이션 버튼
        nav_frame = tk.Frame(self.review_window, bg='#2C2C2C')
        nav_frame.pack(fill='x', padx=10, pady=10)

        btn_style = {
            'font': ('NanumGothic', 14, 'bold'),
            'width': 10,
            'height': 2
        }

        self.prev_btn = tk.Button(
            nav_frame, text="◀ 이전",
            command=self.prev_image,
            bg='#404040', fg='white',
            **btn_style
        )
        self.prev_btn.pack(side='left', padx=5)

        self.counter_label = tk.Label(
            nav_frame,
            text="",
            font=('NanumGothic', 16, 'bold'),
            fg='white',
            bg='#2C2C2C'
        )
        self.counter_label.pack(side='left', expand=True)

        self.next_btn = tk.Button(
            nav_frame, text="다음 ▶",
            command=self.next_image,
            bg='#404040', fg='white',
            **btn_style
        )
        self.next_btn.pack(side='left', padx=5)

        # 하단 버튼
        bottom_frame = tk.Frame(self.review_window, bg='#2C2C2C')
        bottom_frame.pack(fill='x', padx=10, pady=10)

        self.delete_btn = tk.Button(
            bottom_frame, text="🗑 삭제",
            command=self.delete_current,
            bg='#8B0000', fg='white',
            font=('NanumGothic', 12, 'bold'),
            width=12, height=2
        )
        self.delete_btn.pack(side='left', padx=5)

        self.archive_btn = tk.Button(
            bottom_frame, text="📁 아카이브",
            command=self.archive_all,
            bg='#2E7D32', fg='white',
            font=('NanumGothic', 12, 'bold'),
            width=12, height=2
        )
        self.archive_btn.pack(side='left', padx=5)

        self.close_btn = tk.Button(
            bottom_frame, text="✕ 닫기",
            command=self.close_review,
            bg='#555555', fg='white',
            font=('NanumGothic', 12, 'bold'),
            width=12, height=2
        )
        self.close_btn.pack(side='right', padx=5)

        # 창 닫기 이벤트
        self.review_window.protocol("WM_DELETE_WINDOW", self.close_review)

        # 첫 이미지 표시
        self.show_current_image()

        # 타이머 업데이트 시작
        self._update_timer()

    def show_current_image(self):
        """현재 인덱스의 이미지 표시"""
        if not self.current_images or self.review_window is None:
            return

        img_path = self.current_images[self.current_index]

        try:
            # 이미지 로드 및 리사이즈
            img = Image.open(img_path)

            # 창 크기에 맞게 조절
            max_w, max_h = 760, 450
            img.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)

            photo = ImageTk.PhotoImage(img)
            self.image_label.configure(image=photo)
            self.image_label.image = photo  # 참조 유지

            # 정보 업데이트
            filename = os.path.basename(img_path)
            folder = os.path.basename(os.path.dirname(img_path))

            # 시간 파싱
            try:
                time_str = f"{filename[0:2]}:{filename[2:4]}:{filename[4:6]}"
            except:
                time_str = filename

            self.info_label.config(text=f"📅 {folder}  ⏰ {time_str}  📂 {filename}")

            # 카운터 업데이트
            self.counter_label.config(
                text=f"{self.current_index + 1} / {len(self.current_images)}"
            )

            # 버튼 상태 업데이트
            self.prev_btn.config(state='normal' if self.current_index > 0 else 'disabled')
            self.next_btn.config(state='normal' if self.current_index < len(self.current_images) - 1 else 'disabled')

        except Exception as e:
            print(f"[야간리뷰] 이미지 로드 오류: {e}")
            self.info_label.config(text=f"⚠️ 이미지 로드 실패: {img_path}")

    def prev_image(self):
        """이전 이미지"""
        if self.current_index > 0:
            self.current_index -= 1
            self.show_current_image()

    def next_image(self):
        """다음 이미지"""
        if self.current_index < len(self.current_images) - 1:
            self.current_index += 1
            self.show_current_image()

    def delete_current(self):
        """현재 이미지 삭제"""
        if not self.current_images:
            return

        img_path = self.current_images[self.current_index]

        try:
            os.remove(img_path)
            print(f"[야간리뷰] 삭제됨: {img_path}")

            # 목록에서 제거
            self.current_images.pop(self.current_index)

            # 인덱스 조정
            if self.current_index >= len(self.current_images):
                self.current_index = max(0, len(self.current_images) - 1)

            # 헤더 업데이트
            self.header_label.config(
                text=f"🌙 야간 감지 리뷰 ({len(self.current_images)}건)"
            )

            # 남은 이미지가 있으면 표시
            if self.current_images:
                self.show_current_image()
            else:
                self.close_review()

        except Exception as e:
            print(f"[야간리뷰] 삭제 오류: {e}")

    def archive_all(self):
        """전체 아카이브 (reviewed 폴더로 이동)"""
        if not self.current_images:
            return

        moved_count = 0

        for img_path in self.current_images[:]:  # 복사본으로 순회
            try:
                # 아카이브 폴더 생성
                parent_dir = os.path.dirname(img_path)
                archive_dir = os.path.join(parent_dir, "reviewed")
                os.makedirs(archive_dir, exist_ok=True)

                # 파일 이동
                filename = os.path.basename(img_path)
                archive_path = os.path.join(archive_dir, filename)
                os.rename(img_path, archive_path)
                moved_count += 1

            except Exception as e:
                print(f"[야간리뷰] 아카이브 오류: {e}")

        print(f"[야간리뷰] {moved_count}장 아카이브 완료")
        self.close_review()

    def _start_auto_close_timer(self):
        """자동 종료 타이머 시작"""
        def auto_close():
            while self.review_window is not None:
                time.sleep(1)
                elapsed = (datetime.now() - self.review_start_time).total_seconds()
                if elapsed >= self.review_duration_min * 60:
                    # Tkinter는 메인 스레드에서만 수정 가능
                    if self.review_window:
                        self.review_window.after(0, self.close_review)
                    break

        timer_thread = threading.Thread(target=auto_close, daemon=True)
        timer_thread.start()

    def _update_timer(self):
        """남은 시간 타이머 업데이트"""
        if self.review_window is None or self.review_start_time is None:
            return

        elapsed = (datetime.now() - self.review_start_time).total_seconds()
        remaining = max(0, self.review_duration_min * 60 - elapsed)

        mins = int(remaining // 60)
        secs = int(remaining % 60)

        self.timer_label.config(text=f"자동 종료: {mins:02d}:{secs:02d}")

        # 1초마다 업데이트
        if self.review_window:
            self.review_window.after(1000, self._update_timer)

    def close_review(self):
        """리뷰 창 닫기"""
        if self.review_window:
            self.review_window.destroy()
            self.review_window = None
            print("[야간리뷰] 리뷰 종료")


# ============================================================
# 테스트용 독립 실행
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("야간 감지 리뷰 모듈 테스트")
    print("=" * 60)

    # 테스트용 설정
    test_config = {
        'night_review_enabled': True,
        'night_review_time': datetime.now().strftime('%H:%M'),  # 현재 시간으로 테스트
        'night_review_duration_min': 10,
        'snapshot_dir': '~/Detection'
    }

    # 간단한 테스트 앱
    class TestApp:
        def __init__(self):
            self.root = tk.Tk()
            self.root.title("Night Review Test")
            self.root.geometry("400x200")

            tk.Label(self.root, text="야간 리뷰 테스트", font=('Arial', 16)).pack(pady=20)

            self.manager = NightReviewManager(self, test_config)

            tk.Button(
                self.root, text="리뷰 창 열기",
                command=self.manager.show_review,
                font=('Arial', 14)
            ).pack(pady=10)

            tk.Button(
                self.root, text="종료",
                command=self.root.quit,
                font=('Arial', 14)
            ).pack(pady=10)

        def run(self):
            self.root.mainloop()

    app = TestApp()
    app.run()
