import re
import json
import subprocess
import time

import adbutils  # pip install adbutils
from pynput.keyboard import Key, Listener  # pip install pynput
from screeninfo import get_monitors  # pip install screeninfo
from argparse import ArgumentParser

adb = adbutils.AdbClient(host="127.0.0.1", port=5037)
lastkey = None

fps = "30"
bitrate = "1M"
windowsPerLine = 3
windowLines = 3

monitor = ""
for m in get_monitors():
    if m.is_primary:
        monitor = m
        print("Using " + str(monitor))

captureWidth = int(monitor.width / windowsPerLine)
captureHeight = int(monitor.height / windowLines)

cropWidth = 1600
cropXOffset = 75
cropYOffset = 450

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

f = open("headsets.json")
JsonDevices = json.load(f)

AdbDevices = []


def on_press(key):
    global lastkey
    lastkey = key


def on_release(key):
    global lastkey
    lastkey = None


listener = Listener(on_press=on_press, on_release=on_release)
listener.start()


class AdbDevice:
    name = ""
    serial = ""
    ip = ""
    mac = ""
    xposition = 0
    yposition = 0
    scrspyproc = None
    id = int(-1)

    def startScrCpy(self):
        self.scrspyproc = subprocess.Popen(
            ".\scrcpy\scrcpy.exe -n --window-borderless --no-audio --video-codec=h265 --crop "
            + crop
            + " --max-fps="
            + fps
            + " -b "
            + bitrate
            + " -s "
            + self.serial
            + " --max-size "
            + str(captureWidth)
            + " --window-x="
            + str(self.xposition)
            + " --window-y="
            + str(self.yposition)
            + " --window-title="
            + self.name
        )
        time.sleep(0.5)

    def __init__(self, serial, wlan):
        self.serial = serial
        self.ip = re.search("inet ((\d{1,3}\.){3}\d{1,3})", wlan)
        self.mac = re.search("link/ether ..:..:..:..:..:..", wlan)

        if self.ip is not None:
            self.ip = self.ip.group().replace("inet ", "")
            self.mac = self.mac.group().replace("link/ether ", "")

            for i in JsonDevices["headsets"]:
                if self.mac == str(i["mac"]).lower():
                    self.id = i["id"]
                    self.name = i["name"]
                    i["ip"] = self.ip

                    xindex = int(captureWidth) * self.id
                    self.xposition = str(xindex % monitor.width)
                    self.yposition = str(
                        max(0, int(self.id / windowsPerLine)) * int(monitor.height / 3)
                    )

                    AdbDevices.append(self)

                    print(
                        "Added "
                        + self.name
                        + " (id:"
                        + str(self.id)
                        + ") with mac adress "
                        + self.mac
                        + ", and ip adress "
                        + self.ip
                    )
                    return
            print(
                "Device "
                + self.serial
                + " with mac adress "
                + self.mac
                + ", and ip adress "
                + self.ip
                + " isn't a known device !"
            )
        else:
            print("Added " + self.serial + ", but it is not connected to wifi !")


def connectToNewHeadsets():
    currentdevices = [""]

    global lastkey
    while lastkey == None:
        devices = adb.device_list()

        for device in devices:
            serial = device.serial
            ip = device.wlan_ip()
            if not ip in currentdevices:
                if ip not in serial:
                    device.tcpip(port=5555)
                    adb.connect(addr=ip, timeout=5)
                    serial = device.serial

                if ip in serial:
                    wlan = device.shell("ip addr show wlan0")
                    AdbDevice(serial=serial, wlan=wlan)

                    currentdevices.append(ip)
    updateIpAdresses()


def disconnectAll():
    for device in adb.device_list():
        adb.disconnect(addr=device.serial)
        print("Disconnected " + device.serial)

    for device in JsonDevices["headsets"]:
        device["ip"] = ""

    updateIpAdresses()


def reconnectToLastIp():
    print("\nConnecting to last known ips...")
    for i in JsonDevices["headsets"]:
        if i["ip"] != "":
            print("Connecting to " + i["name"] + " (" + i["ip"] + ")")
            try:
                adb.connect(addr=i["ip"], timeout=5)
            except:
                print("Couldn't reach " + i["name"])
                pass

    print("Done !\n")

    if len(adb.device_list()) == 0:
        print("No devices found.")


def updateIpAdresses():
    json_object = json.dumps(JsonDevices, indent=4)
    with open("headsets.json", "w") as outfile:
        outfile.write(json_object)


def startScrcpy():
    for device in AdbDevices:
        device.startScrCpy()
        time.sleep(1)


def stopScrcpy():
    for device in AdbDevices:
        device.scrspyproc.kill()


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument(
        "-r",
        "--reconnect",
        action="store_true",
        default=False,
        help="reconnect to last known ip of headsets",
    )

    parser.add_argument(
        "-d",
        "--disconnect",
        action="store_true",
        default=False,
        help="disconnect all devices",
    )

    args = parser.parse_args()

    if args.disconnect:
        disconnectAll()
        exit(0)

    if args.reconnect or len(adb.device_list()) == 0:
        reconnectToLastIp()

    connectToNewHeadsets()

    startScrcpy()
    while lastkey != Key.esc:
        pass
    stopScrcpy()
