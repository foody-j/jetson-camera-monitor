# Jetson 한글 및 기본 설정 가이드

## 한글 설정

```bash
sudo apt update
sudo apt install -y language-pack-ko language-pack-ko-base fonts-noto-cjk fonts-noto-cjk-extra
sudo locale-gen ko_KR.UTF-8
sudo update-locale LANG=ko_KR.UTF-8 LC_MESSAGES=POSIX
sudo apt install -y ibus ibus-hangul
im-config -n ibus
sudo reboot
```

재부팅 후:
```bash
ibus-daemon -drx
```

## Firefox 설치

```bash
sudo apt install -y firefox
```

### Snap 관련 (필요시)

```bash
snap download snapd --revision=24724
sudo snap ack snapd_24724.assert
sudo snap install snapd_24724.snap
sudo snap refresh --hold snapd
sudo reboot
```

## RustDesk 설치 (원격 제어)

Jetson (ARM64)용 RustDesk 설치:

```bash
# 최신 버전 다운로드 (v1.4.4 기준)
wget https://github.com/rustdesk/rustdesk/releases/download/1.4.4/rustdesk-1.4.4-aarch64.deb

# 설치
sudo apt install -y ./rustdesk-1.4.4-aarch64.deb

# 의존성 문제 시
sudo apt --fix-broken install
```

### 최신 버전 확인

GitHub Releases에서 최신 aarch64.deb 파일 확인:
https://github.com/rustdesk/rustdesk/releases

### 실행

```bash
rustdesk
```

또는 애플리케이션 메뉴에서 RustDesk 실행

### Wayland 문제 시

X11으로 전환 필요할 수 있음:
```bash
# 로그인 화면에서 세션 타입을 X11으로 변경
# 또는 GDM 설정에서 Wayland 비활성화
sudo vim /etc/gdm3/custom.conf
# WaylandEnable=false 설정
```
