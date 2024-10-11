import time
import board
import audiocore
import audiomixer
import audiobusio
import digitalio
import math
import busio
import json
from os import listdir

from mpu6500 import MPU6500  # Assuming you have a library for the MPU6500
from random import randint

import neopixel

# Initialize I2C bus on GPIO0 (SDA) and GPIO1 (SCL)
i2c_bus = busio.I2C(scl=board.GP1, sda=board.GP0)

# Initialize the MPU6500
mpu = MPU6500(i2c_bus, address=0x68)

# Initialize pull up pin on GP15
pin = digitalio.DigitalInOut(board.GP15)
pin.direction = digitalio.Direction.INPUT
pin.pull = digitalio.Pull.UP

i2s_bclk = board.GP6  # BCK (Bit Clock) connected to GPIO6
i2s_wsel = board.GP7  # LRC (Word Select/Left-Right Clock) connected to GPIO7
i2s_data = board.GP8  # DIN (Data Input) connected to GPIO8

num_voices = 4

audio = audiobusio.I2SOut(bit_clock=i2s_bclk, word_select=i2s_wsel, data=i2s_data)

volume_0_wav = audiocore.WaveFile(open("/other_sounds/volume_0.wav", "rb"))
volume_25_wav = audiocore.WaveFile(open("/other_sounds/volume_25.wav", "rb"))
volume_50_wav = audiocore.WaveFile(open("/other_sounds/volume_50.wav", "rb"))
volume_75_wav = audiocore.WaveFile(open("/other_sounds/volume_75.wav", "rb"))
volume_100_wav = audiocore.WaveFile(open("/other_sounds/volume_100.wav", "rb"))

mixer = audiomixer.Mixer(
    voice_count=num_voices,
    sample_rate=16000,
    channel_count=1,
    bits_per_sample=16,
    samples_signed=True,
)
audio.play(mixer)  # attach mixer to audio playback

# set some initial levels
mixer.voice[0].level = 0
mixer.voice[1].level = 0.0
mixer.voice[2].level = 0.0
mixer.voice[3].level = 1


def load_profile(profile_directory):
    global swingl
    global swingh
    global clsh
    global blade_in
    global blade_out
    global hum_wav
    global select_wav

    global WINDOW_SIZE
    global FLASH_WINDOW_SIZE_MIN
    global FLASH_WINDOW_SIZE_MAX
    global FLASH_RANGE_OFFSET
    global COLOR
    global AUGMENTED_COLOR
    global CLASH_THRESHOLD

    # read setting options
    with open(profile_directory + "config.json", "r") as file:
        config = json.load(file)

        WINDOW_SIZE = config["extension_window_size"]
        FLASH_WINDOW_SIZE_MIN = config["flash_window_size_min"]
        FLASH_WINDOW_SIZE_MAX = config["flash_window_size_max"]
        FLASH_RANGE_OFFSET = config["flash_range_offset"]
        COLOR = config["color"]
        AUGMENTED_COLOR = config["augmented_color"]
        CLASH_THRESHOLD = config["clash_threshold"]

    hum_wav = audiocore.WaveFile(open(profile_directory + "hum01.wav", "rb"))
    select_wav = audiocore.WaveFile(open(profile_directory + "select.wav", "rb"))

    mixer.voice[0].play(hum_wav, loop=True)

    swingl_files_count = 0
    swingh_files_count = 0
    clsh_files_count = 0
    in_files_count = 0
    out_files_count = 0

    for filename in listdir(profile_directory):
        if filename.startswith("swingl"):
            swingl_files_count += 1
        if filename.startswith("swingh"):
            swingh_files_count += 1
        if filename.startswith("clsh"):
            clsh_files_count += 1
        if filename.startswith("in"):
            in_files_count += 1
        if filename.startswith("out"):
            out_files_count += 1

    if swingl_files_count != swingh_files_count:
        print("swingh and swingl must come in pairs")

    swingl = [0] * swingl_files_count
    swingh = [0] * swingh_files_count
    clsh = [0] * clsh_files_count
    blade_in = [0] * in_files_count
    blade_out = [0] * out_files_count

    for filename in listdir(profile_directory):
        if filename.endswith(".wav") and filename.startswith("swingl"):
            number = int(filename[6:8]) - 1
            file_path = profile_directory + filename
            print(f"loading file {filename} into swingl with number {number}")
            swingl[int(number)] = audiocore.WaveFile(open(file_path, "rb"))
        if filename.endswith(".wav") and filename.startswith("swingh"):
            number = int(filename[6:8]) - 1
            file_path = profile_directory + filename
            print(f"loading file {filename} into swingh with number {number}")
            swingh[int(number)] = audiocore.WaveFile(open(file_path, "rb"))
        if filename.endswith(".wav") and filename.startswith("clsh"):
            number = int(filename[4:6]) - 1
            file_path = profile_directory + filename
            print(f"loading file {filename} into clsh with number {number}")
            clsh[int(number)] = audiocore.WaveFile(open(file_path, "rb"))
        if filename.endswith(".wav") and filename.startswith("in"):
            number = int(filename[2:4]) - 1
            file_path = profile_directory + filename
            print(f"loading file {filename} into blade_in with number {number}")
            blade_in[int(number)] = audiocore.WaveFile(open(file_path, "rb"))
        if filename.endswith(".wav") and filename.startswith("out"):
            number = int(filename[3:5]) - 1
            file_path = profile_directory + filename
            print(f"loading file {filename} into blade_out with number {number}")
            blade_out[int(number)] = audiocore.WaveFile(open(file_path, "rb"))

    print(swingl)
    print(swingh)
    print(clsh)
    print(blade_in)
    print(blade_out)


def get_wav_file(file_type):
    if file_type == "swing":
        file_number = randint(0, len(swingl) - 1)
        # print(file_number)
        return (swingl[file_number], swingh[file_number])
    elif file_type == "clash":
        file_number = randint(0, len(clsh) - 1)
        # print(file_number)
        return clsh[file_number]
    elif file_type == "in":
        file_number = randint(0, len(blade_in) - 1)
        return blade_in[file_number]
    elif file_type == "out":
        file_number = randint(0, len(blade_out) - 1)
        return blade_out[file_number]


def get_next_line(file_handler):
    while True:
        line = file_handler.readline()
        if not line.startswith("#"):
            return line.replace("\n", "").replace("\r", "")


def get_available_profiles():
    # List folders in /profiles/
    available_profiles = [
        folder for folder in listdir(profiles_path) if listdir(profiles_path + folder)
    ]
    return available_profiles


def save_selection(profile_name):
    global VOLUME

    print(f"Saving active profile {profile_name} and volume {VOLUME}")
    with open("/config.txt", "w") as file:
        file.write(profile_name + "\n")
        file.write(str(VOLUME) + "\n")


def select_profile():
    global mpu
    global mixer
    global last_accel
    global last_timestamp
    global VOLUME
    global select_wav
    global COLOR
    global STRIP
    global STRIP2
    global volume_0_wav
    global volume_25_wav
    global volume_50_wav
    global volume_75_wav
    global volume_100_wav

    count_button_hold = 0
    current_selection = 0
    last_iter_button_pressed = False

    available_profiles = get_available_profiles()
    selected_profile = available_profiles[0]
    if mixer.voice[3].level == 0:
        mixer.voice[3].level = 0.25
    load_profile("/profiles/" + available_profiles[current_selection] + "/")
    STRIP.fill(COLOR)
    STRIP2.fill(COLOR)
    mixer.voice[3].play(select_wav)

    while not pin.value:
        pass

    while True:
        accel = mpu.acceleration
        accel_magnitude = (accel[0] ** 2 + accel[1] ** 2 + accel[2] ** 2) / 10
        current_timestamp = time.monotonic()
        d_accel = (accel_magnitude - last_accel) / (current_timestamp - last_timestamp)
        d_accel_pos = abs(d_accel)
        last_accel = accel_magnitude
        last_timestamp = current_timestamp

        if d_accel_pos >= 500:
            if VOLUME == 0:
                VOLUME = 0.25
                mixer.voice[3].level = 0.25
                mixer.voice[3].play(volume_25_wav)
                print("volume 25")
            elif VOLUME == 0.25:
                VOLUME = 0.50
                mixer.voice[3].play(volume_50_wav)
                print("volume 50")
            elif VOLUME == 0.50:
                VOLUME = 0.75
                mixer.voice[3].play(volume_75_wav)
                print("volume 75")
            elif VOLUME == 0.75:
                VOLUME = 1
                mixer.voice[3].play(volume_100_wav)
                print("volume 100")
            elif VOLUME == 1:
                VOLUME = 0
                mixer.voice[3].level = 0.25
                mixer.voice[3].play(volume_0_wav)
                time.sleep(2)
                print("volume 0")
            time.sleep(0.5)
            mixer.voice[3].level = VOLUME

        if not pin.value:
            last_iter_button_pressed = True
            count_button_hold += 1

            if count_button_hold == 50:
                save_selection(available_profiles[current_selection])
                STRIP.fill(BLACK)
                STRIP2.fill(BLACK)
                while not pin.value:
                    pass
                return
        elif pin.value and last_iter_button_pressed:
            last_iter_button_pressed = False
            current_selection += 1
            current_selection = current_selection % len(available_profiles)
            if mixer.voice[3].level == 0:
                mixer.voice[3].level = 0.25
            load_profile("/profiles/" + available_profiles[current_selection] + "/")
            mixer.voice[3].play(select_wav)
            STRIP.fill(COLOR)
            STRIP2.fill(COLOR)
        time.sleep(0.05)


# Read configuration
with open("/config.txt", "r") as file:
    profile = get_next_line(file)
    VOLUME = float(get_next_line(file))

mixer.voice[3].level = VOLUME
profiles_path = "/profiles/"
profile_path = profiles_path + profile  # Joining path manually

# Verify if profile folder exists
if not listdir(profile_path):
    print(f"No profile found at {profile_path}.")

    available_profiles = get_available_profiles()

    if available_profiles:
        # Set profile to the first available folder
        profile = available_profiles[0]
        profile_path = profiles_path + profile

print(f"Using profile: {profile}")
# add trailing slash
profile_path = profile_path + "/"

load_profile(profile_path)

mixer.voice[0].play(hum_wav, loop=True)
mixer.voice[1].play(swingl[0], loop=True)
mixer.voice[2].play(swingh[0], loop=True)

# initialize strip options
PIXEL_COUNT = 115
DATA_PIN = board.GP2
SECOND_DATA_PIN = board.GP3
BLACK = (0, 0, 0)

STRIP = neopixel.NeoPixel(
    DATA_PIN,
    PIXEL_COUNT,
    bpp=3,
    brightness=1,
    auto_write=True,
    pixel_order=neopixel.GRB,
)
STRIP2 = neopixel.NeoPixel(
    SECOND_DATA_PIN,
    PIXEL_COUNT,
    bpp=3,
    brightness=1,
    auto_write=True,
    pixel_order=neopixel.GRB,
)


def extend():
    global STRIP
    global STRIP2
    global WINDOW_SIZE
    global AUGMENTED_COLOR
    global VOLUME

    # ensure strip is black before extending
    STRIP.fill(BLACK)
    STRIP2.fill(BLACK)

    mixer.voice[0].level = 0
    mixer.voice[1].level = 0
    mixer.voice[2].level = 0

    mixer.voice[3].level = VOLUME
    mixer.voice[3].play(get_wav_file("out"))

    for i in range(-WINDOW_SIZE, PIXEL_COUNT - 2, 3):
        # set start of window to augmented color
        start_of_window = min(i + WINDOW_SIZE, PIXEL_COUNT - 3)
        end_of_window = max(max(i, 0), 0)
        STRIP[start_of_window : start_of_window + 3] = (AUGMENTED_COLOR,) * 3
        STRIP2[start_of_window : start_of_window + 3] = (AUGMENTED_COLOR,) * 3
        # set end of window to normal color
        STRIP[end_of_window : end_of_window + 3] = (COLOR,) * 3
        STRIP2[end_of_window : end_of_window + 3] = (COLOR,) * 3


def retract():
    global STRIP
    global STRIP2
    global VOLUME

    STRIP.fill(COLOR)
    STRIP2.fill(COLOR)

    mixer.voice[0].level = 0
    mixer.voice[1].level = 0
    mixer.voice[2].level = 0

    mixer.voice[3].level = VOLUME
    mixer.voice[3].play(get_wav_file("in"))

    step = -3
    for i in range(PIXEL_COUNT - 3, -1, step):
        STRIP[i] = BLACK
        STRIP2[i] = BLACK
        STRIP[i + 1] = BLACK
        STRIP2[i + 1] = BLACK
        STRIP[i + 2] = BLACK
        STRIP2[i + 2] = BLACK

    STRIP[0] = BLACK
    STRIP2[0] = BLACK


def clash():
    global STRIP
    global STRIP2
    global AUGMENTED_COLOR
    global COLOR
    global mixer
    global wave3
    global VOLUME
    global FLASH_RANGE_OFFSET
    global FLASH_WINDOW_SIZE_MAX
    global FLASH_WINDOW_SIZE_MIN

    bright_point = randint(FLASH_RANGE_OFFSET, PIXEL_COUNT - FLASH_RANGE_OFFSET - 1)
    flash_window_size = randint(FLASH_WINDOW_SIZE_MIN, FLASH_WINDOW_SIZE_MAX)

    end_tip = min(bright_point + flash_window_size, PIXEL_COUNT - 1)
    beginning_tip = max(bright_point - flash_window_size, 0)
    STRIP[bright_point:end_tip] = (AUGMENTED_COLOR,) * (end_tip - bright_point)
    STRIP2[beginning_tip:bright_point] = (AUGMENTED_COLOR,) * (
        bright_point - beginning_tip
    )

    mixer.voice[0].level = 0.5
    mixer.voice[1].level = 0
    mixer.voice[2].level = 0

    mixer.voice[3].level = VOLUME
    mixer.voice[3].play(get_wav_file("clash"))

    time.sleep(0.25)
    STRIP.fill(COLOR)
    STRIP2.fill(COLOR)


axis_1_3_rotation = 0


def handle_audio(x):  # calculate hum magnitude
    global mixer
    global axis_1_3_rotation
    global VOLUME

    y_at_x = -0.30 * math.sin(6 * x + 5) + 0.5

    # calculate swingl magnitude
    if 0 < x < 0.3:
        f_at_x = 0.4 * math.sin(10 * x + 4.9) + 0.393
    elif 0.3 <= x < 0.7:
        f_at_x = -1.976 * x + 1.385
    else:
        f_at_x = 0

    # calculate swingh magnitude
    if 0 < x < 0.3:
        g_at_x = 0
        axis_1_3_rotation = 0
    elif 0.3 <= x < 0.7:
        g_at_x = 1.976 * x - 0.59
    else:
        g_at_x = 1
        axis_1_3_rotation += abs(gyro[0]) + abs(gyro[2])
        # print(axis_1_3_rotation)

        # change g_x and f_x according to how many degrees of rotation was recorded, 20000 for 90 degrees
        if 20000 <= axis_1_3_rotation and axis_1_3_rotation < 30000:
            pitch_phase = (axis_1_3_rotation - 20000) / 10000
            f_at_x = pitch_phase
            g_at_x = 1 - pitch_phase
        elif 30000 <= axis_1_3_rotation < 60000:
            f_at_x = 1
            g_at_x = 0
        elif 60000 <= axis_1_3_rotation and axis_1_3_rotation < 80000:
            pitch_phase = (axis_1_3_rotation - 60000) / 20000
            f_at_x = 1 - pitch_phase
            g_at_x = pitch_phase
            axis_1_3_rotation = 0

    print(y_at_x, f_at_x, g_at_x, axis_1_3_rotation)
    mixer.voice[0].level = y_at_x * VOLUME
    mixer.voice[1].level = f_at_x * VOLUME
    mixer.voice[2].level = g_at_x * VOLUME


# initialize loop variables
IS_TURNED_ON = False
CONSECUTIVE_ROTATION = 0
VALID_TURNS = 0

last_timestamp = time.monotonic()
last_accel = 0

min_accel = 0
max_accel = 0
count_button_hold = 0
while True:
    gyro = mpu.gyro
    accel = mpu.acceleration

    if gyro[1] < -400 and abs(gyro[0]) < 150 and abs(gyro[2]) < 150:
        print("turn detected")
        CONSECUTIVE_ROTATION += 1
    else:
        CONSECUTIVE_ROTATION = 0
        VALID_TURNS -= 1

    if CONSECUTIVE_ROTATION >= 3 and not IS_TURNED_ON:
        VALID_TURNS = 7
    elif CONSECUTIVE_ROTATION >= 10 and IS_TURNED_ON:
        VALID_TURNS = 10

    if not pin.value:
        count_button_hold += 1
    else:
        count_button_hold = 0

    if count_button_hold >= 3 and not IS_TURNED_ON:
        select_profile()

    if VALID_TURNS >= 0 and gyro[1] > 2 or not pin.value:
        print("switching state")
        VALID_TURNS = 0
        CONSECUTIVE_ROTATION = 0
        if IS_TURNED_ON:
            IS_TURNED_ON = False
            retract()
        else:
            IS_TURNED_ON = True
            extend()

    if IS_TURNED_ON:
        # handle rotation calculation
        gyro_magnitude = gyro[0] ** 2 + gyro[2] ** 2

        # handle acceleration calculation
        accel_magnitude = (accel[0] ** 2 + accel[1] ** 2 + accel[2] ** 2) / 10
        current_timestamp = time.monotonic()
        d_accel = (accel_magnitude - last_accel) / (current_timestamp - last_timestamp)
        d_accel_pos = abs(d_accel)
        last_accel = accel_magnitude
        last_timestamp = current_timestamp

        x = max(min(gyro_magnitude / 100000, 1), 0)
        if x < 0.01:
            (low, high) = get_wav_file("swing")
            mixer.voice[1].play(low, loop=True)
            mixer.voice[2].play(high, loop=True)

        if d_accel_pos > CLASH_THRESHOLD:
            clash()
        else:
            handle_audio(x)

        time.sleep(0.01)
    else:
        print(CONSECUTIVE_ROTATION, VALID_TURNS, gyro)
        time.sleep(0.05)
