import socketserver
import simplefix
import datetime as dt
import uuid
import time
import random
import yaml
import sys
import logging
import os
from .fix_protocol import FixProtocol

# --- Global Configuration ---
HOST, PORT = "localhost", 9898
LOG_FILE = "logs/fix_simulator.log"
CONFIG_FILE = "config/config.yaml"
DICT_PATH_PREFIX = "dict"

# --- Logging Setup ---
def setup_logging():
    """Configure and return the simulator logger."""
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

    logger = logging.getLogger("FIX_SIM")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not logger.handlers:
        file_handler = logging.FileHandler(LOG_FILE, mode='a')
        console_handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger

logger = setup_logging()

# --- Protocol Cache ---
PROTOCOL_CACHE = {}
def get_protocol(begin_string: str) -> FixProtocol:
    if begin_string in PROTOCOL_CACHE:
        return PROTOCOL_CACHE[begin_string]
    file_map = {"FIX.4.2": "FIX42.xml", "FIX.4.4": "FIX44.xml"}
    filename = file_map.get(begin_string)
    if not filename:
        raise ValueError(f"No dictionary found for BeginString {begin_string}")
    filepath = f"{DICT_PATH_PREFIX}/{filename}"
    protocol = FixProtocol(filepath)
    PROTOCOL_CACHE[begin_string] = protocol
    return protocol

# --- Simulator Logic ---
class FixSimulatorHandler(socketserver.BaseRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lp_settings = self.server.lp_settings
        self.protocol = None

    def handle(self):
        logger.info(f"Connection from {self.client_address}")
        self.parser = simplefix.FixParser()
        try:
            while True:
                data = self.request.recv(4096)
                if not data:
                    logger.warning(f"Client {self.client_address} disconnected.")
                    break
                self.parser.append_buffer(data)
                while True:
                    msg = self.parser.get_message()
                    if msg is None: break
                    self.process_fix_message(msg)
        except Exception as e:
            logger.error(f"Error on connection {self.client_address}: {e}")

    def process_fix_message(self, msg: simplefix.FixMessage):
        if self.protocol is None:
            if 35 not in msg or msg.get(35) != b'A':
                logger.error("First message was not a Logon. Closing connection.")
                self.request.close()
                return
            try:
                begin_string = msg.get(8).decode()
                self.protocol = get_protocol(begin_string)
                logger.info(f"Established protocol {begin_string} for session {self.client_address}")
            except Exception as e:
                logger.error(f"Failed to establish protocol: {e}. Closing connection.")
                self.request.close()
                return

        is_valid, reason = self.protocol.validate_message(msg)
        if not is_valid:
            logger.warning(f"Invalid message received: {reason}. Ignoring.")
            return

        log_msg_str = msg.encode().decode().replace('\x01', '|')
        logger.info(f"<<< RECV: {log_msg_str}")
        
        msg_type = msg.get(35).decode()
        if msg_type == 'A': self.handle_logon(msg)
        elif msg_type == 'D': self.handle_new_order_single(msg)
        elif msg_type == 'F': self.handle_cancel_request(msg)
        elif msg_type == 'G': self.handle_replace_request(msg)

    def handle_logon(self, msg: simplefix.FixMessage):
        response = self.create_base_message('A')
        response.append_pair(98, 0)
        response.append_pair(108, 30)
        self.send_message(response)
    
    def handle_new_order_single(self, order_msg: simplefix.FixMessage):
        cl_ord_id = order_msg.get(11)
        symbol = order_msg.get(55)
        side = order_msg.get(54)
        order_qty_int = int(order_msg.get(38))
        price = order_msg.get(44) if 44 in order_msg else b'1.2345'
        order_id = str(uuid.uuid4())[:8]

        self.send_message(self.create_execution_report(cl_ord_id, order_id, 0, 0, order_qty_int, 0.0, symbol, side))
        
        latency = self.lp_settings['avg_latency_ms'] + random.uniform(-self.lp_settings['latency_jitter_ms'], self.lp_settings['latency_jitter_ms'])
        time.sleep(max(0, latency / 1000))

        if random.random() < self.lp_settings['fill_rate']:
            if random.random() < self.lp_settings['partial_fill_rate'] and order_qty_int > 1:
                filled_qty = random.randint(1, order_qty_int-1)
                exec_report = self.create_execution_report(cl_ord_id, order_id, 1, 1, order_qty_int - filled_qty, float(price), symbol, side, filled_qty, float(price))
            else:
                exec_report = self.create_execution_report(cl_ord_id, order_id, 2, 2, 0, float(price), symbol, side, order_qty_int, float(price))
        else:
            exec_report = self.create_execution_report(cl_ord_id, order_id, 8, 8, order_qty_int, 0.0, symbol, side)

        self.send_message(exec_report)

    def handle_cancel_request(self, cancel_msg: simplefix.FixMessage):
        cl_ord_id = cancel_msg.get(11)
        orig_cl_ord_id = cancel_msg.get(41).decode()
        logger.info(f"Processing Cancel Request for OrigClOrdID: {orig_cl_ord_id}")
        order_id = str(uuid.uuid4())[:8] 
        exec_report = self.create_execution_report(
            cl_ord_id, order_id, 4, 4, 0, 0.0,
            cancel_msg.get(55), cancel_msg.get(54), cum_qty=0
        )
        exec_report.append_pair(41, orig_cl_ord_id)
        self.send_message(exec_report)
    
    def handle_replace_request(self, replace_msg: simplefix.FixMessage):
        cl_ord_id = replace_msg.get(11)
        orig_cl_ord_id = replace_msg.get(41).decode()
        new_qty = int(replace_msg.get(38))
        logger.info(f"Processing Replace Request for OrigClOrdID: {orig_cl_ord_id}")
        order_id = str(uuid.uuid4())[:8]
        exec_report = self.create_execution_report(
            cl_ord_id, order_id, 5, 0, new_qty, 0.0,
            replace_msg.get(55), replace_msg.get(54), cum_qty=0
        )
        exec_report.append_pair(41, orig_cl_ord_id)
        self.send_message(exec_report)

    def send_message(self, msg: simplefix.FixMessage):
        log_msg_str = msg.encode().decode().replace('\x01', '|')
        logger.info(f">>> SEND: {log_msg_str}")
        self.request.sendall(msg.encode())
        
    def create_base_message(self, msg_type: str) -> simplefix.FixMessage:
        msg = simplefix.FixMessage()
        begin_string_str = self.protocol.path.split('/')[-1].replace('.xml', '')
        if begin_string_str.startswith("FIX") and len(begin_string_str) == 5:
            begin_string_str = f"{begin_string_str[:3]}.{begin_string_str[3]}.{begin_string_str[4]}"
        msg.append_pair(8, begin_string_str.encode())
        msg.append_pair(35, msg_type)
        msg.append_pair(49, "SIMULATOR")
        msg.append_pair(56, "BRIDGE")
        msg.append_pair(34, 1, True)
        msg.append_pair(52, dt.datetime.utcnow().strftime("%Y%m%d-%H:%M:%S.%f")[:-3], True)
        return msg

    def create_execution_report(self, cl_ord_id, order_id, exec_type, ord_status, leaves_qty, avg_px, symbol, side, cum_qty=0, last_px=0.0):
        report = self.create_base_message('8')
        report.append_pair(17, str(uuid.uuid4())[:8]); report.append_pair(11, cl_ord_id); report.append_pair(37, order_id)
        report.append_pair(150, exec_type); report.append_pair(39, ord_status); report.append_pair(55, symbol)
        report.append_pair(54, side); report.append_pair(151, leaves_qty); report.append_pair(14, cum_qty); report.append_pair(6, avg_px)
        if exec_type in (1, 2):
            report.append_pair(32, cum_qty)
            report.append_pair(31, last_px)
        return report


def run_server(persona, host, port, custom_dict_path=None):
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = yaml.safe_load(f)
        lp_settings = config['lps'][persona]
        logger.info(f"Loaded config. Running as LP Persona: '{persona}'")
    except Exception as e:
        logger.critical(f"Failed to load persona '{persona}': {e}")
        return

    class FixTCPServer(socketserver.TCPServer):
        def __init__(self, server_address, RequestHandlerClass):
            self.lp_settings = lp_settings
            # We don't actually need custom_dict_path here anymore as it's not used by the handler
            super().__init__(server_address, RequestHandlerClass)
    
    server = None
    try:
        server = FixTCPServer((host, port), FixSimulatorHandler)
        logger.info(f"FIX Simulator started on {host}:{port}. Press Ctrl+C to stop.")
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Simulator stopping...")
    except Exception as e:
        logger.critical(f"Failed to start the server: {e}", exc_info=True)
    finally:
        if server:
            server.shutdown()
            logger.info("Simulator stopped.")