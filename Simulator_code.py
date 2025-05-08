# SETUP - code libraries
import network 
import urequests
import ujson
from machine import SPI, I2C, RTC, time_pulse_us, ADC, Pin
import time
from mfrc522 import MFRC522
from hx711 import HX711
import random
import math


# Firebase Realtime Database URL
DATABASE_URL = "https://jbdb-21-default-rtdb.europe-west1.firebasedatabase.app/"
# Firebase Authentication API URL
FIREBASE_AUTH_URL = "https://identitytoolkit.googleapis.com/v1/accounts:signUp?key=AIzaSyBHoJxdF3YBoFTcDRbZX3iqfYNIBNTFM7s"

#set up wifi cred
WIFI_SSID = "MetroWest-WiFi" #Wifi SSID
WIFI_PASSWORD = "Mor444562" #Wifi Password 


#define Username, default as unknown
Username = "Unknown user"

# Distance Pin setup
trigger = Pin(14, Pin.OUT)  # Trigger pin on GPIO 14
echo = Pin(12, Pin.IN)       # Echo pin on GPIO 12

RPWM_Output = Pin(32, Pin.OUT)  # foward
LPWM_Output = Pin(33, Pin.OUT)  # back

# SETUP WEIGHT SENSOR
DT_PIN = 4 #data pin 
SCK_PIN_WEIGHT = 5 #clock pin

hx = HX711(DT_PIN, SCK_PIN_WEIGHT) #pin select

scale_factor = -17 / 40000  # scale factor

# reader setup
SCK_PIN_READER = 18   
MOSI_PIN = 22 
MISO_PIN = 21 
RST_PIN = 23  
SDA_PIN = 19

spi = SPI(1, baudrate=1000000, polarity=0, phase=0, sck=Pin(SCK_PIN_READER), mosi=Pin(MOSI_PIN), miso=Pin(MISO_PIN))
#create channel, 1mps, by default, Defines communication pins

mfrc522 = MFRC522(spi, gpioRst=RST_PIN, gpioCs=SDA_PIN)
#initialize the RC522 with spi, reset pin, chip select pin

# DISPLAY SETUP
ADDRESS = 0x27

LCD_CLEARDISPLAY = 0x01
LCD_RETURNHOME = 0x02
LCD_ENTRYMODESET = 0x04
LCD_DISPLAYCONTROL = 0x08
LCD_CURSORSHIFT = 0x10
LCD_FUNCTIONSET = 0x20
LCD_SETCGRAMADDR = 0x40
LCD_SETDDRAMADDR = 0x80
LCD_BACKLIGHT = 0x08
LCD_NOBACKLIGHT = 0x00

En = 0b00000100  
Rw = 0b00000010  
Rs = 0b00000001


""" I2c Class """
class I2cDevice: #class to communicate with the LCD with I2c
    
    def __init__(self, i2c, addr=ADDRESS): #instructor
        self.i2c = i2c #store the i2c
        self.addr = addr #store the addr

    def write_cmd(self, cmd): #func that send command to i2c
        self.i2c.writeto(self.addr, bytearray([cmd])) #send the cmd as a single byte to device with address
        time.sleep(0.0001) # short delay to allow the device time to process the command

    def write_data(self, data): #func for send data
        self.i2c.writeto(self.addr, bytearray([data | LCD_BACKLIGHT]))#send the data combined with backlight using OR
        time.sleep(0.0001) #short delay to allow the device time to process the data


""" LCD Class """        
class LCD: #class for interface with an I2c connected LCD
    
    def __init__(self, i2c, addr=ADDRESS): #lcd object with i2c
        self.lcd_device = I2cDevice(i2c, addr) #create an i2c device
        self.lcd_init() #initialize the lcd display DEF ONE DOWN

    def lcd_init(self): #func to initialize the lcd 
        self.lcd_write(0x03) #set to 8 bit mode. to reset him by standard
        self.lcd_write(0x02) #switch lcd to 4 bit mode

        self.lcd_write(LCD_FUNCTIONSET | 0x08 | 0x00)  #set lcd for 4 bit mode, 2 lines, normal font
        self.lcd_write(LCD_DISPLAYCONTROL | 0x04)  #Turn on display, no underline and blinking
        self.lcd_write(LCD_CLEARDISPLAY) # clear the display
        self.lcd_write(LCD_ENTRYMODESET | 0x02)  #set text entry mode (right after every note)/
        time.sleep(0.2) #delay to ensure lcd is ready

    def lcd_strobe(self, data): #pulse the enable pin for data into the lcd.WITHOUT IT LCD WON'T KNOW DATA IS READY
        self.lcd_device.write_data(data | En) #send enable high
        time.sleep(0.0005) # wait for signal stability
        self.lcd_device.write_data(data & ~En) #set enable low
        time.sleep(0.0001) #stability

    def lcd_write(self, cmd, mode=0): #write a full cmd or data to the lcd. mode 0 = cmd
        self.lcd_device.write_data(mode | (cmd & 0xF0)) #send the higher 4 bits of the command (11110000)
        self.lcd_strobe(mode | (cmd & 0xF0)) #strobe - lcd is ready

        self.lcd_device.write_data(mode | ((cmd << 4) & 0xF0)) #send the lower 4 bits of the command
        self.lcd_strobe(mode | ((cmd << 4) & 0xF0)) #strobe - lcd is ready

    def lcd_write_char(self, charvalue, mode=1): #write a char (instead of command) to the lcd. mode 1 = data
        self.lcd_device.write_data(mode | (charvalue & 0xF0)) #send the higher 4 bits of data (11110000)
        self.lcd_strobe(mode | (charvalue & 0xF0)) #strobe - lcd is ready

        self.lcd_device.write_data(mode | ((charvalue << 4) & 0xF0)) #send the lower 4 bits of data
        self.lcd_strobe(mode | ((charvalue << 4) & 0xF0)) #strobe - lcd is ready

    def lcd_display_string(self, string, line): #display a full string in a specific line
        if line == 1:
            self.lcd_write(0x80)  # set first line
        elif line == 2:
            self.lcd_write(0xC0)  # set second line
        elif line == 3:
            self.lcd_write(0x94)  #set third line
        elif line == 4:
            self.lcd_write(0xD4)  # set fourth line - every num in this 4 is by lcd memory
        else:
            raise ValueError("Line parameter must be 1, 2, 3, or 4.") #error if line number is invalid

        for char in string: #for each character in the string
            self.lcd_write_char(ord(char), Rs) #send the character to the lcd. RS means mode 1

    def lcd_clear(self): #clear the entire display
        self.lcd_write(LCD_CLEARDISPLAY) #clear the screen
        self.lcd_write(LCD_RETURNHOME) #move cursor to the home position

    def backlight_on(self, set_to_on=True): # control the backlight (on/off)
        if set_to_on: #if
            self.lcd_device.write_cmd(LCD_BACKLIGHT) #turn backlight on
        else:
            self.lcd_device.write_cmd(LCD_NOBACKLIGHT) # turn backlight off

# SETUP THE I2C ON ESP32
i2c = I2C(scl=Pin(26), sda=Pin(25), freq=400000)  

# CREATE LCD OBJECT
lcd = LCD(i2c)

""" Function to connect ESP32 to Wifi """
def connect_wifi():
    wifi = network.WLAN(network.STA_IF)
    wifi.active(True)
    if not wifi.isconnected():
        print("Connecting to Wi-Fi...")
        wifi.connect(WIFI_SSID, WIFI_PASSWORD)
        timeout = 10
        start_time = time.time()
        while not wifi.isconnected():
            if time.time() - start_time > timeout:
                print("Failed to connect to Wi-Fi")
                return False
            time.sleep(1) # Sleep time for 1 seconds
            
    print("Signal strength:", wifi.status('rssi'), "dBm") # Print signal strength
    print("Connected to Wi-Fi")
    return True
 
""" Function to get current timestamp """
def get_timestamp():
    # Get the current timestamp in DD-MM-YYYY format
    rtc = RTC()
    t = rtc.datetime()
    
    dd = f"{t[2]:02d}"  # Day (DD)
    mm = f"{t[1]:02d}"  # Month (MM)
    yyyy = f"{t[0]}"    # Year (YYYY)
    
    
    # Generate the inverted prefix for sorting based on YYYYMMDD
    # This will enable the workouts to be sorted by date
    inverted_prefix = 99999999 - int(f"{yyyy}{mm}{dd}")
    
    readable_date = f"{dd}-{mm}-{yyyy}"
    # Return the timestamp in the format "inverted_prefix-DD-MM-YYYY"
    return f"{inverted_prefix}-{readable_date}"


""" Function to randomly select an exercise """
"""In the gym this function will not be needed because the device will be for one exercise
but for testing we want different exercises"""
def get_exercise():
    #Randomly select an exercise from a list
    exercises = ["Bench Press", "Pulldown", "Squat", "Deadlift", "Shoulder Press", "Bicep Curl"]
    #list of exercises
    return random.choice(exercises) #Return a random exercise from list

""" Function to sanitize email to make format ready for database """
def sanitize_email(email):
    #Sanitize the email by replacing periods and '@' symbols with _
    return email.replace(".", "_").replace("@", "_")

""" Funtion that gets the rep distance and returns the range of motion """
def get_rom(distance):
    return min((distance / 25 * 100), 100) #Range of motion calculation
    # Calculation based on max distance (~25)

""" Funtion that gets the resting heart rate based on your workout level """
def get_resting_rate(level):
    lcd.lcd_clear()
    lcd.lcd_display_string("Reading heart",1)
    lcd.lcd_display_string("rate..", 2)
    
    time.sleep(2)
    rate = 0
    
    if level == "Beginner":
        rate = 80
    elif level == "Intermediate":
        rate = 70
    elif level == "Advanaced":
        rate = 60
    
    lcd.lcd_clear()
    lcd.lcd_display_string("Completed",1)
    
    return rate
    
"""--------------------------------- Firebase User Functions -------------------------------"""

""" Sign in or initialize a user by their chip_id """
def sign_in_user(chip_id):
    global Username # Import the global username
    sanitized_email = "" 
    level = ""
    
    chip_path = f"/chips/{chip_id}.json" # Chip path to access chip in database
    chip_url = f"{DATABASE_URL}{chip_path}" # Chip path Url in database

    # Check if the user exists based on the chip_id, if exists gets email and username
    email_user = user_exists(chip_url)
    
    if email_user:  # A user is found with this chip_id
        print("User exists in Firebase") 
        
        sanitized_email = sanitize_email(email_user["email"]) # Get the sanitized email from chip 
        Username = email_user["username"]  # Set global username
        level = email_user["level"] # Get user workout level

    else: # No user was found with this chip_id
        print("User not found, initializing user...")
        lcd.lcd_clear() 
        lcd.lcd_display_string("Chip not found", 1)
        lcd.lcd_display_string("Initializing user", 2)
        user_data = initialize_user()  # Initialize the user and return their data

        if user_data is None: # User initialization Failed
            print("User initialization failed")
            return "" # Sign Up failed, return blank
    
        Username = user_data["username"]  # Set the global Username
        email = user_data["email"] # Get the email from returned data
        level = user_data["level"] # Get user workout level
        
        sign_up_user(email, user_data["password"])  # Sign up the user
        add_chip(chip_id, email, Username, user_data["level"], chip_url) # Add the chip to the database
        sanitized_email = sanitize_email(email) # Set the sanitized email
    
    lcd.lcd_clear() 
    lcd.lcd_display_string("Log in successful", 1)
    return { "email": sanitized_email, "level": level }
    
    
""" Check if the user exists in the Firebase database based on the chip Url """
def user_exists(chip_url):
    
    print("Checking if user exists")
    try:
        response = urequests.get(chip_url)  # Get data from Firebase using Chip Url
        if response.status_code == 200: # HTTP response was successful
            data = response.json()  # Parse the JSON response
            username = data.get('username')  # Get the username from data
            email = data.get("email") # Get the email from data
            level = data.get("level") # Get the level from data
            response.close() # Close response
            
            return {"username":username, "email":email, "level": level} if username and email and level else None
            # Return if data available, else None
        
        else:
            response.close() # Close response
            return None # Return None
        
    except Exception as e: # Handle exceptions
        print("No User Found", e)  # Print fail message
        return None # Return None

""" Initialize a user in Firebase Realtime Database with inputs from the user """
def initialize_user():
    headers = {"Content-Type": "application/json"}  # Set headers for JSON
    global Username # Import the global Username
    
    while True: #Until User Signs Up
        try:
            # Username input - until valid username
            while True:
                Username = input("Enter username: ").strip()
                if Username:
                    break
                print("Username cannot be empty. Please try again.")
            
            # Email input - with validation
            while True:
                email = input("Enter email (With @ and .) : ").strip()
                if validate_email(email): # Validate email
                    break
                print("Invalid email format. Please enter a valid email.")
            
            # Age input 
            while True:
                try:
                    age = int(input("Enter Age : "))
                    if 14 <= age <= 100: 
                        break
                    print("Invalid age. Please enter a valid age.")
                    
                except ValueError: # Handle type exceptions
                    print("Invalid input. Please enter a number.")
                
            # Height input - within normal range
            while True:
                try:
                    height = float(input("Enter height (in cm): "))
                    if height > 50 and height < 250:  # Reasonable height range
                        break
                    print("Please enter a valid height between 0 and 250 cm.")
                    
                except ValueError: # Handle type exceptions
                    print("Invalid input. Please enter a number.")
            
            # Weight input - within normal range
            while True:
                try:
                    weight = float(input("Enter weight (in kg): "))
                    if weight > 0 and weight < 500:  # Reasonable weight range
                        break
                    print("Please enter a valid weight between 0 and 500 kg.")
                    
                except ValueError: # Handle type exceptions
                    print("Invalid input. Please enter a number.")
            
            # Password input - with validation
            while True:
                password = input("Enter password (at least 6 characters, with upper, lower, number): ")
                if validate_password(password): # Validate password
                    break
                print("Password must be at least 6 characters long and include uppercase, lowercase, and a number.")
            
            level = input("Enter Workout Level (Beginner, Intermediate, Advanced)")
            
            resting_rate = get_resting_rate(level)
            
            user_data = {  # Create user data dictionary with all parameters
                "username": Username,
                "email": email,
                "age": str(age),
                "height": height,
                "weight": weight,
                "level": level,
                "resting heart rate": resting_rate
            }
            #Create path for inserting user data
            email = sanitize_email(email) # Sanitize the email
            user_path = f"/users/{email}.json" # User path to access user data in database
            user_url = f"{DATABASE_URL}{user_path}" # User path Url in database
            
            response = urequests.put(user_url, data=ujson.dumps(user_data), headers=headers)  # Send PUT request for user data
            print("User Initialization Response:", response.text)  # Print response
            response.close()  # Close response
            
            user_data["password"] = password
            return user_data  # Return the complete user_data dictionary
        
        except Exception as e: # Handle exceptions
            print("Failed to initialize user:", e)  
            return None # Return None
        
""" Sign up a user in Firebase Authentication """
def sign_up_user(email, password):
    
    auth_data = {  # Create authentication data dictionary
        "email": email,
        "password": password,
        "returnSecureToken": True  # Request secure token
    }  
    headers = {"Content-Type": "application/json"}  # Set headers for JSON
    try:
        auth_response = urequests.post(FIREBASE_AUTH_URL, data=ujson.dumps(auth_data), headers=headers)  
        # Send POST request for authentication data
        auth_result = auth_response.json()  # Get JSON response
        auth_response.close()  # Close response
        if "error" in auth_result:  # Check if there's an error
            print("Firebase Auth Error:", auth_result["error"])  # Print error
            return None

        print("Firebase Auth Response: Success")  # Print success
        
    except Exception as e: # Handle exceptions
        print("Failed to sign up user in Firebase Authentication:", e)  
        return None

""" Add a chip_id with an email and username in Firebase for Log In """
def add_chip(chip_id, email, username, level, chip_url):
    headers = {"Content-Type": "application/json"} # Set headers for JSON
    
    chip_data = { # Create chip data dictionary
        "chip_id": chip_id,
        "email": email,
        "username": username,
        "level": level
    }
    
    try:
        response = urequests.put(chip_url, data=ujson.dumps(chip_data), headers=headers) 
        # Send PUT request for chip data
        print("Chip association response:", response.text) # Print response
        
    except Exception as e: #handle exceptions
        print("Failed to associate chip:", e)
        
    finally:
        response.close() # Close response

""" Function to validate the email format """
def validate_email(email):

    if not email or '@' not in email: # Email contains '@'
        return False
    
    username, domain = email.split('@', 1) # At least one character before and after '@'
    
    if not username or '.' not in domain: # At least one character before '.' and after '@'
        return False
    
    return True

""" Function to validate password strength """
def validate_password(password):
    
    if len(password) < 6: #At least 6 characters long
        return False
    
    # Variables for checking password
    has_upper = False
    has_lower = False
    has_number = False
    
    for char in password:
        if char.isupper(): # Password has at least one uppercase letter
            has_upper = True
        elif char.islower(): # Password has at least one lowercase letter
            has_lower = True
        elif char.isdigit(): # Password has at least one number
            has_number = True
    
    return has_upper and has_lower and has_number


""" Function to send all exercise data to firebase database """
def send_data_to_firebase(sanitized_email, exercise, weight, overall_performance_score, overall_variability_score,
                          set_performance_scores, set_variability_scores, set_times, set_tut, rest_times,
                          average_rom, set_power, set_heartrate, reps, reps_time, reps_rom, reps_power, reps_heartrate):
    
    print("sending data")
    lcd.lcd_clear()
    lcd.lcd_display_string("Workout Completed", 1)
    lcd.lcd_display_string("Sending Data", 2)

    timestamp = get_timestamp() # Get current timestamp to send exercise end time
    workout_path = f"/workoutData/{sanitized_email}/{timestamp}.json" # Workout path to access exercise in database
    workout_url = f"{DATABASE_URL}{workout_path}" # Workout path Url in database
    
    # Build structured workout data for sending
    workout_data = { 
        exercise: { # Exercise name
            "sets": "3", # Overall set count
            "weight": str(weight), # Exercise Weight
            "overall_average_rom": f"{sum(average_rom)/3}%",  # Exercise Overall average range of motion
            "overall_performance_score": overall_performance_score, # Exercise overall performance score
            "overall_variability_score": overall_variability_score, # Exercise overall variability score
            "overall_tut": str(sum(set_tut)), # Exercise overall time under tension
            "overall_time": f"{(sum(set_times) + sum(rest_times)):.2f}", # Exercise overall time
            "average_heartrate": f"{(sum(set_heartrate)/3):.2f}", # Exercise average heartrate
            "overall_average_power": f"{(sum(set_power)/3):.2f}", # Exercise average power
            "sets_data": {}  # Holds data for each set
        }
    }
    
    for set_num in range(3): #Loop for each set
        set_data = {
            "set_time": str(set_times[set_num]), # Set time
            "average_rom": f"{average_rom[set_num]}%" if average_rom[set_num] else "0%", # Set average range of motion
            "set_performance_score": f"{set_performance_scores[set_num]:.2f}", # Set performance score
            "set_variability_scores": f"{set_variability_scores[set_num]:.2f}",# Set variability score
            "rest_time": str(rest_times[set_num]), # Set rest time
            "set_average_heartrate": str(set_heartrate[set_num]), # Set average heartrate
            "set_tut": str(set_tut[set_num]), # Set time under tension
            "set_average_power": f"{(set_power[set_num]):.2f}", # Set average power
            "reps": {}  # Holds data for each rep in the set
        }
        
        for rep_num in range(reps[set_num]): # Loop for each rep
            set_data["reps"][f"rep_{rep_num + 1}"] = { # For each rep set data
                "range_of_motion": f"{reps_rom[set_num][rep_num]}%", # Rep range of motion
                "time": str(reps_time[set_num][rep_num]), # Rep time
                "rep_heartrate": f"{reps_heartrate[set_num][rep_num]:.2f}", # Rep heartrate
                "rep_power": f"{reps_power[set_num][rep_num]:.2f}" # Rep power
            }
            
        # Set the sets data in workout data
        workout_data[exercise]["sets_data"][f"set_{set_num + 1}"] = set_data
        
    
    headers = {"Content-Type": "application/json"} # Set headers for JSON
    
    try: 
        response = urequests.patch(workout_url, data=ujson.dumps(workout_data), headers=headers)
        # Send PUT request for workout data
        print(f"Workout data sent: {ujson.dumps(workout_data, indent=2)}")
        print("Response:", response.text)
        
        lcd.lcd_clear()
        lcd.lcd_display_string("Data sent", 1)
        lcd.lcd_display_string("Well done", 2)
        time.sleep(3)
        lcd.lcd_clear()
        lcd.lcd_display_string("Check app for", 1)
        lcd.lcd_display_string("More data", 2)
        response.close() # Close Response
        
    except Exception as e: 
        print("Failed to send data:", str(e))
        lcd.lcd_clear()
        lcd.lcd_display_string("Failed to send", 1)
        lcd.lcd_display_string("Check Connection", 2)
        time.sleep(3)

                 
""" Functions that controls the motor """
def move_up():
    RPWM_Output.on() # Motor moving up
    LPWM_Output.off()

def move_down():
    RPWM_Output.off() # Motor moving down
    LPWM_Output.on()

def stop_motor():
    RPWM_Output.off() # Motor stops
    LPWM_Output.off()

""" Function to measure distance """
def measure_distance():
    # Ensure the trigger is low for clean signal
    trigger.value(0)
    time.sleep_us(2)

    # Send 10us pulse to trigger the measurement
    trigger.value(1)
    time.sleep_us(10)
    trigger.value(0)

    # Measure the duration of the echo pulse
    duration = time_pulse_us(echo, 1)  # 1 means wait for rising edge
    distance = (duration / 2) / 29.1  # Convert time to distance in cm
    time.sleep(0.05) # Sleep 50ms sec after measurement to avoid overload
    return distance - 4.3 # Remove start distance

""" Function to measure weight """
def measure_weight():
    
    lcd.lcd_clear()
    lcd.lcd_display_string("Reading weight", 1)
    print("reset the weight sensor") # Weight control
    move_down() 
    time.sleep(3) # Moving up the weights for 3 sec
    stop_motor()
    while not hx.is_ready():
        pass
    raw_value_zero = hx.read() # Raw zero weight
    time.sleep(3)
    
    weight_rounded = 0  # Reset weight
    
    move_up()
    time.sleep(2.5) # Move down weights for pressuring
    stop_motor()
    
    time.sleep(1)  # Allow time for weight sensor

    print("Raw zero weight", raw_value_zero)

    weight_rounded = 0 # Rounded weight
    
    while True:
        
        if hx.is_ready():
            raw_value = hx.read() #read weight
            weight_raw = raw_value - raw_value_zero # difference
            weight = (weight_raw * scale_factor) / 1000  # to kilograms
            weight_rounded = round(weight*2)/2  # round to 0.5 kilos
            
        else:
            print("Sensor cannot be read")

        time.sleep(2)
        
        if weight_rounded > 0: # Print weight
            print('Weight {}kg'.format(weight_rounded))
            return weight_rounded

""" Function for heart rate during a workout """
def get_heartrate(past_rate):
    # Algorithm for reading heart rate
    return past_rate * 1.05

""" Function to calculate the power during a rep """
def calc_power(weight, max_distance, time):
    max_distance += 4.3 #Add start distance
    return (weight * max_distance) / time

""" Function to calculate the set variability score """
# The variability score indicates how consistent the reps
# are throughout a set
def calculate_variability_score (set_power, avg_power):
    score = (sum(set_power) - (len(set_power) * avg_power))
    score*= score
    score /= len(set_power)
    return (1 - math.sqrt(score)) * 100

""" Function to calculate the set performance score """
def calculate_performance_score(max_power, avg_power):
    return (avg_power / max_power) * 100

""" Workout Function - Workout Algorithm"""
def workout(email, weight, heart_rate):
    
    print("Starting Workout")
    exercise = get_exercise()  # Returns the chosen exercise
    
    reps = [0, 0, 0] # List with the reps in each set
    
    reps_time = [[], [], []] # List of lists of the time in each rep by set
    reps_rom = [[], [], []] # List of lists of the range of motion in each rep by set
    
    reps_power = [[], [], []] # List of lists of the power in each rep by set
    
    set_power_avg = [0,0,0] # List of each set's average power
    set_times = [0, 0, 0] # List of set times
    set_tut = [0,0,0] # List of set time under tension
    set_rest = [0, 0, 0] # List of the rest period after a set
    set_rest_time = 0 # Variable to calculate set rest time
    sets_rom = [0,0,0] # List of set range of motion
    
    sets_performance_scores = [0,0,0] # List of set performance scores
    sets_variability_scores = [0,0,0] # List of set variability scores
    Rep_Avg_heartrate = [[], [], []] # List of rep heart rate by set
    Set_Avg_heartrate = [0, 0, 0] # List of set average heartrate
    
    power_max = 0 # Variable to keep track of max power
    set_1_reps =  random.randint(10, 16) # Randomly generate rep count for simulation
    rep_count = [set_1_reps, set_1_reps - 2, set_1_reps - 4] # Implement count
    
    for sets in range(3): # Loop for the 3 sets
        
        workout_rate = heart_rate # Start heartrate
        distance = 0 # Start distance variable
        
        while distance < 0: # Wait until set starts, when user starts lifting weight
            distance = measure_distance()
            move_down()
            
        move_down() 
        print(f"Starting Set {sets + 1}")
        start_set_time = time.ticks_ms() # When set starts start the set time
        last_rep_time = start_set_time # Update last rep time
        
        if sets > 0: # If it isn't the first set calculate rest period 
            set_rest[sets] = time.ticks_diff(start_set_time, set_rest_time) / 1000 # Calculate rest time
        
        count = 0
        
        while time.ticks_diff(time.ticks_ms(), last_rep_time) < 30000 and count < rep_count[sets]:
            # Set ends if 30 seconds pass after last rep
            
            while distance <= 0:  # Wait for a valid rep start (distance above )
                distance = measure_distance()
                move_down()

            # Rep starts
            start_rep_time = time.ticks_us() 
            max_distance = distance

            # While the movement is going up
            while distance <= 25:
                max_distance = max(max_distance, distance)
                distance = measure_distance()
                move_down()
                #Boochna goes up
                
            
            power = calc_power(weight, max_distance, (time.ticks_diff(time.ticks_us(), start_rep_time)) / 1000000)
            
            reps_power[sets].append(power)
            power_max = max(power_max, power)
                              
            # While the movement is going down
            while 0 <= distance:
                distance = measure_distance()
                #Boochna goes down
                move_up()
                
            stop_motor()
            
            # Rep ends
            end_rep_time = time.ticks_us()
            rep_time = (time.ticks_diff(end_rep_time, start_rep_time)) / 1000000
            # convert microseconds to seconds
            count += 1
            # Get heartrate
            workout_rate = get_heartrate(workout_rate)
            Rep_Avg_heartrate[sets].append((workout_rate))
            
            # Save rep data
            reps[sets] += 1 # Add a rep
            reps_time[sets].append(rep_time) # Append rep time
            range_of_motion = get_rom(max_distance) # Calculate range of motion
            reps_rom[sets].append(range_of_motion) # Append range of motion

            print(f"Rep {reps[sets]}:\nTime: {rep_time:.2f}s, Range of Motion: {range_of_motion}")
            last_rep_time = time.ticks_ms()  # Reset the last rep time
            set_rest_time = last_rep_time

            # Measure time user is resting to see if set ended
            distance = measure_distance()
            while distance < 0 and time.ticks_diff(time.ticks_ms(), last_rep_time) < 30000:
                move_down() #Implement start of next rep simulation
                distance = measure_distance()

        # Set ends
        set_duration = time.ticks_diff(time.ticks_ms(), start_set_time) / 1000  # Set duration in seconds
        
        set_tut[sets] = sum(reps_time[sets])
        
        length = len(reps_time[sets])
        sets_rom[sets] = sum(reps_rom[sets]) / length # Average ROM for each set
        set_power_avg[sets] = sum(reps_power[sets]) / length
        
        set_performance_score = calculate_performance_score(power_max,set_power_avg[sets])
        sets_performance_scores[sets] = set_performance_score
        set_variability_score = calculate_variability_score(reps_power[sets], set_power_avg[sets])
        sets_variability_scores[sets] = set_variability_score
        
        set_times[sets] = set_duration # Insert set duration to list
        
        Set_Avg_heartrate[sets] = sum(Rep_Avg_heartrate[sets]) / length
        
        print(f"Set {sets + 1} done in {set_duration:.2f}s")
        
        lcd.lcd_clear()
        lcd.lcd_display_string(f"Set {sets + 1} completed", 1) # show which set was just completed 
        lcd.lcd_display_string(f"in {set_duration:.2f}s", 2) # show how long the set took
        time.sleep(2) # wait for 5 seconds to let the trainer to see 
        lcd.lcd_clear() #clear LCD screen
        lcd.lcd_display_string(f"Set Score: {set_performance_score:.2f}", 1) #Display the performance score of the set
        
        # Set message based on performance score
        message = ""
        if set_performance_score < 50:
            message = "Lower Weight"
        elif set_performance_score < 70:
            message = "Take More Rest"
        elif set_performance_score < 90:
            message = "Solid performance"
        
        else:
            lcd.lcd_display_string("Excellent performance", 2)
            time.sleep(3)
            message = "Increase weight"
            
        lcd.lcd_display_string(message, 2) # Display message
        time.sleep(3)
        
        if set_variability_score < 80: # Display messages based on variability score
            lcd.lcd_display_string("Reps inconsistent", 2)
            time.sleep(2)
            lcd.lcd_display_string("Lower weight", 2)
            
        heart_rate += 7 # Average heart rate increase between sets
        random_sleep = random.randint(60,90)
        time.sleep(random_sleep)
        
    overall_variability_score = f"{(sum(sets_performance_scores) / 3):.2f}"
    overall_performance_score = f"{(sum(sets_performance_scores) / 3):.2f}"
    
    print("Workout completed")
    lcd.lcd_clear()
    lcd.lcd_display_string("Workout completed", 1)
    time.sleep(2)
    
    if overall_performance_score >= 90:
        lcd.lcd_clear()
        lcd.lcd_display_string("Consider Increasing", 1) 
        lcd.lcd_display_string("Weight next workout", 2)
        time.sleep(3)
        
    elif overall_performance_score <= 60:
        lcd.lcd_clear()
        lcd.lcd_display_string("Consider Lowering", 1) 
        lcd.lcd_display_string("Weight next workout", 2)
        time.sleep(3)
    
    if overall_variability_score >= 85:
        lcd.lcd_clear()
        lcd.lcd_display_string("Reps inconsistent", 1) 
        lcd.lcd_display_string("Try lowering weight", 2)
        time.sleep(2)
        lcd.lcd_display_string("Or more rest time", 2)
        time.sleep(2)
    
    lcd.lcd_clear()
    lcd.lcd_display_string("Workout Score:", 1)
    lcd.lcd_display_string(overall_performance_score, 2)
    time.sleep(5)
       
    # Send data to Firebase
    send_data_to_firebase(email, exercise, weight, overall_performance_score, overall_variability_score,
                          sets_performance_scores, sets_variability_scores, set_times, set_tut, set_rest,
                          sets_rom, set_power_avg, Set_Avg_heartrate, reps, reps_time, reps_rom,
                          reps_power, Rep_Avg_heartrate)


"""----------------------------------- START OF THE CODE -----------------------------------"""

connect_wifi()
print("waiting for the braclet...") 
lcd.lcd_display_string("waiting for", 1) # noify the trainer that the machine wait for the chip
lcd.lcd_display_string("the bracelet...", 2) 

sanitized_email = ""
resting_heart_rate = 0

#Prepare Machine (Sign Up / Sign In User)
while True :
    (status, tag_type) = mfrc522.request(mfrc522.REQIDL) #scans for nearby RFID tags
    
    if status == mfrc522.OK: #if card detected
        print("Card recognized") 
        
        (status, uid) = mfrc522.anticoll() #reads the uid of the card
        
        if status == mfrc522.OK: #if UID is successfully read
            print("ID is : ", end="") #print UID
            
            for i in uid:
                print(str(i), end=" ") #print each byte of the UID
        
            print() #print newline after it
            
            
            #build chip ID string and try to sign in the user
            chip_id = "".join(str(i) for i in uid) #combine into 1 string
            lcd.lcd_clear() #clar LCD screen
            lcd.lcd_display_string("Logging in", 1) # Display login message

            sign_in_data = sign_in_user(chip_id) #call a function to sign in and get user data
            
            sanitized_email = sign_in_data["email"] # user's mail
            workout_level = sign_in_data["level"] #user's workout level
            
            time.sleep(1)
            lcd.lcd_clear() #clear LCD screen
            lcd.lcd_display_string(f"Hi {Username}!", 1) # greet the user by name
            time.sleep(4) #hold the screen 
        
            resting_heart_rate = get_resting_rate(workout_level) # Get resting heart rate
            print(resting_heart_rate) 
            time.sleep(1)
            
            lcd.lcd_clear()
            lcd.lcd_display_string("Machine ready", 1) # notify user the system is ready
            break #exit loop after successful login
        
weight = measure_weight() # Weight sensor function

#Start The workout
workout(sanitized_email, weight, resting_heart_rate)



