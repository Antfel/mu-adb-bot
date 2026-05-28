import sys

from core.device_manager import list_adb_devices
from states.elf_buff_state import go_to_elf_buff_and_return


def main():
    devices = list_adb_devices()
    if not devices:
        print("[ADB] No devices available", file=sys.stderr)
        sys.exit(1)

    device_id = devices[0]
    success = go_to_elf_buff_and_return(device_id)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
