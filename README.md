How to use
===========
1. Clone the repository:
   ```bash
   git clone https://github.com/gaurishmehra/dashboard.git
   cd dashboard
    ```
    Install dunst and run it (Make sure no other notification daemon is running):
    ```bash
    sudo pacman -S dunst
    dunst &
    ```
2. Make the script executable:
   ```bash
   chmod +x dunst_log.py
   ```
3. Run the script:
   ```bash
    ./dunst_log.py &
   ```
   You should ideally put the script in the hyprland config or make a systemd service for it.
   ```bash
   exec-once = /path/to/dunst_log.py
   ```
4. Run the dashboard:
   ```bash
   python dashboard.py
   ```
5. (Optional) add the following lines to your hyprland config file:
   ```bash
    windowrulev2 = float, class:^(com.gaurish.Dashboard)$
    windowrulev2 = size 300 450, class:^(com.gaurish.Dashboard)$
    windowrulev2 = center, class:^(com.gaurish.Dashboard)$
    windowrulev2 = pin, class:^(com.gaurish.Dashboard)$
    windowrulev2 = noborder, class:^(com.gaurish.Dashboard)$
   ```
    I recommed making it a keybind to toggle the dashboard:
    ```bash
    #!/bin/bash

    # The full path to your media controller python script
    APP_SCRIPT="path/to/dashboard.py"

    # Check if the Media Controller window is open
    if hyprctl clients -j | jq -e '.[] | select(.title=="Media Controller")' > /dev/null 2>&1; then
        # If the window exists, close it by title
        hyprctl dispatch closewindow "title:^Media Controller$"
    else
        # If not running, launch it
        cd "path/to/dashboard" && python3 "$APP_SCRIPT" &
    fi
    ```
    Make it executable:
    ```bash
    chmod +x /path/to/your/script.sh
    ```
    Then link it to a keybind in your hyprland config (Ex - super + slash):
    ```bash
    bind = super, slash, exec, /path/to/your/script.sh
    ```

_If you want to recommend any changes or improvements, feel free to open an issue, but keep in mind this is meant to be a basic/simple/minimal dashboard for Linux systems (Made by me for myself and some friends), so don't recommend shit like "add a screen mirror to the adb section" or "add an app launcher"._

See video.mkv in the files for a demo