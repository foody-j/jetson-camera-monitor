# 1. NVIDIA 공식 l4t-base 이미지 기반으로 시작
FROM nvcr.io/nvidia/l4t-jetpack:r36.4.0

# 환경변수로 시간대 설정
ENV TZ=Asia/Seoul
# tzdata 패키지를 non-interactive 모드로 설치
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && \
    echo $TZ > /etc/timezone && \
    apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y tzdata && \
    rm -rf /var/lib/apt/lists/*
# ============================================

# 2. 파이썬과 PyTorch 설치에 필요한 기본 시스템 라이브러리들을 설치합니다.
RUN apt-get update && apt-get install -y python3-pip libopenblas-base libopenmpi-dev libjpeg-dev zlib1g-dev && rm -rf /var/lib/apt/lists/*
RUN apt-get update && apt-get install -y libgtk2.0-dev && rm -rf /var/lib/apt/lists/*

# 3. 카메라 및 비디오 처리를 위한 라이브러리 설치
RUN apt-get update && apt-get install -y \
    # OpenCV 의존성
    libopencv-dev \
    python3-opencv \
    # V4L2 (Video4Linux2) - 카메라 접근
    v4l-utils \
    # GStreamer - 비디오 스트리밍
    libgstreamer1.0-dev \
    libgstreamer-plugins-base1.0-dev \
    libgstreamer-plugins-bad1.0-dev \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav \
    gstreamer1.0-tools \
    gstreamer1.0-x \
    gstreamer1.0-alsa \
    gstreamer1.0-gl \
    gstreamer1.0-gtk3 \
    && rm -rf /var/lib/apt/lists/*

# 4. Python 패키지 설치 (OpenCV 최신 버전)
RUN pip3 install --upgrade pip && \
    pip3 install opencv-python opencv-contrib-python numpy

# 7. 컨테이너 안의 기본 작업 폴더를 /project로 설정합니다.
WORKDIR /project

# 8. 카메라 접근을 위한 비디오 그룹 설정
RUN groupadd -f video && \
    usermod -a -G video root

# 9. 컨테이너가 시작될 때 기본으로 실행할 명령어를 설정합니다. (터미널 실행)
CMD ["/bin/bash"]

