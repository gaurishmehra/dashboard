import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, Pango
import requests
import json
import os
from datetime import datetime, timedelta
import warnings

warnings.filterwarnings("ignore")

# Defines the main Gtk.Box that holds and manages all weather-related UI and logic.
class WeatherWidget(Gtk.Box):
    # Initializes the weather widget, setting up its state and building the initial user interface.
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        
        self.weather_data = {}
        self.forecast_data = {}
        self.location_data = {}
        self.is_active = False
        self.update_timeout_id = None
        
        self.load_config()
        self.create_ui()
    
    # Reads latitude and longitude from a .env file located in the same directory as the script.
    def load_config(self):
        env_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), '.env')
        self.latitude = None
        self.longitude = None
        try:
            with open(env_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('LATITUDE='):
                        self.latitude = float(line.split('=', 1)[1])
                    elif line.startswith('LONGITUDE='):
                        self.longitude = float(line.split('=', 1)[1])
        except (FileNotFoundError, ValueError) as e:
            print(f"Error loading .env file: {e}")
            print("Please create a .env file with LATITUDE and LONGITUDE values")
    
    # Starts the widget's activity, triggering the first data fetch and scheduling periodic updates.
    def activate(self):
        if self.is_active: 
            return
        self.is_active = True
        print("WeatherWidget Activated")
        self.fetch_weather_data()
        self.update_timeout_id = GLib.timeout_add_seconds(600, self.fetch_weather_data)
    
    # Stops the widget's activity, cancelling any scheduled data updates to save resources.
    def deactivate(self):
        if not self.is_active:
            return
        self.is_active = False
        print("WeatherWidget Deactivated")
        if self.update_timeout_id:
            GLib.source_remove(self.update_timeout_id)
            self.update_timeout_id = None
    
    # Constructs the static skeleton of the widget, including the header, title, and a scrollable area for content.
    def create_ui(self):
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12,
                             margin_top=20, margin_bottom=16, margin_start=20, margin_end=20)
        
        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, hexpand=True)
        self.title_label = Gtk.Label(label="Weather", halign=Gtk.Align.START, css_classes=["title-large"])
        self.location_label = Gtk.Label(label="Loading location...", halign=Gtk.Align.START, css_classes=["location-label"])
        title_box.append(self.title_label)
        title_box.append(self.location_label)
        header_box.append(title_box)
        
        refresh_button = Gtk.Button(icon_name="view-refresh-symbolic", 
                                   tooltip_text="Refresh Weather", 
                                   css_classes=["circular"])
        refresh_button.connect("clicked", lambda b: self.fetch_weather_data())
        header_box.append(refresh_button)
        
        self.append(header_box)
        
        self.content_scrolled = Gtk.ScrolledWindow(vexpand=True, css_classes=["invisible-scroll"])
        self.content_scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        
        self.content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20,
                                   margin_start=20, margin_end=20, margin_bottom=20)
        
        self.content_scrolled.set_child(self.content_box)
        self.append(self.content_scrolled)
        
        self.show_loading()
    
    # Populates the content area with weather data. It clears any existing content and then builds the UI sections for current, hourly, and daily forecasts.
    def create_weather_ui(self):
        for child in list(self.content_box):
            self.content_box.remove(child)
        
        if not self.latitude or not self.longitude:
            self.show_error("Configuration Error", "Please set LATITUDE and LONGITUDE in .env file")
            return
        
        if not self.weather_data:
            self.show_loading()
            return
        
        try:
            self.create_current_weather()
            if self.forecast_data.get('hourly'):
                self.create_hourly_forecast()
            if self.forecast_data.get('daily'):
                self.create_daily_forecast()
        except Exception as e:
            print(f"FATAL: Error building weather UI from data: {e}")
            self.show_error("Data Error", "Could not parse weather data.")

    # Displays a loading spinner to indicate that data is being fetched in the background.
    def show_loading(self):
        for child in list(self.content_box):
            self.content_box.remove(child)
        loading_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                              halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER,
                              margin_top=50, margin_bottom=50)
        spinner = Gtk.Spinner(spinning=True, width_request=32, height_request=32)
        loading_label = Gtk.Label(label="Loading weather data...", css_classes=["dim-label"])
        loading_box.append(spinner)
        loading_box.append(loading_label)
        self.content_box.append(loading_box)
    
    # Displays a user-friendly error message if data fetching or processing fails.
    def show_error(self, title, message):
        for child in list(self.content_box):
            self.content_box.remove(child)
        error_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                            halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER,
                            margin_top=50, margin_bottom=50)
        error_icon = Gtk.Image(icon_name="dialog-error-symbolic")
        error_icon.set_pixel_size(48)
        error_title = Gtk.Label(label=title, css_classes=["title-label"])
        error_message = Gtk.Label(label=message, css_classes=["dim-label"])
        error_box.append(error_icon)
        error_box.append(error_title)
        error_box.append(error_message)
        self.content_box.append(error_box)
    
    # Builds the main card displaying the current weather conditions, such as temperature, icon, and other details.
    def create_current_weather(self):
        current_weather = self.weather_data.get('current', {})
        weather_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16, css_classes=["info-tile"])
        temp_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=20, halign=Gtk.Align.CENTER)
        
        weather_code = current_weather.get('weather_code', 0)
        icon_name = self.get_weather_icon(weather_code)
        weather_icon = Gtk.Image(icon_name=icon_name)
        weather_icon.set_pixel_size(64)
        
        temp = current_weather.get('temperature_2m', 0)
        temp_label = Gtk.Label(label=f"{temp:.1f}°C", css_classes=["temperature-label"])
        
        temp_box.append(weather_icon)
        temp_box.append(temp_label)
        
        weather_desc = self.get_weather_description(weather_code)
        desc_label = Gtk.Label(label=weather_desc, css_classes=["weather-desc"])
        
        weather_card.append(temp_box)
        weather_card.append(desc_label)
        
        details_grid = Gtk.Grid(row_spacing=8, column_spacing=20, halign=Gtk.Align.CENTER)
        details = [
            ("Feels like", f"{current_weather.get('apparent_temperature', 0):.1f}°C"),
            ("Humidity", f"{current_weather.get('relative_humidity_2m', 0)}%"),
            ("Wind Speed", f"{current_weather.get('wind_speed_10m', 0):.1f} km/h"),
            ("Pressure", f"{current_weather.get('surface_pressure', 0):.0f} hPa"),
        ]
        
        for i, (label, value) in enumerate(details):
            row, col = i // 2, (i % 2) * 2
            label_widget = Gtk.Label(label=label + ":", css_classes=["weather-detail-label"], halign=Gtk.Align.END)
            value_widget = Gtk.Label(label=value, css_classes=["weather-detail-value"], halign=Gtk.Align.START)
            details_grid.attach(label_widget, col, row, 1, 1)
            details_grid.attach(value_widget, col + 1, row, 1, 1)
        
        weather_card.append(details_grid)
        self.content_box.append(weather_card)
    
    # A helper to locate the array index for the current hour within the API's hourly forecast data.
    def find_current_hour_index(self, current_time_str, hourly_times):
        if not current_time_str or not hourly_times:
            return 0
        
        try:
            current_dt = datetime.fromisoformat(current_time_str.replace('Z', '+00:00'))
            current_hour = current_dt.replace(minute=0, second=0, microsecond=0)
            
            for i, time_str in enumerate(hourly_times):
                try:
                    hourly_dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                    hourly_hour = hourly_dt.replace(minute=0, second=0, microsecond=0)
                    
                    if current_hour == hourly_hour:
                        return i
                except (ValueError, TypeError):
                    continue
            
            closest_index = 0
            min_diff = float('inf')
            
            for i, time_str in enumerate(hourly_times):
                try:
                    hourly_dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                    diff = abs((current_dt - hourly_dt).total_seconds())
                    
                    if diff < min_diff:
                        min_diff = diff
                        closest_index = i
                except (ValueError, TypeError):
                    continue
            
            print(f"Using closest match at index {closest_index} for current time {current_time_str}")
            return closest_index
            
        except (ValueError, TypeError) as e:
            print(f"Error parsing current time '{current_time_str}': {e}")
            return 0
    
    # Creates the horizontally scrollable section for the 24-hour forecast, starting from the current hour.
    def create_hourly_forecast(self):
        hourly_label = Gtk.Label(label="24-Hour Forecast", css_classes=["section-title"], halign=Gtk.Align.START, margin_top=8)
        self.content_box.append(hourly_label)
        
        hourly_scrolled = Gtk.ScrolledWindow(css_classes=["hourly-scroll"])
        hourly_scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        hourly_scrolled.set_max_content_height(140)
        
        hourly_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        hourly_box.set_margin_start(12)
        hourly_box.set_margin_end(12)
        
        hourly_data = self.forecast_data.get('hourly', {})
        times = hourly_data.get('time', [])
        temps = hourly_data.get('temperature_2m', [])
        weather_codes = hourly_data.get('weather_code', [])
        precipitation = hourly_data.get('precipitation_probability', [])
        
        current_time_str = self.weather_data.get('current', {}).get('time')
        if not all([times, temps, weather_codes, precipitation]):
            print("Hourly forecast skipped: missing required data from API.")
            return

        current_index = self.find_current_hour_index(current_time_str, times)
        
        start_index = current_index
        end_index = min(len(times), current_index + 24)
        
        for i in range(start_index, end_index):
            is_current = (i == current_index)
            try:
                hour_card = self.create_hourly_card(
                    datetime.fromisoformat(times[i].replace('Z', '+00:00')), 
                    temps[i], weather_codes[i], 
                    precipitation[i] if i < len(precipitation) else 0,
                    is_current=is_current
                )
                hourly_box.append(hour_card)
            except (ValueError, TypeError) as e:
                print(f"Error creating hourly card for index {i}: {e}")
                continue
        
        hourly_scrolled.set_child(hourly_box)
        self.content_box.append(hourly_scrolled)

    # Creates a single, small vertical box representing one hour in the forecast.
    def create_hourly_card(self, time, temp, weather_code, precipitation, is_current=False):
        hour_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, css_classes=["hourly-card"], halign=Gtk.Align.CENTER)
        if is_current:
            hour_card.add_css_class("current-hour")
        hour_card.set_size_request(80, -1)
        
        if is_current:
            time_text = "Now"
        else:
            current_time_str = self.weather_data.get('current', {}).get('time', '')
            try:
                current_dt = datetime.fromisoformat(current_time_str.replace('Z', '+00:00'))
                current_date = current_dt.date()
                time_date = time.date()
                
                if time_date != current_date:
                    if time_date < current_date:
                        time_text = f"{time.strftime('%H:%M')}\n-1d"
                    else:
                        time_text = f"{time.strftime('%H:%M')}\n+1d"
                else:
                    time_text = time.strftime("%H:%M")
            except (ValueError, TypeError):
                time_text = time.strftime("%H:%M")
        
        time_label = Gtk.Label(label=time_text, css_classes=["hourly-time"])
        time_label.set_justify(Gtk.Justification.CENTER)
        
        icon_name = self.get_weather_icon(weather_code, is_hourly=True)
        weather_icon = Gtk.Image(icon_name=icon_name)
        weather_icon.set_pixel_size(24)
        
        temp_label = Gtk.Label(label=f"{temp:.0f}°", css_classes=["hourly-temp"])
        precip_label = Gtk.Label(label=f"{precipitation:.0f}%" if precipitation > 0 else "", css_classes=["hourly-precip"])
        
        hour_card.append(time_label)
        hour_card.append(weather_icon)
        hour_card.append(temp_label)
        hour_card.append(precip_label)
        return hour_card

    # Builds the list view for the 7-day weather forecast.
    def create_daily_forecast(self):
        forecast_label = Gtk.Label(label="7-Day Forecast", css_classes=["section-title"], halign=Gtk.Align.START, margin_top=8)
        self.content_box.append(forecast_label)
        
        daily_data = self.forecast_data.get('daily', {})
        dates = daily_data.get('time', [])
        max_temps = daily_data.get('temperature_2m_max', [])
        min_temps = daily_data.get('temperature_2m_min', [])
        weather_codes = daily_data.get('weather_code', [])
        precipitation = daily_data.get('precipitation_probability_max', [])
        
        daily_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, css_classes=["daily-forecast-container"])
        
        for i in range(min(7, len(dates))):
            day_row = self.create_daily_row(
                dates[i], max_temps[i], min_temps[i], weather_codes[i],
                precipitation[i] if i < len(precipitation) else 0
            )
            daily_container.append(day_row)
        
        self.content_box.append(daily_container)
    
    # Creates a single row widget for one day in the 7-day forecast list.
    def create_daily_row(self, date_str, max_temp, min_temp, weather_code, precipitation):
        day_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12, css_classes=["daily-row"])
        day_row.set_margin_start(8)
        day_row.set_margin_end(8)
        
        try:
            date_obj = datetime.fromisoformat(date_str)
            if date_obj.date() == datetime.now().date():
                day_name = "Today"
            elif date_obj.date() == (datetime.now() + timedelta(days=1)).date():
                day_name = "Tomorrow"
            else:
                day_name = date_obj.strftime("%A")
        except:
            day_name = "Unknown"
        
        day_label = Gtk.Label(label=day_name, css_classes=["daily-day"], halign=Gtk.Align.START, hexpand=True)
        day_label.set_size_request(100, -1)
        
        icon_name = self.get_weather_icon(weather_code)
        weather_icon = Gtk.Image(icon_name=icon_name)
        weather_icon.set_pixel_size(20)
        
        if precipitation > 0:
            precip_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
            precip_icon = Gtk.Image(icon_name="weather-showers-symbolic")
            precip_icon.set_pixel_size(12)
            precip_label = Gtk.Label(label=f"{precipitation:.0f}%", css_classes=["daily-precip"])
            precip_box.append(precip_icon)
            precip_box.append(precip_label)
        else:
            precip_box = Gtk.Box()
            precip_box.set_size_request(40, -1)
        
        temp_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        temp_max_label = Gtk.Label(label=f"{max_temp:.0f}°", css_classes=["daily-temp-max"])
        temp_min_label = Gtk.Label(label=f"{min_temp:.0f}°", css_classes=["daily-temp-min"])
        temp_box.append(temp_max_label)
        temp_box.append(temp_min_label)
        
        day_row.append(day_label)
        day_row.append(weather_icon)
        day_row.append(precip_box)
        day_row.append(temp_box)
        return day_row
    
    # Fetches weather and location data from web APIs in a background thread to prevent freezing the UI.
    def fetch_weather_data(self):
        if not self.latitude or not self.longitude:
            GLib.idle_add(self.create_weather_ui)
            return GLib.SOURCE_REMOVE
        
        GLib.idle_add(self.show_loading)

        def fetch_in_thread():
            try:
                current_params = [
                    "temperature_2m", "relative_humidity_2m", "apparent_temperature",
                    "surface_pressure", "wind_speed_10m", "weather_code", "is_day"
                ]
                hourly_params = ["temperature_2m", "weather_code", "precipitation_probability"]
                daily_params = ["weather_code", "temperature_2m_max", "temperature_2m_min", "precipitation_probability_max"]

                weather_url = (
                    f"https://api.open-meteo.com/v1/forecast?"
                    f"latitude={self.latitude}&longitude={self.longitude}"
                    f"¤t={','.join(current_params)}"
                    f"&hourly={','.join(hourly_params)}"
                    f"&daily={','.join(daily_params)}"
                    f"&timezone=auto&forecast_days=7"
                )

                weather_response = requests.get(weather_url, timeout=10)
                weather_response.raise_for_status()
                
                data = weather_response.json()
                self.weather_data = data
                self.forecast_data = data
                
                try:
                    reverse_geo_url = f"https://api.bigdatacloud.net/data/reverse-geocode-client?latitude={self.latitude}&longitude={self.longitude}&localityLanguage=en"
                    geo_response = requests.get(reverse_geo_url, timeout=5)
                    if geo_response.status_code == 200:
                        geo_data = geo_response.json()
                        city = geo_data.get('city') or geo_data.get('locality') or geo_data.get('principalSubdivision')
                        country = geo_data.get('countryName', '')
                        if city: 
                            self.location_data = {'city': f"{city}, {country}" if country else city}
                except requests.RequestException:
                    timezone = data.get('timezone', '')
                    city_name = timezone.split('/')[-1].replace('_', ' ') if '/' in timezone else 'Unknown Location'
                    self.location_data = {'city': city_name}
                
                GLib.idle_add(self.update_location_and_weather)
            
            except requests.exceptions.HTTPError as e:
                print(f"API Error fetching weather data: {e}")
                GLib.idle_add(self.show_error, "API Error", "The weather service returned an error.")
            except requests.exceptions.RequestException as e:
                print(f"Network Error fetching weather data: {e}")
                GLib.idle_add(self.show_error, "Network Error", "Failed to connect to weather service.")
            except Exception as e:
                print(f"An unexpected error occurred: {e}")
                GLib.idle_add(self.show_error, "Application Error", "An unexpected error occurred.")

        import threading
        thread = threading.Thread(target=fetch_in_thread, daemon=True)
        thread.start()
        return GLib.SOURCE_CONTINUE
    
    # Updates the UI on the main thread after the background data fetch is complete.
    def update_location_and_weather(self):
        city_name = self.location_data.get('city', 'Unknown Location')
        self.location_label.set_text(city_name)
        self.create_weather_ui()
    
    # Translates a weather code from the API into a corresponding symbolic icon name for GTK.
    def get_weather_icon(self, weather_code, is_hourly=False):
        is_day = self.weather_data.get('current', {}).get('is_day', 1) == 1 if not is_hourly else True
        
        icon_map = {
            0: "weather-clear-night-symbolic" if not is_day else "weather-clear-symbolic",
            1: "weather-few-clouds-night-symbolic" if not is_day else "weather-few-clouds-symbolic",
            2: "weather-few-clouds-night-symbolic" if not is_day else "weather-few-clouds-symbolic",
            3: "weather-overcast-symbolic", 
            45: "weather-fog-symbolic", 
            48: "weather-fog-symbolic",
            51: "weather-showers-scattered-symbolic", 
            53: "weather-showers-scattered-symbolic", 
            55: "weather-showers-symbolic",
            61: "weather-showers-scattered-symbolic", 
            63: "weather-showers-symbolic", 
            65: "weather-showers-symbolic",
            71: "weather-snow-symbolic", 
            73: "weather-snow-symbolic", 
            75: "weather-snow-symbolic",
            95: "weather-storm-symbolic", 
            96: "weather-storm-symbolic", 
            99: "weather-storm-symbolic",
        }
        return icon_map.get(weather_code, "weather-clear-symbolic")
    
    # Translates a weather code from the API into a human-readable description.
    def get_weather_description(self, weather_code):
        descriptions = {
            0: "Clear", 1: "Mainly Clear", 2: "Partly Cloudy", 3: "Overcast",
            45: "Fog", 48: "Rime Fog", 51: "Light Drizzle", 53: "Drizzle", 55: "Dense Drizzle",
            61: "Slight Rain", 63: "Rain", 65: "Heavy Rain", 71: "Slight Snow", 73: "Snow",
            75: "Heavy Snow", 95: "Thunderstorm", 96: "Thunderstorm + Hail", 99: "Thunderstorm + Heavy Hail",
        }
        return descriptions.get(weather_code, "Unknown")