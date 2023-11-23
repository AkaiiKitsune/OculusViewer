from usbmonitor import USBMonitor
from usbmonitor.attributes import ID_MODEL, ID_MODEL_ID, ID_VENDOR_ID
import PySimpleGUI as sg
import adbutils  # pip install adbutils
import json

adb = adbutils.AdbClient(host="127.0.0.1", port=5037)
jsonDevices = json.load(open("headsets.json"))
font = ("Courier New", 11)

newDevice = False


class AdbDevice:
    def __init__(self, name, id, ip, mac, connected=False):
        self.name = name
        self.id = id
        self.ip = ip
        self.mac = mac
        self.connected = connected

    def __repr__(self):
        return f"{self.name}"

    def toJson(self):
        return {"id": self.id, "mac": self.mac, "name": self.name, "ip": self.ip}

    def toList(self):
        return [self.name, self.id, self.ip, self.mac]


class AdbDevices:
    list = []

    def __init__(self, list):
        self.list = list

    def add(self, value):
        list.append(value)

    def sort(self):
        try:
            list.sort(key=lambda x: int(x.id), reverse=False)
        except:
            pass

    def toList(self):
        temp = []
        for item in self.list:
            temp.append(item.toList())
        return temp

    def updateJson(self):
        self.sort()
        jsonDevices = {"headsets": []}
        for device in self.list:
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


gridLayout = Layout()

deviceListFromjson = []
for device in jsonDevices["headsets"]:
    deviceListFromjson.append(
        AdbDevice(
            name=device["name"],
            id=device["id"],
            ip=device["ip"],
            mac=device["mac"].upper(),
        )
    )
devices = AdbDevices(list=[])
devices.sort()

currentdevices = [""]


def connectToNewDevice():
    devices = adb.device_list()

    for device in devices:
        try:
            serial = device.serial
            ip = device.wlan_ip()

            if not ip in currentdevices:
                if ip not in serial:
                    device.tcpip(port=5555)
                    adb.connect(addr=ip, timeout=3)
                    serial = device.serial

                if ip in serial:
                    wlan = device.shell("ip addr show wlan0")
                    print("Added new device !")
                    global newDevice
                    newDevice = False
                    # AdbDevice(serial=serial, wlan=wlan)
                    currentdevices.append(ip)
        except:
            pass
    pass


def block_focus(window):
    for key in window.key_dict:  # Remove dash box of all Buttons
        element = window[key]
        if isinstance(element, sg.Button):
            element.block_focus()


def editDevice_popup(deviceId):
    device = devices.list[deviceId]

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
                devices.list[deviceId].name = values["-NAME_INPUT-"]
                devices.list[deviceId].id = values["-ID_INPUT-"]
                devices.updateJson()
                window.close()
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

    headings = ["Name", "Id", "Ip", "Mac"]
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
                # col_widths=col_widths,  # Define each column width as len(string)+
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
                                "Edit device",
                                enable_events=True,
                                key="-EDIT_DEVICE-",
                                visible=False,
                            )
                        ),
                        sg.pin(
                            sg.Button(
                                "Remove device",
                                enable_events=True,
                                key="-REMOVE_DEVICE-",
                                visible=False,
                                button_color="red",
                            ),
                        ),
                    ]
                ],
                expand_x=True,
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

    while True:
        event, values = window.read(timeout=100)
        if event == "Exit" or event == sg.WIN_CLOSED:
            window.close()
            break

        elif event == "WINDOW_CLICK":
            window["-EDIT_DEVICE-"].Update(visible=False)
            window["-REMOVE_DEVICE-"].Update(visible=False)
            window["-TABLE-"].Update(select_rows=[])

        elif event == "-TABLE-":
            data_selected = values[event]
            if len(data_selected) > 0:
                window["-EDIT_DEVICE-"].Update(visible=True)
                window["-REMOVE_DEVICE-"].Update(visible=True)

        elif any(["+-double click-" in event, "-EDIT_DEVICE-" in event]):
            deviceId = values["-TABLE-"]
            if len(deviceId) > 0:
                editDevice_popup(deviceId[0])
                window["-EDIT_DEVICE-"].Update(visible=False)
                window["-REMOVE_DEVICE-"].Update(visible=False)
                window["-TABLE-"].Update(values=devices.toList())

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

        elif event == "-REMOVE_DEVICE-":
            if (
                sg.popup_ok_cancel(
                    "This will remove " + devices.list[values["-TABLE-"][0]].name + " !"
                )
                == "OK"
            ):
                devices.list.remove(devices.list[values["-TABLE-"][0]])
                devices.updateJson()
                window["-TABLE-"].Update(values=devices.toList())

            else:
                next

        elif event == "-START-":
            print("Starting View")
            devices.list = deviceListFromjson
            window["-TABLE-"].Update(values=devices.toList())

        if newDevice == True:
            connectToNewDevice()


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
    newDevice = False


# Create the USBMonitor instance
monitor = USBMonitor()

# Start the daemon
monitor.start_monitoring(on_connect=on_connect, on_disconnect=on_disconnect)

# ... Rest of your code ...
settings_screen()

# If you don't need it anymore stop the daemon
monitor.stop_monitoring()
