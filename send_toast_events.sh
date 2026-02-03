#!/bin/bash
# 과제보고서용 토스트 이벤트 전송 (터미널 명령)

BROKER="192.168.0.100"

echo "========================================="
echo "🎬 과제보고서 토스트 이벤트 전송"
echo "========================================="
echo ""
echo "사용법: ./send_toast_events.sh [이벤트번호]"
echo ""
echo "1) 진동 측정 시작"
echo "2) 진동 측정 종료"
echo "3) POT1 짜장 투입"
echo "4) POT1 짬뽕 투입"
echo "5) POT2 볶음밥 투입"
echo "6) POT2 우동 투입"
echo ""
echo "========================================="
echo ""

if [ -z "$1" ]; then
    read -p "이벤트 번호 입력 (1-6): " EVENT
else
    EVENT=$1
fi

case $EVENT in
    1)
        echo "📳 진동 측정 시작 이벤트 전송..."
        mosquitto_pub -h $BROKER -t "HR/Status" -m '{
            "Status": [{
                "DeviceNum": "1",
                "ChkVibration": true
            }]
        }'
        echo "✅ 전송 완료! Jetson GUI에 '진동 측정 시작' 토스트 표시됨"
        ;;

    2)
        echo "📳 진동 측정 종료 이벤트 전송..."
        mosquitto_pub -h $BROKER -t "HR/Status" -m '{
            "Status": [{
                "DeviceNum": "1",
                "ChkVibration": false
            }]
        }'
        echo "✅ 전송 완료! Jetson GUI에 '진동 측정 종료' 토스트 표시됨"
        ;;

    3)
        echo "🍳 POT1 짜장 투입 이벤트 전송..."
        mosquitto_pub -h $BROKER -t "HR/Status" -m '{
            "Status": [{
                "DeviceNum": "1",
                "PTNum": "0",
                "ProcessType": "투입",
                "NowRecipe": "짜장",
                "Mode": "AUTO",
                "RunningTime": "0분 0초",
                "TargetTime": "5분 0초",
                "Potstatus": {
                    "PT_Temp": 0,
                    "PT_Level": 0,
                    "PT_Power": "False",
                    "RT_Speed": 0,
                    "RT_Dir": 0
                }
            }]
        }'
        echo "✅ 전송 완료! Jetson GUI에 '볶음 POT1: 짜장' 토스트 표시됨"
        ;;

    4)
        echo "🍳 POT1 짬뽕 투입 이벤트 전송..."
        mosquitto_pub -h $BROKER -t "HR/Status" -m '{
            "Status": [{
                "DeviceNum": "1",
                "PTNum": "0",
                "ProcessType": "투입",
                "NowRecipe": "짬뽕",
                "Mode": "AUTO",
                "RunningTime": "0분 0초",
                "TargetTime": "5분 0초",
                "Potstatus": {
                    "PT_Temp": 0,
                    "PT_Level": 0,
                    "PT_Power": "False",
                    "RT_Speed": 0,
                    "RT_Dir": 0
                }
            }]
        }'
        echo "✅ 전송 완료! Jetson GUI에 '볶음 POT1: 짬뽕' 토스트 표시됨"
        ;;

    5)
        echo "🍳 POT2 볶음밥 투입 이벤트 전송..."
        mosquitto_pub -h $BROKER -t "HR/Status" -m '{
            "Status": [{
                "DeviceNum": "1",
                "PTNum": "1",
                "ProcessType": "투입",
                "NowRecipe": "볶음밥",
                "Mode": "AUTO",
                "RunningTime": "0분 0초",
                "TargetTime": "5분 0초",
                "Potstatus": {
                    "PT_Temp": 0,
                    "PT_Level": 0,
                    "PT_Power": "False",
                    "RT_Speed": 0,
                    "RT_Dir": 0
                }
            }]
        }'
        echo "✅ 전송 완료! Jetson GUI에 '볶음 POT2: 볶음밥' 토스트 표시됨"
        ;;

    6)
        echo "🍳 POT2 우동 투입 이벤트 전송..."
        mosquitto_pub -h $BROKER -t "HR/Status" -m '{
            "Status": [{
                "DeviceNum": "1",
                "PTNum": "1",
                "ProcessType": "투입",
                "NowRecipe": "우동",
                "Mode": "AUTO",
                "RunningTime": "0분 0초",
                "TargetTime": "5분 0초",
                "Potstatus": {
                    "PT_Temp": 0,
                    "PT_Level": 0,
                    "PT_Power": "False",
                    "RT_Speed": 0,
                    "RT_Dir": 0
                }
            }]
        }'
        echo "✅ 전송 완료! Jetson GUI에 '볶음 POT2: 우동' 토스트 표시됨"
        ;;

    *)
        echo "❌ 잘못된 번호입니다. 1-6 중 선택하세요."
        exit 1
        ;;
esac

echo ""
echo "📸 지금 바로 Jetson GUI 스크린샷 찍으세요! (5초 동안 보임)"
echo ""
