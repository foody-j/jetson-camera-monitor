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
