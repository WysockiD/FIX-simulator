# FIX Protocol Simulator & Test Environment

This project provides a configurable FIX protocol simulator and a dynamic testing client. It is designed to test the robustness, performance, and correctness of a trading bridge or FIX engine.

The simulator is dictionary-driven, allowing it to adapt to different FIX versions and custom counterparty specifications without code changes.

## Prerequisites

1.  Python 3.9+
2.  All required Python packages, which can be installed via:
    ```bash
    pip install -r requirements.txt
    ```

## Quick Start

1.  **Start the Simulator:** Open a terminal and run the following command. This will start the simulator using the default `Fast_ECN` persona defined in `config/config.yaml`.

    ```bash
    python main.py sim
    ```

2.  **Start the Dynamic Client:** Open a *second* terminal and run the client. It will connect to the running simulator and begin a dynamic sequence of trading actions.

    ```bash
    python main.py client
    ```

You will see log output in both terminals as the client and server interact. To stop the programs, press `Ctrl+C` in each terminal.

## Usage

The tool is controlled via the `main.py` entry point.

### Running the Simulator

The `sim` command starts the FIX simulator server.

**Command:**
`python main.py sim [OPTIONS]`

**Options:**
*   `--persona TEXT` The LP persona to use from `config/config.yaml`. Defaults to `Fast_ECN`.
*   `--host TEXT` The host address to bind to. Defaults to `localhost`.
*   `--port INTEGER` The port to listen on. Defaults to `9898`.

**Example:** Run the simulator as a slow, bank-like LP.
```bash
python main.py sim --persona Standard_Bank
```

### Running the Client

The `client` command starts the dynamic market simulation client.

**Command:**
`python main.py client [OPTIONS]`

**Options:**
*   `--fix-version TEXT` The FIX protocol version to use for the `BeginString(8)` tag. Must match a dictionary file in the `dict/` folder (e.g., 4.2 -> FIX.4.2). Defaults to `4.2`.
*   `--host TEXT` The host address of the simulator. Defaults to `localhost`.
*   `--port INTEGER` The port of the simulator. Defaults to `9898`.

**Example:** Run the client speaking the FIX 4.4 protocol.
```bash
python main.py client --fix-version 4.4
```

## Configuration

### LP Personas

The behavior of the simulator (latency, fill rates, etc.) is controlled by "LP Personas" defined in `config/config.yaml`. You can add new personas or modify existing ones to simulate different counterparty conditions.

### FIX Dictionaries

The simulator validates incoming messages based on XML dictionary files located in the `dict/` directory. It dynamically chooses the dictionary based on the `BeginString(8)` tag in a client's `Logon(A)` message.

To support a new FIX version or a counterparty's custom specification:
1.  Create a new XML file (e.g., `LP_XYZ_FIX42.xml`) in the `dict/` folder.
2.  Define the required fields and messages according to the counterparty's spec.
3.  The client can then connect using the corresponding `BeginString`. The simulator does not need to be modified.

## Logging

All simulator activity is logged to `logs/fix_simulator.log`. This includes connections, disconnections, errors, and every raw FIX message sent and received.
