# 1. NVIDIA 공식 l4t-base 이미지 기반으로 시작
FROM nvcr.io/nvidia/l4t-jetpack:r36.4.0

# 2. 파이썬과 PyTorch 설치에 필요한 기본 시스템 라이브러리들을 설치합니다.
RUN apt-get update && apt-get install -y python3-pip libopenblas-base libopenmpi-dev libjpeg-dev zlib1g-dev && rm -rf /var/lib/apt/lists/*
RUN apt-get update && apt-get install -y libgtk2.0-dev && rm -rf /var/lib/apt/lists/*

# 5. 컨테이너 안의 기본 작업 폴더를 /project로 설정합니다.
WORKDIR /project

# 6. 컨테이너가 시작될 때 기본으로 실행할 명령어를 설정합니다. (터미널 실행)
CMD ["/bin/bash"]

