import multiprocessing
import os
import queue
import signal
import sys
import threading
import wave
from datetime import datetime

import grpc
import pyaudio
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QColor, QPainter, QPalette, QPen, QPolygon
from PyQt6.QtWidgets import QApplication, QLabel, QLineEdit, QPushButton, QWidget

import comms_pb2, comms_pb2_grpc
from audio import OpusCoder, play_wav

DEVICE_ID = "test_client"

STREAMS = [
    "status",
    "event",
    "server_audio",
]


# This helper function turns a queue into a generator, which the gRPC client library expects
def message_generator(message_queue):
    while True:
        message = message_queue.get()  # This blocks until a message is available
        print(f"Client: Sending a response of type {type(message)}")
        print("Client: Waiting for next request")
        yield message


# Add signal handler before the App class
def signal_handler(signum, frame):
    """Handle Ctrl+C by closing the application"""
    QApplication.quit()


class Shape(QWidget):
    def __init__(self, parent, shape_type, x, y, size, color):
        super().__init__(parent)
        self.shape_type = shape_type
        self.setGeometry(x, y, size, size)
        self.color = QColor(color)
        self.size = size

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Set the color and pen
        painter.setBrush(self.color)
        painter.setPen(QPen(self.color, 2, Qt.PenStyle.SolidLine))

        if self.shape_type == "circle":
            painter.drawEllipse(0, 0, self.size, self.size)

        elif self.shape_type == "square":
            painter.drawRect(0, 0, self.size, self.size)

        elif self.shape_type == "triangle":
            points = [QPoint(self.size // 2, 0), QPoint(0, self.size), QPoint(self.size, self.size)]
            painter.drawPolygon(QPolygon(points))

        elif self.shape_type == "rhomboid":
            offset = self.size // 2
            points = [QPoint(offset, 0), QPoint(self.size, offset), QPoint(offset, self.size), QPoint(0, offset)]
            painter.drawPolygon(QPolygon(points))


class App(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.running_threads = []
        self.active_rpcs = []
        # Comms
        self.event_queue = multiprocessing.Queue()
        self.event_thread = None
        self.status_thread = None
        self.channel = None
        self.mode = 0

        # Add audio recording setup
        self.audio = pyaudio.PyAudio()
        self.recording = False
        self.audio_frames = []
        self.stream = None
        # Create recordings directory if it doesn't exist
        os.makedirs("audio_recordings/client", exist_ok=True)

    def initUI(self):
        # Set white background
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor("white"))
        self.setPalette(palette)

        # Add background image that fills the window
        background_label = QLabel(self)
        background_label.setStyleSheet("background-color: gray;")
        background_label.setGeometry(0, 0, 600, 800)
        background_label.setScaledContents(True)

        # Create and position buttons with specific coordinates
        # Format: setGeometry(x, y, width, height)

        # Power button
        power_button = QPushButton("Connect", self)
        power_button.setGeometry(495, 312, 72, 48)
        power_button.clicked.connect(self.handle_power_click)
        

        # Square button: stop and go home
        button2 = QPushButton("Stop", self)
        button2.setGeometry(227, 312, 48, 48)
        button2.clicked.connect(self.handle_stop_click)

        # Mode select button
        button3 = QPushButton("Mode", self)
        button3.setGeometry(63, 312, 48, 48)  # Left side button
        button3.clicked.connect(self.handle_mode_click)

        # Play
        button4 = QPushButton("Play", self)
        button4.setGeometry(145, 312, 48, 48)  # Right side button
        button4.clicked.connect(lambda: self.event_queue.put({"button_id": comms_pb2.ButtonEvent.ButtonId.BUTTON_4}))

        # Device ID input
        # Add label above device ID input
        message = "Enter the device_id you'll provide to the server\n"
        message += "Click the Connect button to connect to the server"
        device_id_label = QLabel(
            message,
            self,
        )
        device_id_label.setGeometry(150, 120, 300, 100)
        device_id_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.device_id_input = QLineEdit(self)
        self.device_id_input.setGeometry(200, 100, 200, 30)
        self.device_id_input.setPlaceholderText("Enter Device ID")
        self.device_id_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.device_id_input.setText(DEVICE_ID)
        self.device_id_input.setStyleSheet("background-color: #E0E0E0; border: 1px solid #CCCCCC;")

        # Window properties
        self.setWindowTitle("Client")
        self.setGeometry(100, 50, 600, 400)

        # Add LEDs. Shapes are for mode
        self.led_0 = Shape(self, "circle", 60, 235, 16, "#000000")  # Power
        self.led_1 = Shape(self, "circle", 100, 235, 16, "#000000")  # Server status
        self.square = Shape(self, "square", 163, 235, 18, "#000000")  # Led 2
        self.rhomboid = Shape(self, "rhomboid", 200, 235, 18, "#000000")  # Led 3
        self.triangle = Shape(self, "triangle", 236, 235, 18, "#000000")  # Led 4
        self.circle = Shape(self, "circle", 269, 235, 18, "#000000")  # Led 5

    def closeEvent(self, event):
        """Handle cleanup when the window is closed"""
        if self.channel:
            self.channel.close()
        if self.event_thread:
            self.event_thread.join(timeout=1.0)
        if self.status_thread:
            self.status_thread.join(timeout=1.0)
        if self.server_audio_thread:
            self.server_audio_thread.join(timeout=1.0)
        event.accept()

    def handle_stop_click(self):
        # Turn off all mode LEDs
        self.event_queue.put({"button_id": comms_pb2.ButtonEvent.ButtonId.BUTTON_3})

    def handle_mode_click(self):
        self.event_queue.put({"button_id": comms_pb2.ButtonEvent.ButtonId.BUTTON_2})

    def handle_power_click(self):
        # If on, turn off and close connection
        if self.channel:
            # Terminate all RPCs
            for rpc in self.active_rpcs:
                rpc.cancel()
            self.active_rpcs = []
            print("Cancelled all RPCs")

            # Close GRPC channel
            self.channel.close()
            self.channel = None
            print("Closed GRPC channel")

            # Join all threads
            self.event_queue.put(None)
            for thread in self.running_threads:
                thread.join()
            self.running_threads = []
            print("Joined all threads")

            # Turn off all LEDs
            self.led_0.color = QColor("black")
            self.led_0.update()
            self.led_1.color = QColor("black")
            self.led_1.update()
        else:
            # Start new connection
            self.setup_client(self.device_id_input.text())
            self.led_0.color = QColor("white")
            self.led_0.update()

    def handle_status_response(self, response):
        if response.get:
            print("Received Status GET request")
            device_state = comms_pb2.DeviceStatus(
                led_0=comms_pb2.RGBAColor(rgba=((self.led_0.color.rgb() << 8) | 0xFF) & 0xFFFFFFFF),
                led_1=comms_pb2.RGBAColor(rgba=((self.led_1.color.rgb() << 8) | 0xFF) & 0xFFFFFFFF),
                led_2=comms_pb2.RGBAColor(rgba=((self.square.color.rgb() << 8) | 0xFF) & 0xFFFFFFFF),
                led_3=comms_pb2.RGBAColor(rgba=((self.rhomboid.color.rgb() << 8) | 0xFF) & 0xFFFFFFFF),
                led_4=comms_pb2.RGBAColor(rgba=((self.triangle.color.rgb() << 8) | 0xFF) & 0xFFFFFFFF),
                led_5=comms_pb2.RGBAColor(rgba=((self.circle.color.rgb() << 8) | 0xFF) & 0xFFFFFFFF),
            )
            status_message = comms_pb2.DeviceStatusResponse(state=device_state)
        elif response.set:
            print("Received Status SET request.")
            # Shifting colors by 8 bits to go from RGBA to RGB
            # Ignore Led 0, it is the CONNECT LED
            # if response.set.led_0:
            #     color = response.set.led_0.rgba >> 8
            #     self.led_0.color = QColor(color)
            #     self.led_0.update()
            if response.set.led_1:
                color = response.set.led_1.rgba >> 8
                self.led_1.color = QColor(color)
                self.led_1.update()
            if response.set.led_2:
                color = response.set.led_2.rgba >> 8
                self.square.color = QColor(color)
                self.square.update()
            if response.set.led_3:
                color = response.set.led_3.rgba >> 8
                self.rhomboid.color = QColor(color)
                self.rhomboid.update()
            if response.set.led_4:
                color = response.set.led_4.rgba >> 8
                self.triangle.color = QColor(color)
                self.triangle.update()
            if response.set.led_5:
                color = response.set.led_5.rgba >> 8
                self.circle.color = QColor(color)
                self.circle.update()
            status_message = comms_pb2.DeviceStatusResponse(status="success")
        else:
            status_message = comms_pb2.DeviceStatusResponse(status="error")
        return status_message

    def setup_client(self, device_id):
        self.channel = grpc.insecure_channel(f"localhost:50051")

        stub = comms_pb2_grpc.DeviceServiceStub(self.channel)
        metadata = [("device_id", device_id)]
        # Create queues to store messages which will be sent to the server
        status_message_queue = queue.Queue()
        event_message_queue = queue.Queue()

        # Start streaming connection with server
        if "status" in STREAMS:
            status_response_generator = stub.StatusStream(message_generator(status_message_queue), metadata=metadata)
            self.active_rpcs.append(status_response_generator)
        if "event" in STREAMS:
            event_response_generator = stub.EventStream(message_generator(event_message_queue), metadata=metadata)
            self.active_rpcs.append(event_response_generator)
        if "server_audio" in STREAMS:
            server_audio_packet_generator = stub.ServerAudioStream(
                comms_pb2.AudioStreamRequest(start=True), metadata=metadata
            )
            self.active_rpcs.append(server_audio_packet_generator)

        def event_loop(event_queue):
            try:
                while True:
                    button_event = event_queue.get()
                    if button_event is None:
                        break
                    if "button_id" in button_event:
                        event_message = comms_pb2.DeviceEvent(
                            button_event=comms_pb2.ButtonEvent(
                                button_id=button_event["button_id"],
                                event=comms_pb2.ButtonEvent.ButtonEventType.PRESS,
                            )
                        )
                    else:
                        print("Unknown event type:", button_event)
                        continue
                    event_message_queue.put(event_message)
                    server_response = next(event_response_generator)
                    print("Event loop received:", server_response)
            except grpc.RpcError as e:
                print(f"RPC error in event loop: {e}")
            except Exception as e:
                print(f"Error in event loop: {e}")

        def status_loop():
            try:
                for response in status_response_generator:
                    print("Status loop received:", response)
                    status_message = self.handle_status_response(response)
                    status_message_queue.put(status_message)
            except grpc.RpcError as e:
                print(f"RPC error in status loop: {e}")
            except Exception as e:
                print(f"Error in status loop: {e}")

        def server_audio_loop():
            opus_coder = OpusCoder(sample_rate=48000, channels=1)
            try:
                f = None
                num_packets = 0
                for audio_packet in server_audio_packet_generator:
                    print(
                        "Server audio packet received: is_start",
                        audio_packet.is_start,
                        "is_end",
                        audio_packet.is_end,
                        "num_packets",
                        num_packets,
                    )
                    if audio_packet.is_start:
                        filename = f"audio_recordings/client/recording_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
                        if f:
                            f.close()
                        f = wave.open(filename, "wb")
                        f.setnchannels(1)
                        f.setframerate(48000)
                        f.setsampwidth(2)

                    if f:
                        f.writeframes(opus_coder.decode(bytearray(audio_packet.data)))

                    if audio_packet.is_end:
                        f.close()
                        f = None
                        print(f"Recording saved to {filename}")
                        play_wav(filename)
                        num_packets = 0
                    num_packets += 1

            except grpc.RpcError as e:
                print(f"RPC error in server audio loop: {e}")
            except Exception as e:
                print(f"Error in server audio loop: {e}")


        # Create and start daemon threads
        self.status_thread = threading.Thread(target=status_loop, daemon=True)
        self.event_thread = threading.Thread(target=event_loop, args=(self.event_queue,), daemon=True)
        self.server_audio_thread = threading.Thread(target=server_audio_loop, daemon=True)
        if "status" in STREAMS:
            self.status_thread.start()
            self.running_threads.append(self.status_thread)
        if "event" in STREAMS:
            self.event_thread.start()
            self.running_threads.append(self.event_thread)
        if "server_audio" in STREAMS:
            self.server_audio_thread.start()
            self.running_threads.append(self.server_audio_thread)


if __name__ == "__main__":
    # Set up signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    app = QApplication(sys.argv)
    # Enable Ctrl+C handling in the Qt event loop
    timer = app.startTimer(500)  # Small timer to process Python events
    window = App()
    window.show()
    sys.exit(app.exec())
