import serial
from serial import Serial
import serial.tools.list_ports as lp


def get_serial_ports() -> list[Serial]:
    """List all available serial ports on the system. Should work on all
    plattforms.
    on Linux: To read be able to read and write to serial ports,
    you need admin privileges"""

    ports = lp.comports()

    serial_ports = []

    for p in ports:
        try:
            sp = Serial(p.device)
            serial_ports.append(sp)
        except ValueError as e:
            print(p.device, e)
        except serial.SerialException as _:
            pass
        except:
            print("unknown exception when looking for serial ports")

    return serial_ports


def print_ports(ports: list[Serial]):
    """Enumerate all available ports and print to the console"""
    for i, port in enumerate(ports):
        print(f"[{i + 1}] {port.port}")


def user_input_serial_port() -> Serial:
    """let the user choose one of the available serial ports"""
    ports: list[Serial] = get_serial_ports()
    if len(ports) == 0:
        text = "no port was found. Check if you have permission to access the port"
        raise Exception(text) 

    print("Choose one of the following ports:\n")
    print_ports(ports)
    while True:
        try:
            i = int(input(""))
        except ValueError:
            print("you have to enter an index")
            continue

        if i < 1 or i > len(ports):
            print("invalid index")
            continue

        return ports[i - 1]
