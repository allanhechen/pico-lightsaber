from neopixel import Neopixel  # type: ignore
from time import sleep_ms
from time import ticks_ms
from random import randint
from machine import I2C, Pin, Timer, I2S, SPI
from mpu6500 import MPU6500

## testing
sleep_ms(1000)
led = Pin(25, Pin.OUT)
led.toggle()
## end testing

EXTEND = 1
RETRACT = 2
CLASH = 3

# initialize global variables
IS_TURNED_ON = False
LAST_BUTTON_PRESS = 0
LAST_CLASH_TIME = 0
DEBOUNCE_ACTIVE = False
timer = Timer()
next_action = None
CONSECUTIVE_ROTATION = 0
VALID_TURNS = 0
bytes_read = 0
swing0_state = 0
swing25_state = 0
swing50_state = 0
swing75_state = 0
swing100_state = 0

# initialize strip options
PIXEL_COUNT = 115
DATA_PIN = 2
SECOND_DATA_PIN = 3

STRIP = Neopixel(PIXEL_COUNT, 0, DATA_PIN, "GRB")
STRIP.brightness(100)
STRIP2 = Neopixel(PIXEL_COUNT, 1, SECOND_DATA_PIN, "GRB")
STRIP2.brightness(100)


# extension options
WINDOW_SIZE = (
    20  # window size for extending the blade, multiplied by speed given by gyroscope
)

# clashing options
FLASH_DURATION = 10  # flash duration in iterations, increase for a longer flash duration when striking
FLASH_RANGE_OFFSET = 0  # number of pixels away from the edges the brightest spot for a flash can be when striking
FLASH_WINDOW_SIZE_MIN = (
    25  # number of pixels until the bright pixel returns to the normal pixel
)
FLASH_WINDOW_SIZE_MAX = PIXEL_COUNT - 1

# swing options
SWING_PIXEL_COUNT = 50
MAXIMUM_SWING_SPEED = 20

# hardware options
CLASH_PIN = 5
CLASH_DEBOUNCE_TIME = 150

if FLASH_RANGE_OFFSET > PIXEL_COUNT:
    print("FLASH RANGE OFFSET MUST BE BIGGER THAN PIXEL COUNT")

# initialize possible color options
WHITE = (225, 225, 225)
BLACK = (0, 0, 0)
BLUE = (0, 0, 225)
RED = (225, 0, 0)
GREEN = (0, 225, 0)

# choose blade color
COLOR = RED
AUGMENTED_COLOR = (
    (
        255 if COLOR[0] != 0 else 10,
        255 if COLOR[1] != 0 else 10,
        255 if COLOR[2] != 0 else 10,
    )
    if COLOR != WHITE
    else (255, 255, 255)
)
COLOR_DIFFERENCE = (
    AUGMENTED_COLOR[0] - COLOR[0],
    AUGMENTED_COLOR[1] - COLOR[1],
    AUGMENTED_COLOR[2] - COLOR[2],
)


def extend():
    global STRIP
    global STRIP2
    global WINDOW_SIZE
    global AUGMENTED_COLOR

    # ensure strip is black before extending
    STRIP.fill(BLACK)
    STRIP2.fill(BLACK)

    play_sound()

    for i in range(-WINDOW_SIZE, PIXEL_COUNT, 2):
        if i % 20 == 0:
            play_sound()
        # set start of window to augmented color
        STRIP.set_pixel(min(i + WINDOW_SIZE, PIXEL_COUNT - 1), AUGMENTED_COLOR)
        STRIP2.set_pixel(min(i + WINDOW_SIZE, PIXEL_COUNT - 1), AUGMENTED_COLOR)
        # set end of window to normal color
        STRIP.set_pixel(max(i, 0), COLOR)
        STRIP2.set_pixel(max(i, 0), COLOR)
        STRIP.show()
        STRIP2.show()


def retract():
    global STRIP
    global STRIP2

    play_sound()
    step = -2
    for i in range(PIXEL_COUNT - 1, -1, step):
        if i % 20 == 0:
            play_sound()
        STRIP.set_pixel_line(i, i - step, BLACK)
        STRIP2.set_pixel_line(i, i - step, BLACK)
        STRIP.show()
        STRIP2.show()
        # sleep_ms(10)
    STRIP.fill(BLACK)
    STRIP2.fill(BLACK)
    STRIP.show()
    STRIP2.show()


def clash():
    global STRIP
    global STRIP2
    global target_status

    bright_point = randint(FLASH_RANGE_OFFSET, PIXEL_COUNT - FLASH_RANGE_OFFSET - 1)
    flash_window_size = randint(FLASH_WINDOW_SIZE_MIN, FLASH_WINDOW_SIZE_MAX)
    for i in range(FLASH_DURATION, 0, -1):
        if i % 30 == 0:
            play_sound()
        actual_color = (
            int(COLOR[0] + (COLOR_DIFFERENCE[0] * i) / FLASH_DURATION),
            int(COLOR[1] + (COLOR_DIFFERENCE[1] * i) / FLASH_DURATION),
            int(COLOR[2] + (COLOR_DIFFERENCE[2] * i) / FLASH_DURATION),
        )
        STRIP.set_pixel_line_gradient(
            bright_point,
            min(bright_point + flash_window_size, PIXEL_COUNT - 1),
            actual_color,
            COLOR,
        )
        STRIP2.set_pixel_line_gradient(
            bright_point,
            min(bright_point + flash_window_size, PIXEL_COUNT - 1),
            actual_color,
            COLOR,
        )
        STRIP.set_pixel_line_gradient(
            bright_point, max(bright_point - flash_window_size, 0), COLOR, actual_color
        )
        STRIP2.set_pixel_line_gradient(
            bright_point, max(bright_point - flash_window_size, 0), COLOR, actual_color
        )
        STRIP.show()
        STRIP2.show()
        target_status = SWING0
    # reset blade color to account for edge cases
    STRIP.fill(COLOR)
    STRIP2.fill(COLOR)
    STRIP.show()
    STRIP2.show()


def swing(speed=0):
    """
    Change the blade tip color based on swing speed.

    Maximum swing speed is MAXIMUM_SWING_SPEED, all other speeds are calculated as a ratio to it.
    """
    global STRIP
    global target_status

    speed *= 5

    if speed <= 3:
        target_status = SWING0
    elif speed <= 10:
        target_status = SWING25
    elif speed <= 20:
        target_status = SWING50
    elif speed <= 30:
        target_status = SWING75
    else:
        target_status = SWING100
    play_sound()


def timer_callback(timer):
    global DEBOUNCE_ACTIVE
    DEBOUNCE_ACTIVE = False  # Allow processing of new interrupts


def clash_handler(pin):
    global DEBOUNCE_ACTIVE
    global IS_TURNED_ON
    global next_action

    print("clash")

    if not IS_TURNED_ON:
        return

    if not DEBOUNCE_ACTIVE:
        next_action = CLASH

        # Set the debounce flag
        DEBOUNCE_ACTIVE = True

        # Initialize timer for debounce period
        timer.init(
            mode=Timer.ONE_SHOT, period=CLASH_DEBOUNCE_TIME, callback=timer_callback
        )


# initialize button and clash sensor
clash_sensor = Pin(CLASH_PIN, Pin.IN, Pin.PULL_UP)
clash_sensor.irq(trigger=Pin.IRQ_FALLING, handler=clash_handler)

# initialize gyroscope
i2c = I2C(0, sda=Pin(0), scl=Pin(1), freq=40000)
sensor = MPU6500(i2c)
sensor.calibrate()

############## sound section

CLASH_FILE = open("/sound_files/clash.wav", "rb")
POWERON_FILE = open("/sound_files/poweron.wav", "rb")
POWEROFF_FILE = open("/sound_files/poweroff.wav", "rb")
# SWING100_FILE = open("/sound_files/swing100.wav", "rb")
# SWING75_FILE = open("/sound_files/swing75.wav", "rb")
# SWING50_FILE = open("/sound_files/swing50.wav", "rb")
# SWING25_FILE = open("/sound_files/swing25.wav", "rb")
# SWING0_FILE = open("so....")
swing0_entries = []
for i in range(45):
    swing0_entries.append(open(f"/swing0/segment_{i}.wav", "rb"))

swing25_entries = []
for i in range(20):
    swing25_entries.append(open(f"/swing25/segment_{i}.wav", "rb"))

swing50_entries = []
for i in range(20):
    swing50_entries.append(open(f"/swing50/segment_{i}.wav", "rb"))

swing75_entries = []
for i in range(20):
    swing75_entries.append(open(f"/swing75/segment_{i}.wav", "rb"))

swing100_entries = []
for i in range(20):
    swing100_entries.append(open(f"/swing100/segment_{i}.wav", "rb"))


SWING_100_75_FILE = open("/sound_files/swing_100_75.wav", "rb")
SWING_75_50_FILE = open("/sound_files/swing_75_50.wav", "rb")
SWING_50_25_FILE = open("/sound_files/swing_50_25.wav", "rb")
SWING_25_0_FILE = open("/sound_files/swing_25_0.wav", "rb")
SWING_0_25_FILE = open("/sound_files/swing_0_25.wav", "rb")
SWING_25_50_FILE = open("/sound_files/swing_25_50.wav", "rb")
SWING_50_75_FILE = open("/sound_files/swing_50_75.wav", "rb")
SWING_75_100_FILE = open("/sound_files/swing_75_100.wav", "rb")

# status codes that can be received
CLASH = 0
POWERON = 1
POWEROFF = 2
SWING100 = 3
SWING75 = 4
SWING50 = 5
SWING25 = 6
SWING0 = 7

# further internal status codes
# OFF = 8
SWING_100_75 = 9
SWING_75_50 = 10
SWING_50_25 = 11
SWING_25_0 = 12
SWING_0_25 = 13
SWING_25_50 = 14
SWING_50_75 = 15
SWING_75_100 = 16

# speaker configuration
SCK_PIN = 6  # BCLK
WS_PIN = 7  # LRC
SD_PIN = 8  # DIN
I2S_ID = 0
BUFFER_LENGTH_IN_BYTES = 5000

# global variables
current_file = POWERON_FILE
current_status = POWEROFF
target_status = POWEROFF
sound_set = None


silent = bytearray(1000)
buffer = bytearray(5000)
mv = memoryview(buffer)
speaker = I2S(
    I2S_ID,
    sck=Pin(SCK_PIN),
    ws=Pin(WS_PIN),
    sd=Pin(SD_PIN),
    mode=I2S.TX,
    bits=16,
    format=I2S.MONO,
    rate=24000,
    ibuf=BUFFER_LENGTH_IN_BYTES,
)


def get_appropriate_file():
    global current_status
    global current_file
    global reset_file
    global swing0_state
    global swing25_state
    global swing50_state
    global swing75_state
    global swing100_state

    if current_status == CLASH:
        current_file = CLASH_FILE
    elif current_status == POWERON:
        current_file = POWERON_FILE
    elif current_status == POWEROFF:
        current_file = POWEROFF_FILE
    elif current_status == SWING_100_75:
        current_file = SWING_100_75_FILE
    elif current_status == SWING_75_50:
        current_file = SWING_75_50_FILE
    elif current_status == SWING_50_25:
        current_file = SWING_50_25_FILE
    elif current_status == SWING_25_0:
        current_file = SWING_25_0_FILE
    elif current_status == SWING_0_25:
        current_file = SWING_0_25_FILE
    elif current_status == SWING_25_50:
        current_file = SWING_25_50_FILE
    elif current_status == SWING_50_75:
        current_file = SWING_50_75_FILE
    elif current_status == SWING_75_100:
        current_file = SWING_75_100_FILE

    elif current_status == SWING25:
        swing25_state = (swing25_state + 1) % 20
        current_file = swing25_entries[swing25_state]
    elif current_status == SWING50:
        swing50_state = (swing50_state + 1) % 20
        current_file = swing50_entries[swing50_state]
    elif current_status == SWING75:
        swing75_state = (swing75_state + 1) % 20
        current_file = swing75_entries[swing75_state]
    elif current_status == SWING100:
        swing100_state = (swing100_state + 1) % 20
        current_file = swing100_entries[swing100_state]
    # elif current_status == SWING100:
    else:
        swing0_state = (swing0_state + 1) % 45
        current_file = swing0_entries[swing0_state]
    current_file.seek(44)


def play_sound():
    global mv
    global current_file
    global speaker
    global current_status
    global silent
    global bytes_read
    global reset_file

    reset_file = False
    bytes_read = current_file.readinto(mv)

    # always finish reading current file
    if bytes_read != 0:
        speaker.write(mv[:bytes_read])
        # return only if we read a full buffer
        if bytes_read == BUFFER_LENGTH_IN_BYTES:
            return

    # handle poweroff state
    if current_status == POWEROFF and target_status == POWEROFF:
        speaker.write(silent)
        return
    elif (
        target_status == POWERON or target_status == POWEROFF or target_status == CLASH
    ):
        current_status = target_status
        reset_file = True
    # handle transitional status codes
    elif 9 <= current_status <= 16:
        # haha this is so ugly
        if current_status == SWING_100_75:
            current_status = SWING75
        elif current_status == SWING_75_50:
            current_status = SWING50
        elif current_status == SWING_50_25:
            current_status = SWING25
        elif current_status == SWING_25_0:
            current_status = SWING0
        elif current_status == SWING_0_25:
            current_status = SWING25
        elif current_status == SWING_25_50:
            current_status = SWING50
        elif current_status == SWING_50_75:
            current_status = SWING75
        elif current_status == SWING_75_100:
            current_status = SWING100
        reset_file = True

    # update new status if current status does not match
    if current_status != target_status:
        if current_status > target_status:
            current_status += 2 * (10 - current_status)
        elif current_status < target_status:
            current_status += 6
        reset_file = True

    get_appropriate_file()

    bytes_read = current_file.readinto(mv)
    if bytes_read == 0:
        print("failed to read")
        current_file.seek(44)
        bytes_read = current_file.readinto(mv)

    speaker.write(mv[:bytes_read])


speaker.write(silent)

############## end sound section

while True:
    if next_action == CLASH:
        next_action = None
        clash()

    accel_input = sensor.acceleration
    gyro_input = sensor.gyro

    target_status = SWING0
    # print(target_status, current_status)
    if gyro_input[1] < -4 and abs(gyro_input[0]) < 1.5 and abs(gyro_input[2] < 1.5):
        print("turn detected")
        CONSECUTIVE_ROTATION += 1
    else:
        CONSECUTIVE_ROTATION = 0
        VALID_TURNS -= 1

    if CONSECUTIVE_ROTATION >= 5 and not IS_TURNED_ON:
        VALID_TURNS = 5
    elif CONSECUTIVE_ROTATION >= 2 and IS_TURNED_ON:
        VALID_TURNS = 2

    # print(CONSECUTIVE_ROTATION, VALID_TURNS, gyro_input[1])
    if VALID_TURNS >= 0 and gyro_input[1] > 2:
        print("switching state")
        VALID_TURNS = 0
        CONSECUTIVE_ROTATION = 0
        if IS_TURNED_ON:
            IS_TURNED_ON = False
            target_status = POWEROFF
            retract()
        else:
            IS_TURNED_ON = True
            target_status = POWERON
            extend()

    gyro_magnitude = gyro_input[0] ** 2 + gyro_input[2] ** 2

    if not IS_TURNED_ON:
        sleep_ms(50)
    else:
        swing(gyro_magnitude)