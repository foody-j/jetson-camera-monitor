# Git Push 가이드

## ✅ 커밋 완료!

커밋이 성공적으로 생성되었습니다:
- Commit ID: `ea8dfbf`
- 15개 파일 변경
- 4008줄 추가

## ❌ Push 실패 - 인증 필요

GitHub에 push하려면 인증이 필요합니다. 다음 방법 중 하나를 선택하세요:

---

## 방법 1: Personal Access Token (추천)

### 1-1. GitHub에서 토큰 생성

1. GitHub.com 로그인
2. Settings → Developer settings → Personal access tokens → Tokens (classic)
3. "Generate new token (classic)" 클릭
4. 권한 선택:
   - ✅ `repo` (전체 저장소 접근)
5. 토큰 생성 후 **복사** (다시 볼 수 없음!)

### 1-2. Git에서 사용

```bash
# Push 시도
git push origin main

# Username 입력: GitHub 사용자명
# Password 입력: 위에서 복사한 토큰 (비밀번호 아님!)
```

### 1-3. 토큰 저장 (선택사항)

```bash
# 토큰을 캐시에 저장 (15분)
git config --global credential.helper cache

# 또는 영구 저장 (평문 주의!)
git config --global credential.helper store
```

---

## 방법 2: SSH Key 사용

### 2-1. SSH Key 생성 (없는 경우)

```bash
# SSH key 생성
ssh-keygen -t ed25519 -C "your_email@example.com"

# Enter 3번 (기본 위치, 비밀번호 선택)
```

### 2-2. GitHub에 SSH Key 등록

```bash
# 공개키 출력
cat ~/.ssh/id_ed25519.pub

# 출력된 내용을 복사
```

GitHub에서:
1. Settings → SSH and GPG keys
2. "New SSH key" 클릭
3. 복사한 공개키 붙여넣기

### 2-3. Remote URL 변경

```bash
# HTTPS → SSH로 변경
git remote set-url origin git@github.com:foody-j/jetson-camera-monitor.git

# 확인
git remote -v

# Push
git push origin main
```

---

## 방법 3: VSCode에서 Push (가장 쉬움!)

VSCode를 사용 중이라면:

1. **Source Control** 패널 열기 (Ctrl+Shift+G)
2. 커밋 메시지 확인
3. **"Sync Changes"** 또는 **"Push"** 버튼 클릭
4. GitHub 로그인 팝업이 나타나면 로그인

VSCode가 자동으로 인증을 처리합니다!

---

## 현재 상태

```bash
# 로컬 커밋 확인
git log --oneline -3

# 변경 사항 확인
git show HEAD --stat
```

**커밋은 로컬에 저장되어 있습니다.** 언제든지 push 할 수 있습니다.

---

## 빠른 해결: 터미널에서 Push

```bash
# 방법 1-2 사용 (Personal Access Token)
git push origin main
# Username: foody-j (또는 본인 GitHub ID)
# Password: ghp_xxxxxxxxxxxxxxxxxxxx (토큰)

# 또는

# VSCode Source Control에서 버튼 클릭
```

---

## 문제 해결

### "Authentication failed"
→ 토큰이 만료되었거나 권한이 부족함
→ 새 토큰 생성 (repo 권한 포함)

### "Permission denied (publickey)"
→ SSH key가 등록되지 않음
→ 방법 2 참고하여 SSH key 등록

### "fatal: not a git repository"
→ 잘못된 디렉토리에 있음
→ `cd /home/dkutest/my_ai_project`

---

## 이후 작업

Push가 완료되면:
1. GitHub 저장소에서 커밋 확인
2. `PROJECT_SUMMARY.md` 확인 → Obsidian에 복사
3. `RUN_WEB_VIEWER.md` 참고하여 웹 뷰어 테스트

---

**커밋 요약**:
- ✅ 웹 기반 실시간 모니터링 시스템
- ✅ 음식/기름 세그멘테이션
- ✅ 색상 특징 추출
- ✅ Flask 웹 뷰어
- ✅ 전체 문서화
