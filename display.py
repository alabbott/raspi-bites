from displaymanager import DisplayManager, BusTracker, WeatherTracker, Screen
import time
import datetime
from dotenv import load_dotenv
import os

# Load .env file
load_dotenv()

# Now you can access the variables using os.getenv()
weather_api_key = os.getenv('OPEN_WEATHER_MAP_API_KEY')
news_api_key = os.getenv('NEWS_API_KEY')
bus_api_key = os.getenv('CTA_BUS_API_KEY')
lat = os.getenv('LAT')
lon = os.getenv('LON')

displayManager = DisplayManager()

weatherTracker = WeatherTracker(displayManager, weather_api_key, lat, lon)

tracked_buses = [{"route": "X9",
                  "stop_id": "6024",
                  "stop_number": "X9",
                  "stop_name": "Ashland & Division",
                  "direction": "Southbound"},

                 {"route": "9",
                  "stop_id": "14619",
                  "stop_number": "9",
                  "stop_name": "Ashland & Blackhawk",
                  "direction": "Southbound"},

                  {"route": "72",
                  "stop_id": "903",
                  "stop_number": "72",
                  "stop_name": "North & Bosworth",
                  "direction": "Eastbound"}]

busTracker = BusTracker(displayManager, bus_api_key, tracked_buses=tracked_buses)

def queueScreensMorning():
    message = 'I love you\n        - Alan'
    displayManager.addScreenToQueue(Screen(displayManager.textScreen, message, partial=False, display_time=5))
    busTracker.queueTrackedBusScreens(5)
    weatherTracker.queueWeatherScreens(5)

def queueScreensAfternoon():
    busTracker.queueTrackedBusScreens(10)
    weatherTracker.queueWeatherScreens(10)
    
def queueScreensEvening():
    busTracker.queueTrackedBusScreens(10)
    weatherTracker.queueWeatherScreens(10)

def queueScreensNight():
    message = 'Get some sleep,\n    good night! Zzz'
    displayManager.addScreenToQueue(Screen(displayManager.textScreen, message, partial=False, display_time=10))
    weatherTracker.queueWeatherScreens(10)

last_weather_execution_time = time.time()  # Set initial value to trigger first execution
last_queue_execution_time = time.time() - 3600  # Set initial value to trigger first execution

while True:
    current_time = time.time()
    if current_time - last_weather_execution_time >= 180:
        weatherTracker.update()
        last_weather_execution_time = current_time

    now = datetime.datetime.now().time()

    # Define the time ranges for each block
    morning_start = datetime.time(6, 30)
    afternoon_start = datetime.time(12, 0)
    evening_start = datetime.time(18, 0)
    night_end = datetime.time(22, 0)

    if morning_start <= now < afternoon_start:
        if current_time - last_queue_execution_time >= 300:
            print('Refreshing queue, checking for bus alerts')
            displayManager.clearQueue()
            queueScreensMorning()
            last_queue_execution_time = current_time
    elif afternoon_start <= now < evening_start:
        if current_time - last_queue_execution_time >= 300:
            print('Refreshing queue, checking for bus alerts')
            displayManager.clearQueue()
            queueScreensAfternoon()
            last_queue_execution_time = current_time
    elif evening_start <= now < night_end:
        if current_time - last_queue_execution_time >= 300:
            print('Refreshing queue, checking for bus alerts')
            displayManager.clearQueue()
            queueScreensEvening()
            last_queue_execution_time = current_time
    else:
        if current_time - last_queue_execution_time >= 300:
            print('Refreshing queue, checking for bus alerts')
            displayManager.clearQueue()
            queueScreensNight()
            last_queue_execution_time = current_time

    displayManager.displayQueue()