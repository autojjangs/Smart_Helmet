# Smart_Helmet

🚨 라즈베리파이 실기기 세팅 시 주의사항 (필수)
라즈베리파이는 기본적으로 이 우체국('/dev/serial0') 기능을 '리눅스 터미널 로그인용'으로 쓰고 있어서 막혀있습니다.
나중에 라즈베리파이에서 GPS를 꽂기 전에 반드시 이 설정을 한 번 풀어주셔야 합니다.

[라즈베리파이 터미널에서]

sudo raspi-config 입력

3 Interface Options 선택

I5 Serial Port 선택

"Would you like a login shell to be accessible over serial?" ➔ [No] 선택 (중요!)

"Would you like the serial port hardware to be enabled?" ➔ [Yes] 선택

재부팅 (sudo reboot)

이 세팅만 딱 마치고 선을 꽂으시면, 코드 수정 없이 GPS 데이터가 라즈베리파이로 미친 듯이 쏟아져 들어오기 시작할 겁니다!