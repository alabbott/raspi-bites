import time
from lib.waveshare_epd import epd2in13_V3
from PIL import Image, ImageDraw, ImageFont, ImageOps
from datetime import datetime
import requests
from io import BytesIO
import json
import threading
import signal
import sys
import xml.etree.ElementTree as ET


class DisplayManager:
    def __init__(self) -> None:
        # queue to hold screens
        self.queue = []

        # set up a font for general use
        self.body = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 24)

        # initialize and clear the display, store the display object
        try:
            # Display init, clear
            print('Initializing display')
            self.eink = epd2in13_V3.EPD()
            self.eink.init()
            self.eink.Clear()
            self.w = self.eink.height
            self.h = self.eink.width
            print('width:', self.w)
            print('height:', self.h)
        except IOError as e:
            print(e)

        # make sure we close gracefully
        signal.signal(signal.SIGINT, self._graceful_exit)
        signal.signal(signal.SIGTERM, self._graceful_exit)

    def _graceful_exit(self, signal, frame):
        print("\nQuitting")
        time.sleep(3)
        self.clear()
        self.sleep()
        print("Program exited")
        sys.exit(0)  # Exit the program

    # function to clear the display
    def clear(self, color = "white"):
        try:
            if color == "white":
                self.eink.Clear(0xFF)
                print('Display cleared')
            else:
                self.eink.Clear(0)
                print('Display cleared')
        except IOError as e:
            print(e)

    # function to put the display to sleep
    def sleep(self):
        try:
            self.eink.sleep()
            print('Display sleeping')
        except IOError as e:
            print(e)

    def showScreen(self, screen):
        try:
            if screen.partial == True:
                self.eink.displayPartial(self.eink.getbuffer(screen.image))
            else:
                self.eink.display(self.eink.getbuffer(screen.image))
        except IOError as e:
            print(e)

    def addScreenToQueue(self, screen):
        self.queue.append(screen)

    def clearQueue(self):
        self.queue = []

    def displayQueue(self):
        if not self.queue:
            print('No screens in queue')
            return
        
        for screen in self.queue:
            try:
                screen.update()
            except Exception as e:
                print(e)
            else:
                self.showScreen(screen)
                time.sleep(screen.display_time)
            
    def helloWorld(self):
        image = Image.new(mode='1', size=(self.w, self.h), color=255)
        draw = ImageDraw.Draw(image)
        draw.text((0, 0), 'Hello world!', font=self.body, fill=0, align='left')
        self.showScreen(image)

    def textScreen(self, message):
        # Create a header
        image = self._screenHeader()
        draw = ImageDraw.Draw(image)
        draw.text((5, (self.h /3 + 5)), message, font=self.body, fill=0, align='left')
        return image
    
    def _screenHeader(self):
        # Create the image and set the draw object
        image = Image.new(mode='1', size=(self.w, self.h), color=255)
        draw = ImageDraw.Draw(image)

        # Prepare the weather information
        current_temp = round(self.weather_data['current']['temp'])  # Rounded temperature from the API response
        current_temp = f"{current_temp}°"
        conditions = self.weather_data['current']['weather'][0]['main']  # Get the main weather condition from the API response

        # Increase the size of the icon and reposition it
        icon_size = int(self.h / 3 / 2)  # Icon now takes up half the height of the header
        icon_x = 5  # Buffer from the left
        icon_y = int((self.h / 3 - icon_size) / 2)  # Centered vertically within the header

        # Download and display the weather icon
        icon_code = self.weather_data['current']['weather'][0]['icon']  # Get the icon code from the API response
        response = requests.get(f"https://openweathermap.org/img/wn/{icon_code}.png")
        icon_img = Image.open(BytesIO(response.content)).convert("L")  # Convert image to 8 bit black and white
        # icon_img = ImageOps.invert(icon_img)  # Invert black and white
        icon_img = icon_img.convert("1")  # Convert image back to 1 bit black and white
        icon_img = icon_img.resize((icon_size, icon_size), Image.ANTIALIAS)  # Resize the image
        image.paste(icon_img, (icon_x, icon_y))  # Paste the image onto the display image

        # Increase the font size to match the new icon size and reposition the weather information
        font_size = int(icon_size / 2)
        font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', font_size)
        weather_x = icon_x + icon_size + 5  # Buffer from the icon
        weather_y = icon_y
        draw.text((weather_x, weather_y), current_temp, font=font, fill=0)
        weather_y += font.getsize(current_temp)[1]  # Move y down for the next line of text
        draw.text((weather_x, weather_y), conditions, font=font, fill=0)

        # Double the font size for the time and reposition it
        time_font_size = int(font_size * 2)  # Double the previous font size
        time_font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', time_font_size)
        current_time = time.strftime("%H:%M")
        text_width, text_height = draw.textsize(current_time, font=time_font)
        text_x = (self.w - text_width) / 2  # Recentered horizontally
        text_y = (self.h / 3 - text_height) / 2  # Vertically centered in the top third of the screen
        draw.text((text_x, text_y), current_time, font=time_font, fill=0)

        # Draw a line under the header
        line_y = self.h / 3  # One third down the height
        draw.line([(0, line_y), (self.w, line_y)], fill=0)

        return image

class Screen:
    def __init__(self, content_func, *content_args, partial=False, display_time=3) -> None:
        self.partial = partial
        self.content_func = content_func
        self.content_args = content_args
        self.display_time = display_time
        self.update()

    def update(self):
        self.image = self.content_func(*self.content_args)
        self.last_updated = datetime.now()

class BusTracker:
    def __init__(self, DisplayManager, api_key, tracked_buses=[]) -> None:
        self.DisplayManager = DisplayManager
        self.tracked_buses = tracked_buses
        self.api_key = api_key

    def addTrackedBus(self, route, stop_id, stop_number, stop_name, direction):
        bus = {"route": route,
               "stop_id": stop_id,
               "stop_number": stop_number,
               "stop_name": stop_name,
               "direction": direction}
        
        self.tracked_buses.append(bus)

    def busScheduleScreen(self, bus):
         # Define the endpoint
        url = f"http://www.ctabustracker.com/bustime/api/v3/getpredictions?key={self.api_key}&rt={bus['route']}&stpid={bus['stop_id']}&format=json"

        # Send the GET request
        response = requests.get(url)

        bus_error = False

        # Check if the request was successful
        if response.status_code == 200:
            # Parse the JSON response
            data = json.loads(response.text)

            try:
                bus_predictions = data['bustime-response']['prd']
            except KeyError:
                bus_error = True
                error_data = data['bustime-response']['error']
                
        else:
            # The request failed
            print(f"Failed to retrieve bus predictions. Status code: {response.status_code}")
            return self.DisplayManager.textScreen("Error retrieving bus times")
        
        # Fonts
        stop_font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 18)  # size is now 18
        bus_font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 24)
        min_font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 12)
        direction_font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 14)

        if bus_error:
            # Create a header
            image = self.DisplayManager._screenHeader()
            draw = ImageDraw.Draw(image)

            # Combined stop number and stop name
            stop_text = f"{bus['stop_number']} - {bus['stop_name']}"

            # Draw the stop text centered right below the header
            stop_text_width, stop_text_height = draw.textsize(stop_text, font=stop_font)
            stop_text_x = (self.DisplayManager.w - stop_text_width) / 2
            stop_text_y = self.DisplayManager.h / 3
            draw.text((stop_text_x, stop_text_y), stop_text, font=stop_font, fill=0)

            # draw the error text
            error_text = error_data[0]['msg']
            error_text_width, errpr_text_height = draw.textsize(error_text, font=stop_font)
            error_text_x = (self.DisplayManager.w - error_text_width) / 2
            error_text_y = stop_text_y + stop_text_height + 15
            draw.text((error_text_x, error_text_y), error_text, font=stop_font, fill=0)

            # Draw the direction centered along the bottom of the screen
            direction_width, direction_height = draw.textsize(bus['direction'], font=direction_font)
            direction_x = (self.DisplayManager.w - direction_width) / 2
            direction_y = self.DisplayManager.h - direction_height - 5  # 5 is a buffer space from the bottom
            draw.text((direction_x, direction_y), bus['direction'], font=direction_font, fill=0)

            return image

        next_buses = []
        now = datetime.now()

        for prediction in bus_predictions:
            if prediction['dly'] == False:
                bus_time_str = prediction['prdtm']
                bus_time = datetime.strptime(bus_time_str, "%Y%m%d %H:%M")

                # Calculate the difference in time and convert it to minutes
                time_diff = bus_time - now
                time_diff_minutes = int(time_diff.total_seconds() // 60)  # Using '//' to round down
                
                if time_diff_minutes < 1:
                    time_diff_minutes = "Due"

                next_buses.append(time_diff_minutes)

        # Limit the number of buses to maximum 3
        next_buses = next_buses[:3]

        # Create a header
        image = self.DisplayManager._screenHeader()
        draw = ImageDraw.Draw(image)

        # Combined stop number and stop name
        stop_text = f"{bus['stop_number']} - {bus['stop_name']}"

        # Draw the stop text centered right below the header
        stop_text_width, stop_text_height = draw.textsize(stop_text, font=stop_font)
        stop_text_x = (self.DisplayManager.w - stop_text_width) / 2
        stop_text_y = self.DisplayManager.h / 3
        draw.text((stop_text_x, stop_text_y), stop_text, font=stop_font, fill=0)

        # Determine the number of segments based on the number of buses
        if len(next_buses) != 0:
            num_segments = len(next_buses)
        else:
            num_segments = 1
        segment_width = self.DisplayManager.w / num_segments

        # Draw the number of minutes for the next buses
        for i, bus_time in enumerate(next_buses):
            bus_time_text = str(bus_time)
            bus_time_width, bus_time_height = draw.textsize(bus_time_text, font=bus_font)
            bus_time_x = i * segment_width + (segment_width - bus_time_width) / 2
            bus_time_y = stop_text_y + stop_text_height + 10  # 10 is a buffer space
            draw.text((bus_time_x, bus_time_y), bus_time_text, font=bus_font, fill=0)

            # Draw "min" below each number if the bus isn't "due"
            if not bus_time_text == "Due":
                min_text = "min"
                min_width, min_height = draw.textsize(min_text, font=min_font)
                min_x = bus_time_x + (bus_time_width - min_width) / 2
                min_y = bus_time_y + bus_time_height
                draw.text((min_x, min_y), min_text, font=min_font, fill=0)

        # Draw the direction centered along the bottom of the screen
        direction_width, direction_height = draw.textsize(bus['direction'], font=direction_font)
        direction_x = (self.DisplayManager.w - direction_width) / 2
        direction_y = self.DisplayManager.h - direction_height - 5  # 5 is a buffer space from the bottom
        draw.text((direction_x, direction_y), bus['direction'], font=direction_font, fill=0)

        return image
    
    def queueScreensForBusAlert(self, bus, display_time):
        base_url = "http://www.transitchicago.com/api/1.0/routes.aspx"
        response = requests.get(base_url, params={"routeid": bus['route']})

        if response.status_code != 200:
            print("Error checking for bus alerts")
            return
        
        root = ET.fromstring(response.content)
        route_info = root.find('RouteInfo')

        if route_info is None:
            print("Error checking for bus alerts")
            return
        
        route_status = route_info.find('RouteStatus')
        if route_status is None:
            print("Error checking for bus alerts")
            return
        
        alert_message = route_status.text

        if alert_message == "Normal Service":
            print(f"No bus alerts for {bus['route']} - {bus['stop_name']}")
            return
        
        busAlertScreen = Screen(self.busAlertScreen, bus, alert_message, partial=False, display_time=int(display_time))
        self.DisplayManager.addScreenToQueue(busAlertScreen)
        print(f"Queued bus alert screen for {bus['route']} - {bus['stop_name']}: {alert_message}")
        return
        
    def busAlertScreen(self, bus, alert_message):
        # Fonts
        stop_font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 18)  # size is now 18
        bus_font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 24)
        min_font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 12)
        direction_font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 14)

        # Create a header
        image = self.DisplayManager._screenHeader()
        draw = ImageDraw.Draw(image)

        # Combined stop number and stop name
        stop_text = f"{bus['stop_number']} - {bus['stop_name']}"

        # Draw the stop text centered right below the header
        stop_text_width, stop_text_height = draw.textsize(stop_text, font=stop_font)
        stop_text_x = (self.DisplayManager.w - stop_text_width) / 2
        stop_text_y = self.DisplayManager.h / 3
        draw.text((stop_text_x, stop_text_y), stop_text, font=stop_font, fill=0)

        # draw the error text
        error_text = "Alert: " + alert_message
        error_text_width, errpr_text_height = draw.textsize(error_text, font=stop_font)
        error_text_x = (self.DisplayManager.w - error_text_width) / 2
        error_text_y = stop_text_y + stop_text_height + 15
        draw.text((error_text_x, error_text_y), error_text, font=stop_font, fill=0)

        # Draw the direction centered along the bottom of the screen
        direction_width, direction_height = draw.textsize(bus['direction'], font=direction_font)
        direction_x = (self.DisplayManager.w - direction_width) / 2
        direction_y = self.DisplayManager.h - direction_height - 5  # 5 is a buffer space from the bottom
        draw.text((direction_x, direction_y), bus['direction'], font=direction_font, fill=0)

        return image
    
    def queueTrackedBusScreens(self, display_time):        
        for bus in self.tracked_buses:
            busScreen = Screen(self.busScheduleScreen, bus, partial=False, display_time=int(display_time))
            self.DisplayManager.addScreenToQueue(busScreen)
            print(f"Queued bus screen for {bus['route']} - {bus['stop_name']}")

            self.queueScreensForBusAlert(bus, display_time)
    
class WeatherTracker:
    def __init__(self, DisplayManager, api_key, lat, lon) -> None:
        self.DisplayManager = DisplayManager
        self.api_key = api_key
        self.lat = lat
        self.lon = lon

        self.update()

    def update(self):
        # Update weather here
        base_url = "https://api.openweathermap.org/data/3.0/onecall"
        params = {
            "lat": self.lat,
            "lon": self.lon,
            "units": "imperial",
            "exclude": "minutely",  # We exclude minutely data as we don't need it for this implementation
            "appid": self.api_key
        }
        response = requests.get(base_url, params=params)
        self.weather_data = response.json()
        self.DisplayManager.weather_data = self.weather_data
        print('Weather data updated')
        return response.json()
    
    def weatherScreen(self):
        # Create a header
        image = self.DisplayManager._screenHeader()
        draw = ImageDraw.Draw(image)

        # Fonts
        location_font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 22)
        temperature_font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 34)
        description_font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 16)
        high_low_font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 14)

        # The API now returns temperature in Fahrenheit, no need to convert from Kelvin
        current_temp_f = round(self.weather_data['current']['temp'])

        # Texts
        location = "Chicago"
        temperature = f"{current_temp_f}°F"
        description = self.weather_data['current']['weather'][0]['description'].capitalize()

        # Position
        location_x = 5
        location_y = int(self.DisplayManager.h / 3) + 5  # 5px under the header
        temperature_x = location_x
        temperature_y = location_y + location_font.getsize(location)[1]  # No padding between location and temperature

        # Download and display the weather icon
        icon_height = int(((self.DisplayManager.h/3)*2 - description_font.getsize(description)[1] - high_low_font.getsize('H: 88°F L: 88°F')[1] - 5))
        icon_code = self.weather_data['current']['weather'][0]['icon']  # Get the icon code from the API response
        response = requests.get(f"https://openweathermap.org/img/wn/{icon_code}.png")
        icon_img = Image.open(BytesIO(response.content)).convert("L")  # Convert image to 8 bit black and white
        # icon_img = ImageOps.invert(icon_img)  # Invert black and white
        icon_img = icon_img.convert("1")  # Convert image back to 1 bit black and white
        icon_img = icon_img.resize((icon_height, icon_height), Image.ANTIALIAS)  # Resize the image
        icon_x = self.DisplayManager.w - icon_img.width - 5  # 5px from the right edge
        icon_y = location_y

        # Description
        description_x = self.DisplayManager.w - description_font.getsize(description)[0] - 5  # 5px from the right edge
        description_y = icon_y + icon_img.height  # below the icon

        # High and low temperatures
        high_temp = round(self.weather_data['daily'][0]['temp']['max'])  # For today
        low_temp = round(self.weather_data['daily'][0]['temp']['min'])  # For today
        high_low_text = f"H: {high_temp}°F L: {low_temp}°F"
        high_low_x = self.DisplayManager.w - high_low_font.getsize(high_low_text)[0] - 5  # 5px from the right edge
        high_low_y = description_y + description_font.getsize(description)[1]  # below the description

        # Draw the texts
        draw.text((location_x, location_y), location, font=location_font, fill=0)
        draw.text((temperature_x, temperature_y), temperature, font=temperature_font, fill=0)
        draw.text((description_x, description_y), description, font=description_font, fill=0)
        draw.text((high_low_x, high_low_y), high_low_text, font=high_low_font, fill=0)

        # Paste the icon
        image.paste(icon_img, (icon_x, icon_y))

        return image

    def tempChartScreen(self):
        # Create a header
        image = self.DisplayManager._screenHeader()
        draw = ImageDraw.Draw(image)

        # Fonts
        temp_font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 16)
        hour_font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 12)

        # Retrieve next 6 hours of data
        next_6_hours = self.weather_data['hourly'][:6]

        # Icon size and start position
        icon_size = int(self.DisplayManager.h / 5)

        # Temp and hour start positions
        hour_y = ((self.DisplayManager.h // 3) + 10)
        icon_y = hour_y + hour_font.getsize('88')[1] + 5
        temp_y = icon_y + icon_size + 5

        # Column width
        column_width = self.DisplayManager.w // 6

        # Draw hourly data
        for i, hour in enumerate(next_6_hours):
            temp = round(hour['temp'])  # Ensure 'temp' is the correct field in your data
            hour_number = datetime.fromtimestamp(hour['dt']).hour  # Adjust if needed

            # Icon, temp and hour positions (centered within the column)
            icon_x = i * column_width + (column_width - icon_size) // 2
            temp_x = i * column_width + (column_width - temp_font.getsize(str(temp))[0]) // 2
            hour_x = i * column_width + (column_width - hour_font.getsize(str(hour_number))[0]) // 2

            # Download and display the weather icon
            icon_code = hour['weather'][0]['icon']  # Get the icon code from the API response
            response = requests.get(f"https://openweathermap.org/img/wn/{icon_code}.png")
            icon_img = Image.open(BytesIO(response.content)).convert("L")  # Convert image to 8 bit black and white
            # icon_img = ImageOps.invert(icon_img)  # Invert black and white
            icon_img = icon_img.convert("1")  # Convert image back to 1 bit black and white
            icon_img = icon_img.resize((icon_size, icon_size), Image.ANTIALIAS)  # Resize the image
            image.paste(icon_img, (icon_x, icon_y))  # Paste the image onto the display image

            # Draw the temperature
            draw.text((temp_x, temp_y), f"{temp}°", font=temp_font, fill=0)

            # Draw the hour number
            draw.text((hour_x, hour_y), str(hour_number), font=hour_font, fill=0)

        return image
    
    def queueWeatherScreens(self, display_time):
        summaryScreen = Screen(self.weatherScreen, partial=False, display_time=int(display_time))
        self.DisplayManager.addScreenToQueue(summaryScreen)
        print('Queued weather summary screen')
        chartScreen = Screen(self.tempChartScreen, partial=False, display_time=int(display_time))
        self.DisplayManager.addScreenToQueue(chartScreen)
        print('Queued temperature chart screen')