# Web Kiosk Deployment

현장 PC 부팅 후 다음 순서로 자동 실행되도록 구성하는 배포 절차입니다.

1. `systemd`가 `JETSON1_web.py` 또는 `JETSON2_web.py`를 자동 실행
2. 디스플레이 매니저가 지정 사용자로 자동 로그인
3. 로그인 후 Firefox가 `127.0.0.1` 로컬 대시보드를 자동 오픈

기본 포트:

- Jetson 1: `http://127.0.0.1:7000`
- Jetson 2: `http://127.0.0.1:8000`

## 설치

프로젝트 루트에서 실행:

```bash
chmod +x install_web_kiosk.sh
./install_web_kiosk.sh
```

설치 스크립트가 수행하는 작업:

- `/etc/systemd/system/jetson1-web.service` 또는 `jetson2-web.service` 설치
- 매일 새벽 2시 재시작 타이머 설치
- `~/.local/bin/<jetson>-launch-firefox.sh` 생성
- `~/.config/autostart/<jetson>-web-browser.desktop` 생성
- `gdm3` 또는 `lightdm` 자동 로그인 설정 시도

## 확인

```bash
sudo systemctl status jetson1-web.service --no-pager
sudo systemctl status jetson2-web.service --no-pager
sudo journalctl -u jetson1-web.service -f
sudo journalctl -u jetson2-web.service -f
```

Autostart 파일 확인:

```bash
ls ~/.config/autostart
ls ~/.local/bin
```

## 동작 원리

Firefox는 부팅 직후 바로 뜨지 않고, 로컬 웹 서버가 응답할 때까지 최대 180초 대기한 뒤 실행됩니다.

즉 네트워크가 끊겨도 다음 조건만 만족하면 동작합니다.

- 로컬 OS 부팅 성공
- GUI 로그인 성공
- `JETSON*_web.py` 서비스 실행 성공

`127.0.0.1`은 자기 자신의 로컬 루프백 주소이므로 인터넷 연결과 무관합니다.

## 제거

```bash
chmod +x uninstall_web_kiosk.sh
./uninstall_web_kiosk.sh
```
