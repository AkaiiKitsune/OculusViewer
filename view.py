import os
import re
import socket
import subprocess
from time import sleep
from usbmonitor import USBMonitor  # pip install usb-monitor
from usbmonitor.attributes import ID_MODEL, ID_MODEL_ID, ID_VENDOR_ID
from screeninfo import get_monitors  # pip install screeninfo
import PySimpleGUI as sg  # pip install pysimplegui==4.70.1
import adbutils  # pip install adbutils
import threading
import json

# sg.main()

adb = adbutils.AdbClient(host="127.0.0.1", port=5037)
font = ("Courier New", 11)
currentWindow = None
mainWindow = None

if not os.path.isfile("headsets.json"):
    with open("headsets.json", "w") as outfile:
        outfile.write(json.dumps({"headsets": []}, indent=4))
jsonDevices = json.load(open("headsets.json"))

newDevice = False
tableUpdate = True
stopThreads = False
currentdevices = [""]

screen = ""
for m in get_monitors():
    if m.is_primary:
        screen = m
        print("Using " + str(screen))

fps = "30"
bitrate = "1M"
# Quest 3
cropWidth = 1930
cropXOffset = 140
cropYOffset = 500

windowsPerLine = 3
windowLines = 3
captureWidth = int(screen.width / windowsPerLine)
captureHeight = int(screen.height / windowLines)
cropFactor = cropWidth / captureWidth
cropHeight = int(captureHeight * cropFactor)


crop = (
    str(cropWidth)
    + ":"
    + str(cropHeight)
    + ":"
    + str(cropXOffset)
    + ":"
    + str(cropYOffset)
)


class Layout:
    if not os.path.isfile("layout.json"):
        with open("layout.json", "w") as outfile:
            outfile.write(json.dumps([], indent=4))

    list = json.load(open("layout.json"))

    def __init__(self):
        next

    def getHeadsetIdFromGridId(self, gridId):
        for i in self.list:
            if int(i["gridId"]) == int(gridId):
                return i["headsetId"]
        return None

    def getIdFromHeadsetId(self, headsetId):
        self.list = json.load(open("layout.json"))
        for i in self.list:
            if int(i["headsetId"]) == int(headsetId):
                return int(i["gridId"])
        return None

    def updateEntry(self, gridId, headsetId):
        for entry in self.list:
            if entry["gridId"] == gridId:
                entry["headsetId"] = headsetId
                self.updateJson()
                return

        self.list.append(
            {
                "gridId": gridId,
                "headsetId": headsetId,
            }
        )
        self.updateJson()
        return

    def updateJson(self):
        jsonLayout = []
        for key in self.list:
            if key["headsetId"] != "":
                jsonLayout.append(key)

        json_object = json.dumps(jsonLayout, indent=4)
        with open("layout.json", "w") as outfile:
            outfile.write(json_object)


gridLayout = Layout()


class AdbDevice:
    def __init__(self, name, id, ip, serial, connected=False):
        self.name = name
        self.id = id
        self.ip = ip
        self.serial = serial
        self.connected = connected

        self.scrspyproc = None

        self.selftestthread = None
        self.selftestenable = True
        self.lostconnect = False

    def __repr__(self):
        return f"{self.name}"

    def start_scrcpy(self):
        if self.scrspyproc is None:
            gridId = gridLayout.getIdFromHeadsetId(headsetId=self.id)
            if gridId is not None:
                xindex = int(captureWidth) * gridId
                xposition = str(xindex % (screen.width - 1))
                yposition = str(
                    max(0, int(gridId / windowsPerLine)) * int(screen.height / 3)
                )

                self.scrspyproc = subprocess.Popen(
                    ".\scrcpy\scrcpy.exe -n --window-borderless --disable-screensaver --no-audio --rotation-offset=22 --video-codec=h265 --crop "
                    + crop
                    + " --max-fps="
                    + fps
                    + " -b "
                    + bitrate
                    + " -s "
                    + self.ip
                    + " --max-size "
                    + str(captureWidth)
                    + " --window-x="
                    + str(xposition)
                    + " --window-y="
                    + str(yposition)
                    + " --window-title="
                    + "'"
                    + self.name
                    + "'"
                )

    def stop_scrcpy(self):
        if self.scrspyproc is not None:
            self.scrspyproc.kill()
            self.scrspyproc = None
            print("Stopped video for " + self.serial, self.name)

    def start_watchdog(self):
        self.selftestenable = True
        if self.selftestthread is None:
            if self.ip != "":
                print("Starting watchdog for", self.serial, self.name)
                self.selftestthread = threading.Thread(
                    target=self.selftest, args=(), kwargs={}
                )
                self.selftestthread.start()

    def check_port(self, port=5555, timeout=2):
        sck = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sck.settimeout(timeout)
        try:
            sck.connect((self.ip, int(port)))
            sck.shutdown(socket.SHUT_RDWR)
            return True
        except:
            return False
        finally:
            sck.close()

    def selftest(self):
        global stopThreads
        global tableUpdate
        self.connect()
        while not stopThreads:
            # If the device has an IP and selftest is enabled...
            if self.selftestenable == True:
                if self.ip == "":
                    print(
                        "Ending selftest for",
                        self.serial,
                        self.name,
                        "because it has no IP. This should not happen!",
                    )
                    return

                # If we haven't lost connection,
                if not self.lostconnect:
                    devices = adb.device_list()
                    found = False
                    # We check if the device exist and if so, try to connect (this will do nothing if device already exists)
                    # It will however allow to reconnect if we lost connection before.
                    for device in devices:
                        if self.ip in device.serial:
                            found = True
                            self.connect()

                    # If we didn't find the device in the adb device list, we enter lost connection state
                    if not found:
                        if self.connected:
                            self.lostconnect = True
                            self.disconnect()

                # In the lost connection state, we check every 5 seconds if the wifi debug port of the device is open
                # If it does, we reconnect to the device.
                else:
                    if self.check_port():
                        self.connect()
                        sleep(5)
            sleep(5)

    def toJson(self):
        return {
            "id": self.id,
            "name": self.name,
            "ip": self.ip,
            "serial": self.serial,
        }

    def toList(self):
        return [self.connected, self.name, self.id, self.ip, self.serial]

    def connect(self):
        global tableUpdate
        try:
            self.start_watchdog()
            # If device has an IP
            if self.ip != "":
                # And if it is currently not connected
                if self.serial not in currentdevices:
                    print(
                        (
                            "Attempting to connect to"
                            if not self.lostconnect
                            else "Recovering connection to"
                        ),
                        self.serial,
                        "%s" % self.name if self.name != "" else self.ip,
                    )
                    # We connect and update the internal states accordingly
                    adb.connect(addr=self.ip + ":5555", timeout=3)
                    self.connected = True

                    if not self.lostconnect == True:
                        print("Successfully connected to", self.serial, self.name)
                    self.lostconnect = False

                    currentdevices.append(self.serial)
                    tableUpdate = True
                    if devices.streaming == True:
                        self.start_scrcpy()
            else:
                print("No known ip for", self.serial, self.name)
        except:
            # If we error out on connect, we update the internal states accordingly too.
            print("Couldn't connect to", self.serial, self.name)
            # self.ip = ""
            self.connected = False
            tableUpdate = True

    def disconnect(self):
        global tableUpdate
        try:
            print(
                (
                    "Disconnecting"
                    if not self.lostconnect
                    else "Lost connection" + " from"
                ),
                self.serial,
                self.name,
            )
            if self.serial in currentdevices:
                currentdevices.remove(self.serial)
            adb.disconnect(addr=self.ip + ":5555")
            if self.selftestthread is not None:
                if self.lostconnect == False:
                    self.selftestenable = False
                    print(
                        "ADBDEVICE Disconnect: Disabling selftest for",
                        self.serial,
                        self.name,
                    )

            try:
                self.scrspyproc.kill()
            except:
                pass
            self.scrspyproc = None
            self.connected = False
        except Exception as error:
            print("ADBDEVICE Disconnect:", error)
        self.connected = False
        tableUpdate = True


class AdbDevices:
    adblist = []
    jsonadblist = []
    streaming = False

    def __init__(self, list=[]):
        self.adblist = list
        for device in jsonDevices["headsets"]:
            self.jsonadblist.append(
                AdbDevice(
                    name=device["name"],
                    id=device["id"],
                    ip=device["ip"],
                    serial=device["serial"],
                )
            )

    def remove(self, value):
        global tableUpdate
        try:
            print("Removing", value.serial, value.name)
            value.disconnect()
            self.adblist.remove(value)
            tableUpdate = True
        except Exception as error:
            print(error)
        pass

    def add(self, value):
        global tableUpdate
        # print("Adding device to list")
        found = False
        for device in self.adblist:
            if device.serial == value.serial:
                device.connected = True
                device.ip = value.ip
                if device.serial not in currentdevices:
                    currentdevices.append(device.serial)
                found = True
                break
        if not found:
            self.adblist.append(value)
        self.updateJson()
        tableUpdate = True

    def reconnect(self):
        global tableUpdate
        global currentWindow
        print("Attempting to connect to last known ip's")
        index = 0
        for device in self.adblist:
            index += 1
            try:
                mainWindow.set_title(
                    f"OculusViewer Setup - Connecting to last known ip's... {index}/{len(self.adblist)}"
                )
                if device.ip != "":
                    device.connect()
            except:
                exit("Errored out on reconnect")
        mainWindow.set_title("OculusViewer Setup")

    def kill_server(self):
        global tableUpdate
        print("Killing ADB Server")
        for device in self.adblist:
            device.disconnect()
        adb.server_kill()
        tableUpdate = True

    def sort(self):
        # print("Sorting list")
        try:
            self.adblist.sort(key=lambda x: int(x.id), reverse=False)
        except Exception as error:
            print(error)
            pass

    def toList(self):
        temp = []
        for item in self.adblist:
            temp.append(item.toList())
        return temp

    def updateJson(self):
        # print("Updating json list")
        self.sort()
        jsonDevices = {"headsets": []}
        for device in self.adblist:
            jsonDevices["headsets"].append(device.toJson())

        json_object = json.dumps(jsonDevices, indent=4)
        with open("headsets.json", "w") as outfile:
            outfile.write(json_object)

    def addExistingDevices(self):
        print("Adding existing devices")
        for device in self.jsonadblist:
            if device.serial not in self.adblist:
                self.adblist.append(device)
                device.start_watchdog()

    def stream(self, streamingStatus: bool):
        self.streaming = streamingStatus
        if streamingStatus == True:
            print("Starting Streaming")
            for device in sorted(devices.adblist, key=lambda device: device.id):
                if device.connected:
                    device.start_scrcpy()
                    if gridLayout.getIdFromHeadsetId(headsetId=device.id) != None:
                        sleep(2)
                    else:
                        print(
                            device.serial,
                            device.name,
                            "is not assigned a position, skipping",
                        )
                else:
                    print(device.serial, device.name, "is not connected, skipping")
        else:
            for device in sorted(devices.adblist, key=lambda device: device.id):
                if device.scrspyproc is not None:
                    device.stop_scrcpy()


devices = AdbDevices()


def block_focus(window):
    for key in window.key_dict:  # Remove dash box of all Buttons
        element = window[key]
        if isinstance(element, sg.Button):
            element.block_focus()


def editDevice_popup(deviceId):
    global tableUpdate
    global currentWindow
    device = devices.adblist[deviceId]

    col_layout = [[sg.Button("OK", key="-OK-")]]
    layout = [
        [
            sg.Text("Current id : "),
            sg.Input(
                device.id,
                enable_events=True,
                key="-ID_INPUT-",
                expand_x=True,
                justification="left",
            ),
        ],
        [
            sg.Text("Current name : "),
            sg.Input(
                device.name,
                enable_events=True,
                key="-NAME_INPUT-",
                expand_x=True,
                justification="left",
            ),
        ],
        [sg.Column(col_layout, expand_x=True, element_justification="right")],
    ]
    window = sg.Window(
        "Device", layout, use_default_focus=False, finalize=True, modal=True
    )
    block_focus(window)
    currentWindow = window

    while True:
        event, values = window.read()
        if event == "Exit" or event == sg.WIN_CLOSED:
            window.close()
            break

        # if last char entered not a digit
        if (
            event == "-ID_INPUT-"
            and len(values["-ID_INPUT-"])
            and values["-ID_INPUT-"][-1] not in ("-0123456789")
        ):
            # delete last char from input
            window["-ID_INPUT-"].update(values["-ID_INPUT-"][:-1])

        elif event == "-OK-":
            if len(values["-ID_INPUT-"]) > 0 and len(values["-NAME_INPUT-"]) > 0:
                devices.adblist[deviceId].name = values["-NAME_INPUT-"]
                devices.adblist[deviceId].id = values["-ID_INPUT-"]
                devices.updateJson()
                window.close()
                tableUpdate = True
                break

    return None


def addDevice_popup():
    global tableUpdate
    global newDevice
    global currentWindow
    oldDevicesList = [device.serial for device in adb.device_list()]
    newDevicesList = []
    devicesDiff = []
    newDevice = False

    print("Old device list :", oldDevicesList)
    window = sg.Window(
        "New Device",
        [[sg.Text("Waiting for a new device...")]],
        use_default_focus=False,
        finalize=True,
        modal=True,
    )
    block_focus(window)
    currentWindow = window

    # We're waiting for a new android device to be connected.
    while True:
        event, values = window.Read(timeout=100)
        if event == "Exit" or event == sg.WIN_CLOSED:
            window.close()
            return

        if newDevice == True:
            sleep(1)
            newDevicesList = [device.serial for device in adb.device_list()]
            print("New device list:", newDevicesList)

            devicesDiff = [
                item for item in newDevicesList if item not in oldDevicesList
            ]

            if len(devicesDiff) > 0:
                print("Found new device:", devicesDiff)
                window.close()
                break
            else:
                # We update the old device list if a device has been disconnected
                oldDevicesList = [device.serial for device in adb.device_list()]
    # Exited first window, found a new device.

    try:
        # We check the wifi on which the device is connected to.
        d = adb.device(serial=devicesDiff[0])
        pattern = r'(?:wifiNetworkKey|networkId)="([^"]+)"'
        wlan0 = d.shell("dumpsys netstats | grep -E 'iface=wlan.'")
        wifiName = re.findall(pattern, wlan0)
        sentence = (
            "connected to " + wifiName[0]
            if len(wifiName) > 0
            else "not connected to wifi."
        )

        if len(wifiName) == 0:
            sg.popup_error("Your device needs to be connected to wifi.")
            return

        # If user said yes, we try to enable wireless debugging.
        deviceserial = d.serial
        ip = d.wlan_ip()

        # We first check that the device isn't already connected
        for device in devices.adblist:
            if device.serial == deviceserial:
                if device.connected == True:
                    sg.popup(
                        deviceserial + " is already connected !",
                        auto_close=True,
                        auto_close_duration=5,
                    )
                    return
                else:
                    sg.popup(
                        deviceserial
                        + " "
                        + device.name
                        + " is already known, connecting !",
                        auto_close=True,
                        auto_close_duration=5,
                    )
                    device.connect()
                    return

        print(deviceserial, " is not in current device list")
        mainWindow.set_title("OculusViewer Setup - Adding " + deviceserial + "...")

        # If the device isn't already in wifi debug mode, we enable it
        if ip not in deviceserial:
            print("Enabling wifi debugging for " + deviceserial)
            d.tcpip(port=5555)
            sleep(2)  # We wait just a bit

        # we then connect to the device
        adb.connect(addr=ip, timeout=5)
        d = adb.device(serial=ip + ":5555")
        print("We connected to", deviceserial + " (" + d.serial + ") !")

    # If anything happens during wifi debug init or connection, we error out.
    except Exception as error:
        print("We had an unexpected error :", error)
        sg.popup_error(
            "Unexpected error :",
            error,
            "\nMake sure you are connected to the right wifi network on the device.",
        )
        mainWindow.set_title("OculusViewer Setup")
        return

    # We found a new android device in debug mode and connected to it. we're adding it to the list !
    col_layout = [[sg.Button("OK", key="-OK-")]]
    layout = [
        [
            sg.Text("New device: " + deviceserial + " (" + d.serial + ")"),
        ],
        [
            sg.Text("New id : "),
            sg.Input(
                "",
                enable_events=True,
                key="-ID_INPUT-",
                expand_x=True,
                justification="left",
            ),
        ],
        [
            sg.Text("New name : "),
            sg.Input(
                "",
                enable_events=True,
                key="-NAME_INPUT-",
                expand_x=True,
                justification="left",
            ),
        ],
        [sg.Column(col_layout, expand_x=True, element_justification="right")],
    ]
    window = sg.Window(
        "Adding Device",
        layout,
        use_default_focus=False,
        finalize=True,
        modal=True,
    )
    block_focus(window)
    currentWindow = window

    while True:
        event, values = window.read()
        if event == "Exit" or event == sg.WIN_CLOSED:
            window.close()
            break

        # if last char entered not a digit
        if (
            event == "-ID_INPUT-"
            and len(values["-ID_INPUT-"])
            and values["-ID_INPUT-"][-1] not in ("-0123456789")
        ):
            # delete last char from input
            window["-ID_INPUT-"].update(values["-ID_INPUT-"][:-1])

        elif event == "-OK-":
            if len(values["-ID_INPUT-"]) > 0 and len(values["-NAME_INPUT-"]) > 0:
                print("Adding", deviceserial, values["-NAME_INPUT-"])

                adbDevice = AdbDevice(
                    ip=ip,
                    name=values["-NAME_INPUT-"],
                    id=values["-ID_INPUT-"],
                    serial=deviceserial,
                    connected=True,
                )
                adbDevice.connect()
                devices.add(adbDevice)
                devices.updateJson()

                tableUpdate = True
                window.close()
                break

    mainWindow.set_title("OculusViewer Setup")


def enableDebug_popup():
    global tableUpdate
    global newDevice
    global currentWindow
    oldDevicesList = [device.serial for device in adb.device_list()]
    newDevicesList = []
    devicesDiff = []
    newDevice = False
    lastconnected = ""

    print("Old device list :", oldDevicesList)
    window = sg.Window(
        "New Device",
        [[sg.Text("Waiting for device...")]],
        use_default_focus=False,
        finalize=True,
        modal=True,
    )
    block_focus(window)
    currentWindow = window

    # We're waiting for a new android device to be connected.
    while True:
        event, values = window.Read(timeout=100)
        if event == "Exit" or event == sg.WIN_CLOSED:
            window.close()
            return

        if newDevice == True:
            block_focus(window)
            sleep(1)
            newDevice = False
            newDevicesList = [device.serial for device in adb.device_list()]
            print("New device list:", newDevicesList)

            devicesDiff = [
                item for item in newDevicesList if item not in oldDevicesList
            ]

            # If we found a new device, we check if we already know it.
            if len(devicesDiff) > 0:
                print("Found new device:", devicesDiff)
                try:
                    # We check the wifi on which the device is connected to.
                    d = adb.device(serial=devicesDiff[0])
                    pattern = r'(?:wifiNetworkKey|networkId)="([^"]+)"'
                    wlan0 = d.shell("dumpsys netstats | grep -E 'iface=wlan.'")
                    wifiName = re.findall(pattern, wlan0)

                    if len(wifiName) == 0:
                        sg.popup_error("Your device needs to be connected to wifi.")
                        next

                    deviceserial = d.serial
                    ip = d.wlan_ip()

                    # We first check that the device isn't already connected
                    deviceAlreadyConnected = False
                    deviceAlreadyExists = False
                    for device in devices.adblist:
                        if device.serial == deviceserial:
                            deviceAlreadyExists = True
                            if device.connected == True:
                                deviceAlreadyConnected = True

                    if deviceAlreadyConnected:
                        if deviceserial not in lastconnected:
                            sg.popup(
                                deviceserial + " is already connected !",
                                auto_close=True,
                                auto_close_duration=5,
                            )
                    else:
                        if not deviceAlreadyExists:
                            if not deviceserial[-5:] == ":5555":
                                sg.popup(
                                    deviceserial
                                    + " is not known, you need to add it first !",
                                    auto_close=True,
                                    auto_close_duration=5,
                                )
                            else:
                                print("New device is an ip, skipping")
                        else:
                            mainWindow.set_title(
                                "OculusViewer Setup - Connecting to "
                                + deviceserial
                                + "..."
                            )

                            # If the device isn't already in wifi debug mode, we enable it
                            if ip not in deviceserial:
                                print("Enabling wifi debugging for " + deviceserial)
                                d.tcpip(port=5555)
                                sleep(2)  # We wait just a bit

                            # we then connect to the device
                            adb.connect(addr=ip, timeout=5)
                            d = adb.device(serial=ip + ":5555")
                            print(
                                "We connected to",
                                deviceserial + " (" + d.serial + ") !",
                            )
                            for device in devices.adblist:
                                if device.serial == deviceserial:
                                    device.connected = True
                                    if deviceserial not in currentdevices:
                                        currentdevices.append(deviceserial)
                                    tableUpdate = True
                                    lastconnected = device.serial
                                    sg.popup(
                                        deviceserial
                                        + " ("
                                        + ip
                                        + ") is now connected !",
                                        auto_close_duration=5,
                                        auto_close=True,
                                    )

                # If anything happens during wifi debug init or connection, we error out.
                except Exception as error:
                    print("We had an unexpected error :", error)
                    sg.popup_error(
                        "Unexpected error :",
                        error,
                        "\nMake sure you are connected to the right wifi network on the device.",
                    )
                    mainWindow.set_title("OculusViewer Setup")
                    return
            else:
                # We update the old device list if a device has been disconnected
                oldDevicesList = [device.serial for device in adb.device_list()]
                lastconnected = ""

            mainWindow.set_title("OculusViewer Setup")


def settings_screen():
    def callback(event):
        x, y = window.TKroot.winfo_pointerxy()
        widget = window.TKroot.winfo_containing(x, y)
        # scrollbar not saved as attribute, so not work for it.
        if widget not in (table, table_frame):
            window.write_event_value("WINDOW_CLICK", (x, y))

    global newDevice
    global tableUpdate
    global currentWindow
    global mainWindow

    # ----- Full layout -----
    rows = 3
    cols = 3

    grid = [[sg.Text("Display grid :")]]
    gridId = 0
    dropdown = [""]
    for col in range(cols):
        temp = []
        for row in range(rows):
            dropdown.append(gridId)
            HeadsetId = gridLayout.getHeadsetIdFromGridId(gridId)

            temp.append(
                sg.Frame(
                    layout=[
                        [
                            sg.Combo(
                                values=dropdown,
                                default_value=(
                                    HeadsetId if HeadsetId is not None else ""
                                ),
                                expand_x=True,
                                enable_events=True,
                                readonly=True,
                                key="-DROPDOWN_" + str(gridId) + "-",
                            )
                        ],
                    ],
                    title="",
                )
            )

            gridId += 1
        grid.append(temp)

    headings = ["Connected", "Name", "Id", "Ip", "Serial"]
    device_list = [
        [
            sg.Text("Current devices : "),
        ],
        [
            sg.Table(
                values=devices.toList(),
                headings=headings,
                auto_size_columns=False,
                def_col_width=20,
                num_rows=30,
                font=font,
                col_widths=[
                    11,
                    20,
                    5,
                    17,
                    21,
                    21,
                ],
                expand_x=True,
                expand_y=True,
                justification="center",
                key="-TABLE-",
                select_mode=sg.TABLE_SELECT_MODE_BROWSE,
                selected_row_colors="red on yellow",
                enable_events=True,
            )
        ],
        [
            sg.Column(
                [
                    [
                        sg.pin(
                            sg.Button(
                                "Disconnect",
                                enable_events=True,
                                key="-CONNECT_DEVICE-",
                                visible=False,
                                expand_x=True,
                                expand_y=True,
                            ),
                        ),
                        sg.pin(
                            sg.Button(
                                "Edit device",
                                enable_events=True,
                                key="-EDIT_DEVICE-",
                                visible=False,
                                expand_x=True,
                                expand_y=True,
                            )
                        ),
                        sg.pin(
                            sg.Button(
                                "Remove device",
                                enable_events=True,
                                key="-REMOVE_DEVICE-",
                                visible=False,
                                button_color="red",
                                expand_x=True,
                                expand_y=True,
                            ),
                        ),
                    ]
                ],
                expand_x=True,
                expand_y=True,
                element_justification="right",
            ),
        ],
    ]

    menu_def = [
        [
            "Devices",
            ["Add New Device", "Initiate Known Devices"],
        ],
        ["Server", ["Reconnect to all IPs", "Kill Server"]],
        ["Help", "About..."],
    ]
    grid.append(
        [
            sg.Button(
                "Start Streaming",
                enable_events=True,
                key="-START-",
                expand_x=True,
                expand_y=True,
            ),
            sg.Button(
                "Stop Streaming",
                enable_events=True,
                key="-STOP-",
                expand_x=True,
                expand_y=True,
                button_color="red",
                visible=False,
            ),
        ]
    )
    layout = [
        [
            [sg.Menu(menu_def)],
            sg.Column(device_list),
            sg.VSeparator(),
            sg.Column(grid),
        ]
    ]

    window = sg.Window("OculusViewer Setup", layout, finalize=True)
    window["-TABLE-"].bind("<Double-Button-1>", "+-double click-")
    table = window["-TABLE-"].Widget
    table_frame = window["-TABLE-"].table_frame
    window.TKroot.bind("<ButtonRelease-1>", callback, add="+")
    currentWindow = mainWindow = window
    data_selected = []

    # newdevicethread = threading.Thread(target=connectToNewDevice, args=(), kwargs={})
    reconnectdevicesthread = threading.Thread(
        target=devices.reconnect, args=(), kwargs={}
    )
    # reconnectdevicesthread.start()

    def updateTable():
        devices.sort()
        # print(devices.toList())
        window["-TABLE-"].Update(values=devices.toList())

        colorTuple = ()
        index = 0
        for device in devices.adblist:
            if device.connected == True:
                colorTuple += ((index, "green"),)
            elif device.lostconnect:
                colorTuple += ((index, "black"),)
            else:
                colorTuple += (((index, sg.theme_background_color())),)
            index += 1

        window["-TABLE-"].Update(row_colors=(tuple(colorTuple)))
        try:
            window["-TABLE-"].Update(select_rows=data_selected)
        except:
            window["-TABLE-"].Update(select_rows=[])

    def unselectTable():
        window["-EDIT_DEVICE-"].Update(visible=False)
        window["-REMOVE_DEVICE-"].Update(visible=False)
        window["-CONNECT_DEVICE-"].Update(visible=False)
        window["-TABLE-"].Update(select_rows=[])

    while True:
        event, values = window.Read(timeout=100)
        if event == "Exit" or event == sg.WIN_CLOSED:
            window.close()
            break

        # elif event == "WINDOW_CLICK":
        #     window["-EDIT_DEVICE-"].Update(visible=False)
        #     window["-REMOVE_DEVICE-"].Update(visible=False)
        #     window["-CONNECT_DEVICE-"].Update(visible=False)
        #     window["-TABLE-"].Update(select_rows=[])
        elif event == "Add New Device":
            unselectTable()
            addDevice_popup()

        elif event == "Kill Server":
            unselectTable()
            devices.kill_server()

        elif event == "Reconnect to all IPs":
            unselectTable()
            if not reconnectdevicesthread.is_alive():
                reconnectdevicesthread = threading.Thread(
                    target=devices.reconnect, args=(), kwargs={}
                )
                reconnectdevicesthread.start()

        elif event == "Initiate Known Devices":
            unselectTable()
            enableDebug_popup()

        elif event == "-TABLE-":
            if data_selected == values[event] and data_selected != []:
                data_selected = []
                window["-CONNECT_DEVICE-"].Update(visible=False)
                window["-EDIT_DEVICE-"].Update(visible=False)
                window["-REMOVE_DEVICE-"].Update(visible=False)
                updateTable()
            else:
                data_selected = values[event]
                if len(data_selected) > 0:
                    if devices.adblist[values["-TABLE-"][0]].connected:
                        window["-CONNECT_DEVICE-"].Update("Disconnect")
                    else:
                        window["-CONNECT_DEVICE-"].Update("Connect")
                    window["-CONNECT_DEVICE-"].Update(visible=True)
                    window["-EDIT_DEVICE-"].Update(visible=True)
                    window["-REMOVE_DEVICE-"].Update(visible=True)

        elif any(["+-double click-" in event, "-EDIT_DEVICE-" in event]):
            deviceId = values["-TABLE-"]
            if len(deviceId) > 0:
                editDevice_popup(deviceId[0])
                currentWindow = window

        elif "-DROPDOWN_" in event:
            unselectTable()
            for i in range(rows * cols):
                value = values["-DROPDOWN_" + str(i) + "-"]
                gridLayout.updateEntry(gridId=i, headsetId=value)
                window["-CONNECT_DEVICE-"].Update(visible=False)

            for i in range(rows * cols):
                HeadsetId = gridLayout.getHeadsetIdFromGridId(gridId=i)
                window["-DROPDOWN_" + str(i) + "-"].update(
                    HeadsetId if HeadsetId is not None else ""
                )

        elif event == "-CONNECT_DEVICE-":
            # If device is connected, we disconnect and unselect the table
            if devices.adblist[values["-TABLE-"][0]].connected:
                devices.adblist[values["-TABLE-"][0]].disconnect()
            else:
                # If device is not connected, we connect to it.
                devices.adblist[values["-TABLE-"][0]].connect()

        elif event == "-REMOVE_DEVICE-":
            unselectTable()
            if (
                sg.popup_ok_cancel(
                    "This will remove "
                    + devices.adblist[values["-TABLE-"][0]].name
                    + " !"
                )
                == "OK"
            ):
                devices.remove(devices.adblist[values["-TABLE-"][0]])
                devices.updateJson()
                updateTable()

            else:
                next

        elif event == "-START-":
            unselectTable()
            devices.stream(streamingStatus=True)
            window["-START-"].Update(visible=False)
            window["-STOP-"].Update(visible=True)

        elif event == "-STOP-":
            unselectTable()
            devices.stream(streamingStatus=False)
            window["-START-"].Update(visible=True)
            window["-STOP-"].Update(visible=False)

        elif event == "About...":
            os.system('start "" https://github.com/AkaiiKitsune/OculusViewer/')

        elif tableUpdate:
            tableUpdate = False
            updateTable()


device_info_str = (
    lambda device_info: f"{device_info[ID_MODEL]} ({device_info[ID_MODEL_ID]} - {device_info[ID_VENDOR_ID]})"
)


# Define the `on_connect` and `on_disconnect` callbacks
def on_connect(device_id, device_info):
    print(f"Connected: {device_info_str(device_info=device_info)}")
    global newDevice
    newDevice = True


def on_disconnect(device_id, device_info):
    print(f"Disconnected: {device_info_str(device_info=device_info)}")
    global newDevice
    newDevice = True


# Create the USBMonitor instance
monitor = USBMonitor()

# Start the daemon
monitor.start_monitoring(on_connect=on_connect, on_disconnect=on_disconnect)

# ... Rest of your code ...
devices.addExistingDevices()
settings_screen()

# If you don't need it anymore stop the daemon
monitor.stop_monitoring()
stopThreads = True

for device in devices.adblist:
    device.stop_scrcpy()
