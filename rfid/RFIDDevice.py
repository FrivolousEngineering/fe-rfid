from typing import List, Callable

import serial
import logging
import threading
import time

from serial.serialutil import SerialException


class RFIDDevice:
    def __init__(self, port: str, baud_rate: int,
                 on_card_detected_callback: Callable[[str, str], None],
                 on_card_lost_callback: Callable[[str, str], None],
                 traits_detected_callback: Callable[[str, List[str]], None]):
        """
        A handler for a single USB port for an RFID krystalium card reader.
        It will emit signals when a card is found, when it is lost and its traits have been read
        :param port: The USB port this device is listening to
        :param baud_rate: The baudrate it's using
        :param on_card_detected_callback: Callback for when card is detected. First param is name of this reader, second is cardID
        :param on_card_lost_callback: Callback for when card is lost. First param is name of this reader, second is cardID
        :param traits_detected_callback: Callback for traits detected by the card. First param is name of reader, second is lost of strings of detected traits
        """
        self._port = port
        self._baud_rate = baud_rate
        self._serial = None
        self.name = None
        self._on_card_detected_callback = on_card_detected_callback
        self._on_card_lost_callback = on_card_lost_callback
        self._traits_detected_callback = traits_detected_callback
        self._detected_card = None
        self._detected_traits = None
        self._delayed_emit = False  # If a card was detected before a name, we delay the callback
        self._request_trait_info = False  # Should we re-request trait info?
        self._writing = False
        self._listen_thread = threading.Thread(target=self._handleSerialListen, daemon=True)
        self._send_thread = threading.Thread(target=self._handleSerialSend, daemon=True)

        self._recreate_serial_timer = None
        self._serial_recreate_time = 5  # in seconds
        self.start()

    @property
    def ready(self) -> bool:
        return self._serial is not None and self.name is not None

    @property
    def card_id(self) -> str | None:
        return self._detected_card

    @property
    def traits(self) -> list[str] | None:
        return self._detected_traits

    @property
    def writing(self) -> bool:
        return self._writing

    def start(self) -> None:
        self._createSerial()

    def stop(self):
        self._serial = None
        if self._recreate_serial_timer:
            self._recreate_serial_timer.cancel()

    def set_name(self, name: str):
        if not self.ready:
            logging.warning(f"Device {self._port} not ready")

        self.sendRawCommand(f"NAME {name}")

    def writeSample(self, sample_type: str, traits: list[str]):
        if sample_type.upper() not in ("RAW", "REFINED", "BLOOD"):
            raise ValueError(f"Invalid type for sample: {sample_type}")

        match sample_type.upper():
            case "RAW":
                if len(traits) != 4:
                    raise ValueError("Incorrect traits for Raw sample")
            case "REFINED":
                if len(traits) != 5:
                    raise ValueError("Incorrect traits for Refined sample")
            case "BLOOD":
                if len(traits) != 3:
                    raise ValueError("Incorrect traits for Blood sample")
            case _: raise ValueError(f"Unrecognised sample type {sample_type}")

        self._writing = True
        command = f"WRITESAMPLE {sample_type.upper()} {" ".join(traits)}"
        self.sendRawCommand(command)
        self._request_trait_info = True

    def _startSerialThreads(self) -> None:
        self._listen_thread.start()
        self._send_thread.start()

    @staticmethod
    def _validateCardTraits(arguments: List[str]) -> bool:
        logging.info(f"Checking reader response {arguments}")

        # If we get "EMPTY" it means that they just got a weird tag with no traits
        # on it. We need to fix that
        if arguments[0] == "EMPTY":
            logging.warning(f"EMPTY TAG")
            return False

        if arguments[0] != "RAW" and arguments[0] != "REFINED" and arguments[0] != "BLOOD":
            logging.warning(f"INVALID TYPE: {arguments[0]}")
            return False

        # We send traits back in all caps, which serves as a rudimentary check
        # To see if the reading is correct
        if any(arg != arg.upper() for arg in arguments[1:]):
            logging.warning("Invalid response")
            return False
        return True

    def _createSerial(self) -> None:
        try:
            self._listen_thread.join()  # Ensure that previous thread has closed
            self._listen_thread = threading.Thread(target=self._handleSerialListen, daemon=True)
        except RuntimeError:
            # If the thread hasn't started before it will cause a runtime. Ignore that.
            pass

        try:
            self._send_thread.join()
            self._send_thread = threading.Thread(target=self._handleSerialSend, daemon=True)
        except RuntimeError:
            pass
        try:
            self._serial = serial.Serial(self._port, self._baud_rate, timeout=3)
        except SerialException:
            self._serial = None

        if self._serial is not None:
            # Call later
            threading.Timer(2, self._startSerialThreads).start()
        else:
            # Check again after a bit of time has passed
            self._recreate_serial_timer = threading.Timer(self._serial_recreate_time, self._createSerial)
            self._recreate_serial_timer.start()

    def sendRawCommand(self, command: str) -> bool:
        # TODO: add command validity checking.
        if self._serial:
            self._serial.write(b"\n")
            command += "\n"
            self._serial.write(command.encode('utf-8'))
            return True
        else:
            logging.error(f"Unable to write command '{command}' without serial connection")
            return False

    def _handleSerialSend(self):
        logging.info(f"Starting serial send thread for {self._port}")
        while self._serial:
            try:
                if self.name is None:
                    self.sendRawCommand("NAME")
                if self._request_trait_info:
                    self.sendRawCommand("READ ALL")
                    self._request_trait_info = False
                time.sleep(0.5)
            except serial.SerialException:
                self._recreateSerial()
            except Exception as e:
                logging.error(f"Serial send error on {self._port}: {e}")
                time.sleep(1)

    def _handleSerialListen(self):
        logging.info(f"Starting serial listen thread for {self._port}")
        while self._serial:
            try:
                line = self._serial.readline().decode("utf-8", errors = "ignore").strip()
                if line.startswith("Tag found:"):
                    response = line.replace("Tag found: ", "")
                    arguments = response.split(" ")
                    card_id = arguments[0]
                    self._detected_card = card_id
                    if self.name is not None:
                        self._on_card_detected_callback(self.name, card_id)
                    else:
                        logging.warning("Card was detected before a name was known, delaying callback")

                    if not self._validateCardTraits(arguments[1:]):
                        # TODO: Send read all command!
                        self._request_trait_info = True
                    else:
                        self._detected_traits = arguments[1:]
                        if self.name is not None:
                            self._traits_detected_callback(self.name, arguments[1:])
                        else:
                            self._delayed_emit = True
                            logging.warning("Card was detected before a name was known, delaying callback")
                elif line.startswith("Tag lost:"):
                    card_id = line.replace("Tag lost: ", "")
                    self._detected_card = None
                    self._delayed_emit = False
                    if self.name is not None:
                        self._on_card_lost_callback(self.name, card_id)
                    self._detected_traits = None
                elif line.startswith("Traits: "):
                    response = line.replace("Traits: ", "")
                    arguments = response.split(" ")
                    if self._validateCardTraits(arguments):
                        self._detected_traits = arguments[1:]
                        if self.name is not None:
                            self._traits_detected_callback(self.name, arguments)
                        else:
                            self._delayed_emit = True
                            logging.warning("Traits were detected before a name was known, delaying callback")
                    else:
                        logging.warning("READ ALL FAILED :(")
                elif line.startswith("Name:"):
                    self.name = line.replace("Name:", "").strip()
                    logging.info(f"Device {self._port} identified as {self.name}")
                    if self._delayed_emit:
                        self._delayed_emit = False
                        self._on_card_detected_callback(self.name, self._detected_card)
                        if self._detected_traits is not None:
                            self._traits_detected_callback(self.name, self._detected_traits)
                elif line == "Write complete!":
                    self._writing = False
                else:
                    print(line)
            except serial.SerialException:
                self._recreateSerial()
            except Exception as e:
                logging.exception(f"Serial listen error on {self._port}: {e}")
                time.sleep(1)

    def _recreateSerial(self):
        logging.warning("Previously working serial has stopped working, try to re-create!")
        self._serial = None
        self.name = None
        self._detected_card = None
        self._detected_traits = None
        # Try to re-create it after a few seconds
        self._recreate_serial_timer = threading.Timer(self._serial_recreate_time, self._createSerial)
        self._recreate_serial_timer.start()
