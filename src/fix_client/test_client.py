# src/fix_client/test_client.py
import socket
import simplefix
import datetime as dt
import time
import uuid


HOST, PORT = "localhost", 9898
SENDER_COMP_ID = "BRIDGE"
TARGET_COMP_ID = "SIMULATOR"
FIX_VERSION = b"FIX.4.2" 

class FixClient:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.sock = None
        self.parser = simplefix.FixParser()
        self.is_connected = False
        self.is_logged_on = False

    def connect(self):
        try:
            print(f"[{dt.datetime.now()}] Attempting to connect to {self.host}:{self.port}...")
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.host, self.port))
            self.sock.setblocking(False) 
            self.is_connected = True
            print(f"[{dt.datetime.now()}] Connection established. Sending Logon.")
            self.send_logon()
            return True
        except (ConnectionRefusedError, TimeoutError) as e:
            self.is_connected = False
            self.sock = None
            print(f"[{dt.datetime.now()}] Connection failed: {e}")
            return False

    def send_logon(self):
        logon_msg = self.create_base_message("A")
        logon_msg.append_pair(98, 0)
        logon_msg.append_pair(108, 30)
        self.send_message(logon_msg)

    def send_order(self):
        if not self.is_logged_on:
            return
        order_msg = self.create_base_message("D")
        order_msg.append_pair(11, f"ORD_{str(uuid.uuid4())[:8]}")
        order_msg.append_pair(55, "EUR/USD")
        order_msg.append_pair(54, "1")
        order_msg.append_pair(60, dt.datetime.utcnow().strftime("%Y%m%d-%H:%M:%S"), True)
        order_msg.append_pair(38, 10000)
        order_msg.append_pair(40, "2")
        order_msg.append_pair(44, "1.0950")
        self.send_message(order_msg)

    def send_message(self, msg):
        if not self.is_connected or self.sock is None: return
        print(f">>> Sending MsgType={msg.get(35).decode()}")
        try:
            self.sock.sendall(msg.encode())
        except (BrokenPipeError, ConnectionResetError) as e:
            print(f"Connection lost while sending: {e}")
            self.disconnect()

    def listen(self):
        if not self.is_connected or self.sock is None: return
        try:
            data = self.sock.recv(4096)
            if not data:
                print("Server disconnected.")
                self.disconnect()
                return
            
            self.parser.append_buffer(data)
            while True:
                msg = self.parser.get_message()
                if msg is None: break
                self.handle_message(msg)
        except BlockingIOError:
            pass
        except (BrokenPipeError, ConnectionResetError, OSError) as e:
            print(f"Connection lost while listening: {e}")
            self.disconnect()

    def handle_message(self, msg):
        msg_type = msg.get(35).decode()
        print(f"<<< Received MsgType={msg_type}")
        if msg_type == 'A':
            print("Logon successful!")
            self.is_logged_on = True

    def disconnect(self):
        if self.sock:
            self.sock.close()
        self.is_connected = False
        self.is_logged_on = False
        self.sock = None
        print("Client disconnected.")

    def create_base_message(self, msg_type):
        msg = simplefix.FixMessage()
        msg.append_pair(8, FIX_VERSION)
        msg.append_pair(35, msg_type)
        msg.append_pair(49, SENDER_COMP_ID)
        msg.append_pair(56, TARGET_COMP_ID)
        msg.append_pair(34, 1, True)
        msg.append_pair(52, dt.datetime.utcnow().strftime("%Y%m%d-%H:%M:%S.%f")[:-3], True)
        return msg

    def run(self):
        last_order_time = 0
        while True:
            if not self.is_connected:
                if self.connect():
                    last_order_time = time.time()
                else:
                    time.sleep(5)
                continue
            
            self.listen()

            if self.is_logged_on and (time.time() - last_order_time > 5):
                print("\n--- Sending a new test order ---")
                self.send_order()
                last_order_time = time.time()
            
            time.sleep(0.1)

if __name__ == "__main__":
    client = FixClient(HOST, PORT)
    client.run()