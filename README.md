# OculusViewer

 This is a shitty python script to display the screen of multiple Quest 2's at once on a single screen.

![8 Quest 2's casting to a single screen](https://raw.githubusercontent.com/AkaiiKitsune/OculusViewer/main/img/Preview.png)

## First time using the script

Unpack a copy of [scrcpy](https://github.com/Genymobile/scrcpy) in a folder named "scrcpy" next to the `view.py` file.

You then need to add 1 to 9 headsets in the headsets.json file. The "id" will determine it's position on the screen (It will be displayed in a 3 by 3 grid from top left to bottom right).

As of right now the script only really works on 1920x1080 screens (the grid gets fucked up on smaller resolutions)

When you start the script, you need to plug in your Quests one by one by usb and always authorize usb debugging for your computer.

Once this is done and you have sucessfully connected all your headsets, long press the ctrl key on your keyboard. The script will then start a scrcpy instance for each headset.

When you're done press escape to close everything.

## Using the script after initial setup

This script will save the last known ip of your Quests. solong as you only leave them in sleep mode and don't turn them off, the script will always directly connect to your Quests by wifi (no need to plug them by usb anymore). If you didn't set a fixed ip for your Quests and their ip changed or, if your turned them off; just plug them back with an usb cable and they'll be setup for wifi use again.
