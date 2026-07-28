from machine import ADC, Pin, PWM, SoftI2C, RTC
from time import sleep, sleep_ms
from servo import Servo
import dht
from lcd_api import LcdApi
from i2c_lcd import I2cLcd
import ssd1306
import framebuf
import neopixel

# 1. 하드웨어 핀 및 센서 초기화
# 조도 센서 초기화 (LDR Pin 36)
cds = ADC(Pin(36))
cds.atten(ADC.ATTN_11DB)

# 서보 모터 초기화 (Servo Pin 13)
motor = Servo(pin=13)
# motor.move(90) # 90도 정렬 설정 (실행 시 초기 움직임 방지를 위해 주석 처리)

# 피에조 부저 초기화 (PWM Pin 23)
piezo = PWM(Pin(23))
piezo.duty_u16(0)

# RGB LED 초기화 (PWM 제어)
R_pwm = PWM(Pin(25))
G_pwm = PWM(Pin(26))
B = Pin(27, Pin.OUT)

R_pwm.freq(1000)
G_pwm.freq(1000)

R_pwm.duty_u16(0)
G_pwm.duty_u16(0)
B.value(0)

# 네오픽셀 초기화 (GPIO 4 연결, 12구)
np = neopixel.NeoPixel(Pin(4), 12)
for i in range(12):
    np[i] = (0, 0, 0)
np.write()

# DHT11 온습도 센서 초기화 (Pin 14)
d = dht.DHT11(Pin(14))

# I2C 통신 객체 초기화 (OLED와 LCD가 공유)
i2c = SoftI2C(sda=Pin(21), scl=Pin(22))

# TV (I2C LCD 16x2) 초기화 (SoftI2C 주소: 0x27)
lcd = I2cLcd(i2c, 0x27, 2, 16)
lcd.clear()

# OLED 디스플레이 초기화 (SSD1306 128x64, 주소: 0x3C)
display2 = ssd1306.SSD1306_I2C(128, 64, i2c)
display2.fill(0)
display2.show()

# 4채널 정전식 터치 센서 입력 핀 정의 (Active-Low 스위치 지원을 위해 PULL_UP 설정)
touch1 = Pin(17, Pin.IN, Pin.PULL_UP) # 1번 터치 센서 핀 (D17)
touch2 = Pin(5, Pin.IN, Pin.PULL_UP)  # 2번 터치 센서 핀 (D5)
touch3 = Pin(18, Pin.IN, Pin.PULL_UP) # 3번 터치 센서 핀 (D18)
touch4 = Pin(19, Pin.IN, Pin.PULL_UP) # 4번 터치 센서 핀 (D19)

# 물리 스위치 입력 핀 정의 (D16에 꽂힌 3핀 스위치 모듈)
limit_switch = Pin(16, Pin.IN, Pin.PULL_UP)

# 터치 센서 및 물리 스위치 이전 상태 저장 (엣지 감지 디바운싱용)
touch1_prev = 0
touch2_prev = 0
touch3_prev = 0
touch4_prev = 0
limit_switch_prev = 0

# 내장 실시간 시계 (RTC) 초기화
rtc = RTC()

# 2. 전역 상태 변수 정의 (4개 독립 놀이기구 개별 카운터 도입)
play_count_1 = 0
play_count_2 = 0
play_count_3 = 0
play_count_4 = 0
current_play_step = 0 # 현재 순환 플레이 단계 (1->2->3->4 순환)

feed_seconds = 14400 # 기본 급식 대기 시간: 4시간 (14400초)
light_toggle_active = True # True: 자동 조명 모드 활성, False: 조명 수동 강제 소등
cds_flag = 0

# LCD 캐싱 변수 정의 (화면 깜빡임 방지)
prev_lcd_line0 = ""
prev_lcd_line1 = ""

# 부저 멜로디 정의
blindMelody = (524, 659, 784)
melody1 = (784, 784, 880, 880, 784, 784, 659) # 학교종
melody2 = (523, 523, 784, 784, 880, 880, 784) # 작은별

# 3. 시간 동기화 함수
def sync_time(time_str):
    try:
        parts = time_str.split(':')
        if len(parts) == 7:
            year = int(parts[1])
            month = int(parts[2])
            day = int(parts[3])
            hour = int(parts[4])
            minute = int(parts[5])
            second = int(parts[6])
            rtc.datetime((year, month, day, 0, hour, minute, second, 0))
            print("Time Synced successfully:", rtc.datetime())
            return True
    except Exception as e:
        print("Time Sync Error:", e)
    return False

# 4. 자동/수동 급식 메커니즘
def trigger_feeding():
    global feed_seconds
    print("Feeding started...")
    motor.move(180) # 180도로 이동
    sleep(1)        # 1초간 대기
    motor.move(90)  # 다시 원래대로(90도) 복귀
    
    # 급식 성공 알림음 연주
    piezo.duty_u16(1000)
    for freq in (523, 659, 784):
        piezo.freq(freq)
        sleep(0.15)
    piezo.duty_u16(0)
    
    p.send("snack_requested:0\n")
    feed_seconds = 14400
    p.send("feed_countdown:{}\n".format(feed_seconds))
    print("Feeding completed.")

# 강아지가 D16 발판 버튼을 밟아 주인을 화상 호출하는 반려견 호출벨 IoT 기믹
def trigger_owner_call():
    try:
        print("Dog is calling the owner! sending BLE signal...")
        # 1. 블루투스 대시보드로 '강아지가 화상 통화 요청함' 알림 실시간 발송
        p.send("owner_call:1\n")
        
        # 2. OLED에 한쪽 귀 옆에 수화기를 대고 전화 거는 찐빵 강아지 렌더링
        display2.fill(0)
        display2.rect(0, 0, 128, 64, 1)
        display2.rect(2, 2, 124, 60, 1)
        # 둥근 뺨 & 귀
        display2.fill_rect(32, 12, 64, 36, 1)
        display2.pixel(32, 12, 0); display2.pixel(95, 12, 0)
        display2.pixel(32, 47, 0); display2.pixel(95, 47, 0)
        display2.fill_rect(24, 16, 8, 22, 1)
        display2.fill_rect(96, 16, 8, 22, 1)
        
        # 초롱초롱한 양눈
        display2.fill_rect(43, 22, 8, 10, 0)
        display2.pixel(44, 23, 1)
        display2.fill_rect(77, 22, 8, 10, 0)
        display2.pixel(78, 23, 1)
        
        # 수화기 그리기 (왼쪽 뺨 옆에 3D 스타일 수화기)
        display2.fill_rect(14, 20, 6, 20, 1) # 수화기 몸체
        display2.fill_rect(10, 18, 10, 4, 1)  # 수청기 (귀 부분)
        display2.fill_rect(10, 38, 10, 4, 1)  # 송화기 (입 부분)
        display2.line(20, 30, 32, 35, 1)      # 전화 꼬임선 연결선
        
        # 수줍은 고양이 입꼬리 (ㅅ 모양)
        display2.line(61, 37, 64, 39, 0)
        display2.line(64, 39, 67, 37, 0)
        display2.show()
        
        # 3. 피에조 부저 전화 벨소리 연주 (따르릉~ 따르릉~ 레트로 벨소리 2회)
        for _ in range(2):
            for freq in (880, 0, 880, 0, 1047, 0, 1047, 0):
                if freq == 0:
                    piezo.duty_u16(0)
                    sleep(0.04)
                else:
                    piezo.duty_u16(1000)
                    piezo.freq(freq)
                    sleep(0.06)
            sleep(0.2)
        piezo.duty_u16(0)
        
    except Exception as e:
        print("Owner Call Error:", e)

# 5. 터치 플레이 스텝별 효과 제어
def set_neopixel_pattern(step):
    try:
        if step == 1:
            # 멜로디 인형: 12구 꼬리 잔상 체이서 회전 효과
            for r in range(12):
                for i in range(12):
                    dist = (i - r) % 12
                    if dist == 0:
                        np[i] = (255, 30, 0)  # 가장 밝은 빨강
                    elif dist == 1:
                        np[i] = (100, 10, 0)  # 흐릿한 빨강
                    elif dist == 2:
                        np[i] = (30, 0, 0)    # 잔상
                    else:
                        np[i] = (0, 0, 0)
                np.write()
                sleep_ms(40)
            for i in range(12):
                np[i] = (255, 0, 0)
            np.write()
            
        elif step == 2:
            # 자동 레이저: 12구가 홀수/짝수 그룹으로 나뉘어 교차 번쩍이는 레이저 효과
            for _ in range(4):
                for i in range(12):
                    np[i] = (0, 255, 50) if i % 2 == 0 else (0, 0, 0)
                np.write()
                sleep_ms(60)
                for i in range(12):
                    np[i] = (0, 0, 0) if i % 2 == 0 else (0, 150, 255)
                np.write()
                sleep_ms(60)
            for i in range(12):
                np[i] = (0, 255, 50)
            np.write()
            
        elif step == 3:
            # 삑삑이 공: 양쪽 대칭형(0&11, 1&10...)으로 오가는 대칭 네온 웨이브 효과
            for r in range(6):
                for i in range(12):
                    dist = abs(6 - i)
                    if dist == r or dist == (r + 1) % 6:
                        np[i] = (180, 0, 255) # 보라
                    else:
                        np[i] = (0, 30, 255)  # 파랑
                np.write()
                sleep_ms(50)
            for i in range(12):
                np[i] = (0, 50, 255)
            np.write()
            
        elif step == 4:
            # 오뚝이 장난감: 12개 풀 컬러 레인보우 그라데이션이 빠르게 돌다 고정되는 볼텍스 효과
            colors = [
                (255, 0, 0), (255, 80, 0), (255, 150, 0), (180, 255, 0),
                (0, 255, 0), (0, 255, 100), (0, 255, 255), (0, 120, 255),
                (0, 0, 255), (100, 0, 255), (200, 0, 255), (255, 0, 150)
            ]
            for shift in range(24): # 2바퀴
                for i in range(12):
                    np[i] = colors[(i + shift) % 12]
                np.write()
                sleep_ms(30)
            for i in range(12):
                np[i] = colors[i]
            np.write()
    except Exception as e:
        print("NeoPixel Write Error:", e)

def play_piezo_melody(step):
    try:
        if step == 1:
            # 1번: 동물의 숲 T.K. - 나비보벳따우 (악보 기반 + 웅장한 2옥타브 다운 저음 튜닝 버전)
            # Dm9 -> Em9 -> Amaj7 -> Bb7#11 코드를 타는 저음 뚱가뚱가 핑거스타일 비트
            notes = [
                # 1마디: Dm9 (레-레-파#-쉼-레-레-레#)
                147, 294, 370, 0, 147, 147, 156,
                # 2마디: Em9 (미-미-솔#-쉼-미-솔-솔#)
                165, 330, 415, 0, 165, 98, 104,
                # 3마디: Amaj7/Eb9 (레-레-파#-쉼-레-솔-솔#)
                147, 294, 370, 0, 147, 98, 104,
                # 4마디: Bb7#11 (레-미-파#-미-솔#)
                147, 330, 370, 165, 208
            ]
            durations = [
                # 1마디 박자
                0.14, 0.14, 0.14, 0.14, 0.14, 0.07, 0.07,
                # 2마디 박자
                0.14, 0.14, 0.14, 0.14, 0.14, 0.07, 0.07,
                # 3마디 박자
                0.14, 0.14, 0.14, 0.14, 0.14, 0.07, 0.07,
                # 4마디 박자
                0.14, 0.14, 0.14, 0.14, 0.45
            ]
            for note, dur in zip(notes, durations):
                if note == 0:
                    piezo.duty_u16(0)
                else:
                    piezo.duty_u16(1000)
                    piezo.freq(note)
                sleep(dur)
            piezo.duty_u16(0)
            
        elif step == 2:
            # 2번: 슈퍼 마리오 시작 멜로디 (E5, E5, 쉼, E5, 쉼, C5, E5, G5, G4)
            notes = [659, 659, 0, 659, 0, 523, 659, 0, 784, 0, 392]
            durations = [0.08, 0.08, 0.08, 0.08, 0.08, 0.08, 0.12, 0.08, 0.12, 0.2, 0.15]
            for note, dur in zip(notes, durations):
                if note == 0:
                    piezo.duty_u16(0)
                else:
                    piezo.duty_u16(1000)
                    piezo.freq(note)
                sleep(dur)
            piezo.duty_u16(0)
            
        elif step == 3:
            # 3번: 슈퍼 마리오 사망 멜로디 (Die Theme - Game Over)
            notes = [988, 1397, 0, 1397, 1397, 1319, 1175, 1047]
            durations = [0.08, 0.08, 0.04, 0.08, 0.08, 0.08, 0.08, 0.35]
            for note, dur in zip(notes, durations):
                if note == 0:
                    piezo.duty_u16(0)
                else:
                    piezo.duty_u16(1000)
                    piezo.freq(note)
                sleep(dur)
            piezo.duty_u16(0)
            
        elif step == 4:
            # 4번: 포켓몬스터 야생 배틀 인트로 효과음 (Wild Pokemon Encounter - 게임보이 버전 완벽 재현)
            # 1. 풀숲에서 몬스터 조우시 화면 소용돌이 스윕 사운드 (초고속 주파수 왕복)
            piezo.duty_u16(1000)
            for _ in range(3):
                for freq in [880, 988, 1047, 1175, 1319, 1175, 1047, 988]:
                    piezo.freq(freq)
                    sleep_ms(15)
            
            # 2. 화면이 바뀌며 시작되는 야생 배틀 긴장감 비트 (쿵작쿵작 연타)
            battle_notes = [830, 880, 0, 830, 880, 0, 830, 880, 830, 880, 830, 880]
            battle_durs = [0.08, 0.08, 0.04, 0.08, 0.08, 0.04, 0.06, 0.06, 0.06, 0.06, 0.06, 0.2]
            for note, dur in zip(battle_notes, battle_durs):
                if note == 0:
                    piezo.duty_u16(0)
                else:
                    piezo.duty_u16(1000)
                    piezo.freq(note)
                sleep(dur)
            piezo.duty_u16(0)
    except Exception as e:
        print("Buzzer Play Error:", e)

def set_oled_display(step):
    try:
        # 화면 비우기
        display2.fill(0)
        
        # 1. 아기자기한 더블 테두리 액자 그리기
        display2.rect(0, 0, 128, 64, 1)
        display2.rect(2, 2, 124, 60, 1)
        
        # 2. 아주 귀여운 찐빵형 강아지 얼굴 뼈대 (둥글둥글 뺨 적용)
        # 아래로 쳐진 귀 (양옆)
        display2.fill_rect(24, 16, 8, 22, 1)
        display2.fill_rect(96, 16, 8, 22, 1)
        # 귀 아래 모서리 부드럽게 깎기
        display2.pixel(24, 37, 0)
        display2.pixel(31, 37, 0)
        display2.pixel(96, 37, 0)
        display2.pixel(103, 37, 0)
        
        # 찐빵형 얼굴 본체
        display2.fill_rect(32, 12, 64, 36, 1)
        # 얼굴 4개 모서리 깎아서 둥근 구 형태 만들기
        display2.pixel(32, 12, 0)
        display2.pixel(95, 12, 0)
        display2.pixel(32, 47, 0)
        display2.pixel(95, 47, 0)
        
        # 귀여운 작은 코 (가운데에 콕 박혀 있음)
        display2.fill_rect(61, 30, 6, 4, 0)
        
        # 수줍은 고양이 입꼬리 (ㅅ 모양)
        display2.line(61, 37, 64, 39, 0)
        display2.line(64, 39, 67, 37, 0)
        
        # 3. 스텝별 다채롭고 깜찍한 눈과 표정 묘사
        if step == 1:
            # 1번: 똘망똘망하게 윙크하기
            # 왼쪽 눈: 찡긋 웃는 눈 ( ^ )
            display2.line(43, 27, 47, 23, 0)
            display2.line(47, 23, 51, 27, 0)
            # 오른쪽 눈: 초롱초롱한 눈망울 (큰 둥근 눈 + 흰색 하이라이트)
            display2.fill_rect(75, 22, 8, 10, 0)
            display2.pixel(76, 23, 1) # 초롱초롱한 눈동자 빛
            
        elif step == 2:
            # 2번: 둥글둥글한 패션 선글라스를 낀 힙한 얼굴
            display2.fill_rect(40, 20, 16, 12, 0) # 왼쪽 동글 알
            display2.fill_rect(72, 20, 16, 12, 0) # 오른쪽 동글 알
            display2.line(56, 24, 72, 24, 0)     # 안경 연결선
            # 선글라스 알 모서리 둥글게 깎기
            display2.pixel(40, 20, 1)
            display2.pixel(55, 20, 1)
            display2.pixel(40, 31, 1)
            display2.pixel(55, 31, 1)
            display2.pixel(72, 20, 1)
            display2.pixel(87, 20, 1)
            display2.pixel(72, 31, 1)
            display2.pixel(87, 31, 1)
            
            # 입꼬리 한쪽만 썩소로 시크하게 올리기
            display2.line(64, 39, 68, 41, 0)
            display2.line(68, 41, 71, 38, 0)
            
        elif step == 3:
            # 3번: 양쪽 다 초롱초롱 왕눈 뜨고 날름 메롱 혀 내밀기
            display2.fill_rect(43, 22, 8, 10, 0)
            display2.pixel(44, 23, 1)
            display2.fill_rect(77, 22, 8, 10, 0)
            display2.pixel(78, 23, 1)
            
            # 메롱 혀 (흰색 바탕에 검은 테두리와 틈새선)
            display2.fill_rect(61, 39, 6, 8, 1)
            display2.rect(61, 39, 6, 8, 0)
            display2.line(64, 39, 64, 45, 0)
            
        elif step == 4:
            # 4번: 양쪽 다 눈웃음 (> <) 짓고 볼터치에 벌어진 웃는 입
            # 왼쪽 눈 >
            display2.line(42, 23, 49, 27, 0)
            display2.line(42, 31, 49, 27, 0)
            # 오른쪽 눈 <
            display2.line(86, 23, 79, 27, 0)
            display2.line(86, 31, 79, 27, 0)
            
            # 사선 볼터치 (볼 부분에 사선 2개씩 깜찍하게)
            display2.line(35, 35, 33, 38, 0)
            display2.line(38, 35, 36, 38, 0)
            display2.line(90, 35, 88, 38, 0)
            display2.line(93, 35, 91, 38, 0)
            
            # 헤헤 크게 벌리고 웃는 입
            display2.fill_rect(60, 39, 8, 6, 0)
            
        # 버퍼에 그린 내용을 OLED 화면에 최종 반영
        display2.show()
    except Exception as e:
        print("OLED Draw Error:", e)

def trigger_play_mode(step):
    global play_count_1, play_count_2, play_count_3, play_count_4
    print("Triggered Play Mode Step:", step)
    
    set_oled_display(step)
    set_neopixel_pattern(step)
    play_piezo_melody(step)
    
    p.send("play_active:{}\n".format(step))
    
    if step == 1:
        play_count_1 += 1
        p.send("play_count_1:{}\n".format(play_count_1))
    elif step == 2:
        play_count_2 += 1
        p.send("play_count_2:{}\n".format(play_count_2))
    elif step == 3:
        play_count_3 += 1
        p.send("play_count_3:{}\n".format(play_count_3))
    elif step == 4:
        play_count_4 += 1
        p.send("play_count_4:{}\n".format(play_count_4))
        
    p.send("snack_requested:1\n")

# Wi-Fi 및 서버 정보 로드
import json
import network
import urequests

wifi_ssid = "ICEE"
wifi_password = "icee2026"
server_ip = "192.168.0.17"

try:
    with open("wifi_config.json", "r") as f:
        config = json.load(f)
        wifi_ssid = config.get("ssid", wifi_ssid)
        wifi_password = config.get("password", wifi_password)
        server_ip = config.get("server_ip", server_ip)
        print("성공")
        
except Exception as e:
    print("Could not load wifi_config.json, using defaults:", e)

server_url = "http://{}:8000".format(server_ip)

def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    try:
        wlan.active(False)
        sleep(0.5)
    except:
        pass
    wlan.active(True)
    if not wlan.isconnected():
        print("Connecting to Wi-Fi: {}...".format(wifi_ssid))
        wlan.connect(wifi_ssid, wifi_password)
        for _ in range(20):
            if wlan.isconnected():
                break
            sleep(0.5)
    if wlan.isconnected():
        print("Wi-Fi Connected! IP Address:", wlan.ifconfig()[0])
        lcd.clear()
        lcd.move_to(0, 0)
        lcd.putstr("WiFi Connected!")
        lcd.move_to(0, 1)
        lcd.putstr(wlan.ifconfig()[0])
        sleep(2.0)
        return True
    else:
        print("Wi-Fi Connection Failed!")
        lcd.clear()
        lcd.move_to(0, 0)
        lcd.putstr("WiFi Connect Fail")
        lcd.move_to(0, 1)
        lcd.putstr("Check wifi_config")
        sleep(3.0)
        return False

# 와이파이 연결 시도
connect_wifi()

# BLE 모듈 초기화 및 인스턴스 생성
import ble_library
import bluetooth

ble = bluetooth.BLE()
p_ble = ble_library.BLESimplePeripheral(ble, "ESP_Js")

# BLE와 Wi-Fi를 동시에 지원하는 DualBuffer 클래스
class DualBuffer:
    def __init__(self):
        self.buffer = []
    
    def send(self, data):
        # 1. 즉시 블루투스(BLE)로 전송
        try:
            p_ble.send(data)
        except Exception as e:
            print("BLE send error:", e)
            
        # 2. 와이파이(HTTP) 전송을 위해 버퍼에 누적
        self.buffer.append(data)
        print("Buffered for WiFi:", data.strip())
        # 즉시 전송이 필요한 이벤트는 바로 플러시
        if any(event in data for event in ["owner_call", "play_", "snack_"]):
            flush_buffer()

    def on_write(self, callback):
        # BLE 수신 콜백 등록
        p_ble.on_write(callback)

p = DualBuffer()

def flush_buffer():
    if not p.buffer:
        return
    data_to_send = "".join(p.buffer)
    p.buffer.clear()
    try:
        res = urequests.post(server_url + "/api/esp/sensors", data=data_to_send, timeout=3)
        res.close()
    except Exception as e:
        print("Failed to send sensors:", e)

def poll_commands():
    try:
        res = urequests.get(server_url + "/api/esp/commands", timeout=3)
        if res.status_code == 200:
            commands = res.json()
            res.close()
            for cmd in commands:
                on_rx(cmd)
        else:
            res.close()
    except Exception as e:
        print("Failed to poll commands:", e)

def on_rx(v):
    global light_toggle_active
    if isinstance(v, bytes):
        v = v.decode('utf-8')
    v = str(v).strip()
    print("Received Command:", v)
    
    if v.startswith("SETTIME:"):
        sync_time(v)
        return

    if v == '1':
        try:
            d.measure()
            temp = str(int(d.temperature()))
            humi = str(int(d.humidity()))
            p.send("temp : " + temp + "\n")
            p.send("humi : " + humi + "\n")
        except Exception:
            p.send("temp : Error\n")
            p.send("humi : Error\n")
        
    elif v == '2':
        cds_value = cds.read()
        p.send(str(cds_value) + "\n")

    elif v == '3':
        lcd.backlight_on()
        
    elif v == '4':
        lcd.backlight_off()
    
    elif v == '5':
        piezo.duty_u16(1000)
        for i in melody1:
            piezo.freq(i)
            sleep(0.3)
        piezo.duty_u16(0) 

    elif v == '6':
        piezo.duty_u16(1000)
        for i in melody2:
            piezo.freq(i)
            sleep(0.3)
        piezo.duty_u16(0) 
    
    elif v == '7':
        light_toggle_active = True
        R_pwm.duty_u16(0)
        G_pwm.duty_u16(65535)
        B.value(0)
    
    elif v == '8':
        light_toggle_active = False
        R_pwm.duty_u16(0)
        G_pwm.duty_u16(0)
        B.value(0)
        
    elif v == '9':
        set_oled_display(4)

    elif v == 'a':
        trigger_feeding()
        
    elif v == 'b':
        light_toggle_active = not light_toggle_active
        print("Light auto mode active:", light_toggle_active)

    elif v == 'c':
        trigger_play_mode(1)
    elif v == 'd':
        trigger_play_mode(2)
    elif v == 'e':
        trigger_play_mode(3)
    elif v == 'f':
        trigger_play_mode(4)
    elif v == 'call_accept':
        # 통화 수락 시: OLED에 행복한 눈웃음과 함께 통화 중 상태를 표시
        try:
            display2.fill(0)
            display2.rect(0, 0, 128, 64, 1)
            display2.rect(2, 2, 124, 60, 1)
            display2.fill_rect(32, 12, 64, 36, 1)
            display2.pixel(32, 12, 0); display2.pixel(95, 12, 0)
            display2.pixel(32, 47, 0); display2.pixel(95, 47, 0)
            display2.fill_rect(24, 16, 8, 22, 1)
            display2.fill_rect(96, 16, 8, 22, 1)
            
            # 행복한 눈웃음 (> <)
            display2.line(42, 23, 49, 27, 0)
            display2.line(42, 31, 49, 27, 0)
            display2.line(86, 23, 79, 27, 0)
            display2.line(86, 31, 79, 27, 0)
            
            # 수화기
            display2.fill_rect(14, 20, 6, 20, 1)
            display2.fill_rect(10, 18, 10, 4, 1)
            display2.fill_rect(10, 38, 10, 4, 1)
            display2.line(20, 30, 32, 35, 1)
            
            # 신나서 벌린 입 (화상전화로 주인 목소리 듣고 신난 모습)
            display2.fill_rect(60, 37, 8, 6, 0)
            # 볼터치
            display2.line(35, 35, 33, 38, 0)
            display2.line(93, 35, 91, 38, 0)
            display2.show()
            
            # 수락 확인 징글음 (삐리링!)
            piezo.duty_u16(1000)
            for freq in (784, 988, 1175):
                piezo.freq(freq)
                sleep(0.08)
            piezo.duty_u16(0)
        except Exception as e:
            print("Call Accept Display Error:", e)

    elif v == 'call_end':
        # 통화 종료 시: 대기화면으로 원복하고 삑 소리 연주
        try:
            set_oled_display(1)
            piezo.duty_u16(1000)
            piezo.freq(392)
            sleep(0.15)
            piezo.duty_u16(0)
        except Exception as e:
            print("Call End Display Error:", e)

p.on_write(on_rx)

# 초기 대기화면 드로잉
display2.text("== Smart Hotel ==", 8, 4, 1)
display2.text("Smart Dog Suite", 8, 24, 1)
display2.text("Waiting BLE...", 8, 44, 1)
display2.show()

print("Smart Dog Suite System Live. Waiting for BLE connection...")

# 터치 센서의 플로팅 노이즈 필터링 함수 (Active-Low 기준: 10ms 간격으로 3번 연속 LOW(0)인지 검증)
def read_touch_stable(pin):
    for _ in range(3):
        if pin.value() == 1:
            return 0
        sleep_ms(10)
    return 1

# 6. 메인 프로그램 루프
dht_timer = 0
temp_val = 24
humi_val = 50
loop_count = 0
current_play_step = 1

while True:
    # 1. 정전식 터치 센서 감지 (D17, D5, D18, D19 개별 실시간 감지)
    t1 = read_touch_stable(touch1)
    t2 = read_touch_stable(touch2)
    t3 = read_touch_stable(touch3)
    t4 = read_touch_stable(touch4)

    # 2. 물리 스위치 감지 (D16 - 3핀 스위치)
    sw = read_touch_stable(limit_switch)

    # 터치센서 개별 트리거 작동
    if t1 and not touch1_prev:
        trigger_play_mode(1)
    if t2 and not touch2_prev:
        trigger_play_mode(2)
    if t3 and not touch3_prev:
        trigger_play_mode(3)
    if t4 and not touch4_prev:
        trigger_play_mode(4)

    # D16 단일 터치 센서 대신, D16에 연결된 물리 스위치를 밟으면 주인을 화상 호출!
    if sw and not limit_switch_prev:
        trigger_owner_call()

    touch1_prev = t1
    touch2_prev = t2
    touch3_prev = t3
    touch4_prev = t4
    limit_switch_prev = sw

    # 1초에 한 번만 (0.05초 * 20번 = 1초) 센서 측정, 화면 출력, 타이머 연산 등을 수행
    loop_count += 1
    
    # 0.5초(10틱)마다 웹 대시보드의 원격 제어 명령 수신
    if loop_count % 10 == 0:
        poll_commands()
        
    if loop_count >= 20:
        loop_count = 0

        # 1. 5초 간격 온습도 정기 측정
        dht_timer += 1
        if dht_timer >= 5:
            dht_timer = 0
            try:
                d.measure()
                temp_val = d.temperature()
                humi_val = d.humidity()
                cds_val = cds.read()
                
                p.send("temp : " + str(temp_val) + "\n")
                p.send("humi : " + str(humi_val) + "\n")
                p.send(str(cds_val) + "\n")
                p.send("feed_countdown:{}\n".format(feed_seconds))
            except Exception as e:
                print("DHT11 sensor read failed:", e)

        # 2. 실내 온도/습도 임계치 이탈 경고 체크
        is_abnormal = (temp_val < 15 or temp_val > 30 or humi_val < 30 or humi_val > 70)
        
        if is_abnormal:
            p.send("env_alert:1\n")
            # "삐삐" 경고음 (Double Beep)
            for _ in range(2):
                piezo.duty_u16(1000)
                piezo.freq(880)
                sleep(0.08)
                piezo.duty_u16(0)
                sleep(0.08)
        else:
            p.send("env_alert:0\n")

        # 3. 조명 상태 제어 (조도 센서 연동)
        if not light_toggle_active:
            R_pwm.duty_u16(0)
            G_pwm.duty_u16(0)
            B.value(0)
        else:
            if is_abnormal:
                R_pwm.duty_u16(65535)
                G_pwm.duty_u16(0)
                B.value(0)
            else:
                cds_value = cds.read()
                green_duty = int((4095 - cds_value) / 4095 * 65535)
                green_duty = max(1000, min(65535, green_duty))
                
                R_pwm.duty_u16(0)
                G_pwm.duty_u16(green_duty)
                B.value(0)

        # 4. 급식 카운트다운 타이머 관리
        if feed_seconds > 0:
            feed_seconds -= 1
            if feed_seconds % 10 == 0:
                p.send("feed_countdown:{}\n".format(feed_seconds))
        else:
            trigger_feeding()

        # 5. LCD 화면 정보 출력 (온습도, 현재시각, 급식 잔여 시간)
        try:
            t = rtc.datetime()
            time_str = "{:02d}:{:02d}".format(t[4], t[5])
            
            ch = feed_seconds // 3600
            cm = (feed_seconds % 3600) // 60
            cs = feed_seconds % 60
            countdown_str = "{:02d}:{:02d}:{:02d}".format(ch, cm, cs)
            
            line0 = "T:{}C H:{}%".format(temp_val, humi_val)
            line0 = "{:<16}".format(line0)
            
            line1 = "{}   {}".format(time_str, countdown_str)
            line1 = "{:<16}".format(line1)
            
            if line0 != prev_lcd_line0:
                lcd.move_to(0, 0)
                lcd.putstr(line0)
                prev_lcd_line0 = line0
                
            if line1 != prev_lcd_line1:
                lcd.move_to(0, 1)
                lcd.putstr(line1)
                prev_lcd_line1 = line1
        except Exception as e:
            print("LCD write error:", e)

        # 1초 주기로 수집된 센서 데이터를 서버로 전송
        flush_buffer()

    sleep(0.05)
