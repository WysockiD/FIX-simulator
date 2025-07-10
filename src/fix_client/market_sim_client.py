# src/fix_client/market_sim_client.py
import socket
import simplefix
import datetime as dt
import time
import uuid
import random


SENDER_COMP_ID = "BRIDGE"
TARGET_COMP_ID = "SIMULATOR"
SYMBOLS = ["EUR/USD", "GBP/USD", "USD/JPY", "AUD/USD", "USD/CAD"]

class Order:
    
    def __init__(self, cl_ord_id, symbol, side, qty, price):
        self.cl_ord_id = cl_ord_id
        self.symbol = symbol
        self.side = side
        self.qty = qty
        self.price = price
        self.order_id = None
        self.status = 'New'

class FixClient:
    def __init__(self, host, port, fix_version):
        self.host = host
        self.port = port
        self.fix_version = fix_version
        self.sock = None
        self.parser = simplefix.FixParser()
        self.is_connected = False
        self.is_logged_on = False
        self.open_orders = {}

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
        cl_ord_id = f"ORD_{str(uuid.uuid4())[:12]}"
        symbol = random.choice(SYMBOLS)
        side = random.choice(["1", "2"])
        qty = random.randint(1, 10) * 10000
        price = round(random.uniform(1.05, 1.25), 5)

        order = Order(cl_ord_id, symbol, side, qty, price)
        self.open_orders[cl_ord_id] = order
        print(f"--- Sending New Order {cl_ord_id} for {qty} {symbol} ---")

        order_msg = self.create_base_message("D")
        order_msg.append_pair(11, cl_ord_id)
        order_msg.append_pair(55, symbol)
        order_msg.append_pair(54, side)
        order_msg.append_pair(60, dt.datetime.utcnow().strftime("%Y%m%d-%H:%M:%S"))
        order_msg.append_pair(38, qty)
        order_msg.append_pair(40, "2")
        order_msg.append_pair(44, price)
        self.send_message(order_msg)

    def cancel_random_order(self):
        if not self.open_orders: return
        target_cl_ord_id = random.choice(list(self.open_orders.keys()))
        order = self.open_orders[target_cl_ord_id]
        
        print(f"--- Sending Cancel Request for {target_cl_ord_id} ---")
        
        cancel_msg = self.create_base_message("F")
        cancel_msg.append_pair(11, f"CNL_{str(uuid.uuid4())[:12]}")
        cancel_msg.append_pair(41, target_cl_ord_id)
        cancel_msg.append_pair(55, order.symbol)
        cancel_msg.append_pair(54, order.side)
        cancel_msg.append_pair(60, dt.datetime.utcnow().strftime("%Y%m%d-%H:%M:%S"))
        self.send_message(cancel_msg)

    def modify_random_order(self):
        if not self.open_orders: return
        target_cl_ord_id = random.choice(list(self.open_orders.keys()))
        order = self.open_orders[target_cl_ord_id]
        new_qty = max(1000, order.qty + random.randint(-5, 5) * 1000)

        print(f"--- Sending Modify Request for {target_cl_ord_id}, new qty {new_qty} ---")
        
        replace_msg = self.create_base_message("G")
        replace_msg.append_pair(11, f"MOD_{str(uuid.uuid4())[:12]}")
        replace_msg.append_pair(41, target_cl_ord_id)
        replace_msg.append_pair(55, order.symbol)
        replace_msg.append_pair(54, order.side)
        replace_msg.append_pair(60, dt.datetime.utcnow().strftime("%Y%m%d-%H:%M:%S"))
        replace_msg.append_pair(38, new_qty)
        replace_msg.append_pair(40, "2")
        self.send_message(replace_msg)
        
    def send_malformed_order(self):
        print("--- Sending Malformed Order (Missing Side) ---")
        order_msg = self.create_base_message("D")
        order_msg.append_pair(11, f"BAD_{str(uuid.uuid4())[:12]}")
        order_msg.append_pair(55, "EUR/USD")
        order_msg.append_pair(38, 10000)
        order_msg.append_pair(40, "2")
        self.send_message(order_msg)

    def send_message(self, msg):
        if not self.is_connected or self.sock is None:
            return
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
        
        elif msg_type == '8': # ExecutionReport
            orig_cl_ord_id = (msg.get(41) if 41 in msg else msg.get(11)).decode()

            if orig_cl_ord_id in self.open_orders:
                order_status = msg.get(39).decode()
                if order_status in ['2', '4', '8']:
                    print(f"--- Order {orig_cl_ord_id} is now closed. Removing from open orders. ---")
                    del self.open_orders[orig_cl_ord_id]
                elif order_status == '0' and 37 in msg: # New
                    self.open_orders[orig_cl_ord_id].order_id = msg.get(37).decode()
                elif order_status == '5': # Replaced
                    print(f"--- Order {orig_cl_ord_id} was successfully modified. ---")
                    self.open_orders[orig_cl_ord_id].status = 'Replaced'
            else:
                 print(f"--- Received ExecutionReport for an unknown or closed order {orig_cl_ord_id} ---")

    def disconnect(self):
        if self.sock: self.sock.close()
        self.is_connected=False; self.is_logged_on=False; self.sock=None
        print("Client disconnected.")

    def create_base_message(self, msg_type):
        msg = simplefix.FixMessage()
        msg.append_pair(8, self.fix_version)
        msg.append_pair(35, msg_type)
        msg.append_pair(49, SENDER_COMP_ID)
        msg.append_pair(56, TARGET_COMP_ID)
        msg.append_pair(34, 1, True)
        msg.append_pair(52, dt.datetime.utcnow().strftime("%Y%m%d-%H:%M:%S.%f")[:-3], True)
        return msg

    def run(self):
        last_action_time = 0
        while True:
            try:
                if not self.is_connected:
                    if self.connect():
                        last_action_time = time.time()
                    else:
                        time.sleep(5)
                    continue
                
                self.listen()

                if self.is_logged_on and (time.time() - last_action_time > random.uniform(1.0, 3.0)):
                    action = random.choices(['new', 'cancel', 'modify', 'bad_order'], weights=[45, 25, 25, 5], k=1)[0]
                    if action == 'new': self.send_order()
                    elif action == 'cancel' and self.open_orders: self.cancel_random_order()
                    elif action == 'modify' and self.open_orders: self.modify_random_order()
                    elif action == 'bad_order': self.send_malformed_order()
                    last_action_time = time.time()
                
                time.sleep(0.1)
            except KeyboardInterrupt:
                print("\nClient stopping...")
                self.disconnect()
                break


def run_client(host, port, fix_version):
    client = FixClient(host, port, fix_version)
    client.run()