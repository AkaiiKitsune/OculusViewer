import os
import re
import socket
import subprocess
from time import sleep
from usbmonitor import USBMonitor
from usbmonitor.attributes import ID_MODEL, ID_MODEL_ID, ID_VENDOR_ID
import PySimpleGUI as sg
import adbutils  # pip install adbutils
import threading
import json

adb = adbutils.AdbClient(host="127.0.0.1", port=5037)
jsonDevices = json.load(open("headsets.json"))
font = ("Courier New", 11)
currentWindow = None

newDevice = False
tableUpdate = True
stopThreads = False
currentdevices = [""]


class AdbDevice:
    selftestthread = None
    lostconnect = False

    def __init__(self, name, id, ip, mac, connected=False):
        self.name = name
        self.id = id
        self.ip = ip
        self.mac = mac
        self.connected = connected

    def __repr__(self):
        return f"{self.name}"

    def start_watchdog(self):
        if self.selftestthread is None:
            print("Starting watchdog for", self.mac)
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
        while not stopThreads:
            if self.ip != "":
                try:
                    devices = adb.device_list()
                    found = False
                    for device in devices:
                        if self.ip in device.serial:
                            found = True

                    if not found:
                        if self.connected:
                            self.disconnect()
                            self.lostconnect = True
                    else:
                        if not self.connected:
                            if self.check_port():
                                self.connect()
                except:
                    pass
            sleep(2)

    def toJson(self):
        return {"id": self.id, "mac": self.mac, "name": self.name, "ip": self.ip}

    def toList(self):
        return [self.connected, self.name, self.id, self.ip, self.mac]

    def connect(self):
        global tableUpdate
        try:
            self.start_watchdog()
            if self.ip != "":
                print("connecting to", self.ip)
                adb.connect(addr=self.ip + ":5555", timeout=5)
                self.connected = True
                self.lostconnect = False
                tableUpdate = True
            else:
                print("no known ip for", self.mac)
        except:
            print("couldn't connect to", self.ip)
            self.ip = ""
            self.connected = False
            tableUpdate = True

    def disconnect(self):
        global tableUpdate
        try:
            print("Disconnecting from", self.mac, self.name)
            try:
                currentdevices.remove(self.mac)
            except:
                pass
            adb.disconnect(addr=self.ip + ":5555")

            self.connected = False
            # self.ip = ""
        except Exception as error:
            print(error)
        tableUpdate = True


class AdbDevices:
    adblist = []
    jsonadblist = []

    def __init__(self, list=[]):
        self.adblist = list
        for device in jsonDevices["headsets"]:
            self.jsonadblist.append(
                AdbDevice(
                    name=device["name"],
                    id=device["id"],
                    ip=device["ip"],
                    mac=device["mac"].upper(),
                )
            )

    def remove(self, value):
        global tableUpdate
        self.adblist.remove(value)
        try:
            print("Removing ", value.ip)
            currentdevices.remove(value.mac)
            adb.disconnect(addr=value.ip + ":5555")
            tableUpdate = True
        except Exception as error:
            print(error)
        pass

    def add(self, value):
        global tableUpdate
        # print("Adding device to list")
        found = False
        for device in self.adblist:
            if device.mac == value.mac:
                device.connected = True
                device.ip = value.ip
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
            currentWindow.set_title(
                f"OculusViewer Setup - Connecting to last known ip's... {index}/{len(self.adblist)}"
            )
            if device.ip != "":
                device.connect()
        currentWindow.set_title("OculusViewer Setup")
        self.updateJson()

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


class Layout:
    list = json.load(open("layout.json"))

    def __init__(self):
        next

    def getIdFromFromGridId(self, gridId):
        for i in self.list:
            if i["gridId"] == gridId:
                return i["headsetId"]

    def updateJson(self):
        jsonLayout = []
        for key in self.list:
            if key["headsetId"] != "":
                jsonLayout.append(key)

        json_object = json.dumps(jsonLayout, indent=4)
        with open("layout.json", "w") as outfile:
            outfile.write(json_object)


devices = AdbDevices()
gridLayout = Layout()


def connectToExistingDevices():
    print("Connecting to existing devices")
    # Searching for devices already connected to the computer
    global tableUpdate
    global currentWindow
    adbdevices = adb.device_list()
    for device in adbdevices:
        name = ""
        id = -1
        ip = device.wlan_ip()
        wlan = device.shell("ip addr show wlan0")
        mac = (
            re.search("link/ether ..:..:..:..:..:..", wlan)
            .group()
            .replace("link/ether ", "")
        ).upper()

        if not mac in currentdevices:
            for i in jsonDevices["headsets"]:
                if mac == str(i["mac"]).upper():
                    id = i["id"]
                    name = i["name"]
                    break
            adbDevice = AdbDevice(ip=ip, mac=mac, name=name, id=id, connected=True)
            print(
                "found",
                adbDevice.mac,
                adbDevice.name if adbDevice.name != "" else adbDevice.ip,
            )
            devices.adblist.append(adbDevice)
            adbDevice.start_watchdog()
            tableUpdate = True
            currentdevices.append(mac)

    for device in devices.jsonadblist:
        if device.mac not in currentdevices:
            devices.adblist.append(device)
            device.start_watchdog()


def connectToNewDevice():
    try:
        global tableUpdate
        global newDevice
        adbdevices = adb.device_list()
        for device in adbdevices:
            serial = device.serial
            ip = device.wlan_ip()

        for device in adbdevices:
            serial = device.serial
            ip = device.wlan_ip()
            wlan = device.shell("ip addr show wlan0")
            name = ""
            id = -1
            mac = (
                re.search("link/ether ..:..:..:..:..:..", wlan)
                .group()
                .replace("link/ether ", "")
            ).upper()

            if not mac in currentdevices:
                if ip not in serial:
                    currentWindow.set_title("OculusViewer Setup - Adding new device...")
                    # print(mac, " is not in current device list")
                    device.tcpip(port=5555)
                    adb.connect(addr=ip, timeout=10)
                    ip = device.wlan_ip()
                    serial = device.serial
                    sleep(2)

                if ip in serial:
                    for i in jsonDevices["headsets"]:
                        if mac == str(i["mac"]).upper():
                            id = i["id"]
                            name = i["name"]
                            break

                    print("Adding", mac, name)

                    adbDevice = AdbDevice(
                        ip=ip, mac=mac, name=name, id=id, connected=True
                    )
                    devices.add(adbDevice)
                    adbDevice.start_watchdog()
                    currentdevices.append(mac)
                    newDevice = False
                    tableUpdate = True
            else:
                pass
    except Exception as error:
        # print(error)
        pass
    try:
        currentWindow.set_title("OculusViewer Setup")
    except:
        pass


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

    # ----- Full layout -----
    rows = 3
    cols = 3

    grid = [[sg.Text("Display grid :")]]
    gridId = 0
    dropdown = [""]
    for col in range(cols):
        for row in range(rows):
            dropdown.append(gridId)
            gridId += 1
    gridId = 0
    for col in range(cols):
        temp = []
        for row in range(rows):
            try:
                headsetId = int(gridLayout.getIdFromFromGridId(gridId=gridId)) + 1
            except:
                headsetId = 0

            temp.append(
                sg.Frame(
                    layout=[
                        [
                            sg.Combo(
                                values=dropdown,
                                default_value=dropdown[headsetId],
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

    headings = ["Connected", "Name", "Id", "Ip", "Mac"]
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
                num_rows=10,
                font=font,
                col_widths=[
                    11,
                    20,
                    5,
                    17,
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
            sg.Button("Start OculusViewer", enable_events=True, key="-START-"),
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
            ["Reconnect", "Kill Server"],
        ],
        ["Help", "About..."],
    ]
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
    currentWindow = window

    newdevicethread = threading.Thread(target=connectToNewDevice, args=(), kwargs={})
    reconnectdevicesthread = threading.Thread(
        target=devices.reconnect, args=(), kwargs={}
    )

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

    while True:
        event, values = window.Read(timeout=30)
        if event == "Exit" or event == sg.WIN_CLOSED:
            window.close()
            break

        elif event == "WINDOW_CLICK":
            window["-EDIT_DEVICE-"].Update(visible=False)
            window["-REMOVE_DEVICE-"].Update(visible=False)
            window["-CONNECT_DEVICE-"].Update(visible=False)
            window["-TABLE-"].Update(select_rows=[])

        elif event == "Kill Server":
            devices.kill_server()

        elif event == "Reconnect":
            if not reconnectdevicesthread.is_alive():
                reconnectdevicesthread = threading.Thread(
                    target=devices.reconnect, args=(), kwargs={}
                )
                reconnectdevicesthread.start()

        elif event == "-TABLE-":
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
                window["-CONNECT_DEVICE-"].Update(visible=False)
                window["-EDIT_DEVICE-"].Update(visible=False)
                window["-REMOVE_DEVICE-"].Update(visible=False)
                currentWindow = window

        elif "-DROPDOWN_" in event:
            for i in range(rows * cols):
                try:
                    value = values["-DROPDOWN_" + str(i) + "-"]
                    gridLayout.list[i]["headsetId"] = value
                except Exception as error:
                    gridLayout.list.append(
                        {
                            "gridId": i,
                            "headsetId": value,
                        }
                    )
            gridLayout.updateJson()

        elif event == "-CONNECT_DEVICE-":
            if devices.adblist[values["-TABLE-"][0]].connected:
                devices.adblist[values["-TABLE-"][0]].disconnect()
            else:
                print("Reconnecting")

        elif event == "-REMOVE_DEVICE-":
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
            print("Starting View")
            updateTable()

        elif tableUpdate:
            tableUpdate = False
            updateTable()

        if newDevice == True:
            if not newdevicethread.is_alive():
                newdevicethread = threading.Thread(
                    target=connectToNewDevice, args=(), kwargs={}
                )
                newdevicethread.start()


device_info_str = (
    lambda device_info: f"{device_info[ID_MODEL]} ({device_info[ID_MODEL_ID]} - {device_info[ID_VENDOR_ID]})"
)


# Define the `on_connect` and `on_disconnect` callbacks
def on_connect(device_id, device_info):
    # print(f"Connected: {device_info_str(device_info=device_info)}")
    global newDevice
    newDevice = True


def on_disconnect(device_id, device_info):
    # print(f"Disconnected: {device_info_str(device_info=device_info)}")
    global newDevice
    newDevice = False


# Create the USBMonitor instance
monitor = USBMonitor()

# Start the daemon
monitor.start_monitoring(on_connect=on_connect, on_disconnect=on_disconnect)

# ... Rest of your code ...
connectToExistingDevices()
settings_screen()

# If you don't need it anymore stop the daemon
monitor.stop_monitoring()
stopThreads = True
