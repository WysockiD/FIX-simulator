# main.py
import click
from src.fix_sim import fix_simulator
from src.fix_client import market_sim_client

@click.group()
def cli():
    """
    FIX Simulator and Client Control Plane.
    
    This tool allows you to run a configurable FIX protocol simulator
    and a dynamic market simulation client for testing trading systems.
    """
    pass

@cli.command()
@click.option('--persona', default='Fast_ECN', help='The LP persona to use from config.yaml.')
@click.option('--host', default='localhost', help='The host address to bind the server to.')
@click.option('--port', default=9898, type=int, help='The port to run the server on.')
def sim(persona, host, port):
    """
    Run the FIX Simulator Server.
    
    It will use the specified LP persona for its behavior.
    Example: python main.py sim --persona Slow_Aggregator
    """
    click.echo(f"Starting FIX Simulator with persona: {persona} on {host}:{port}...")
    try:
        fix_simulator.run_server(persona, host, port)
    except Exception as e:
        click.echo(f"An error occurred: {e}", err=True)


@cli.command()
@click.option('--fix-version', default='4.2', help='The FIX protocol version to use (e.g., 4.2, 4.4).')
@click.option('--host', default='localhost', help='The host address of the simulator to connect to.')
@click.option('--port', default=9898, type=int, help='The port of the simulator.')
def client(fix_version, host, port):
    """
    Run the Dynamic Market Simulation Client.
    
    This client will connect to the simulator and perform a series of
    dynamic actions like sending, cancelling, and modifying orders.
    Example: python main.py client --fix-version 4.4
    """
    click.echo(f"Starting Market Sim Client for FIX.{fix_version} connecting to {host}:{port}...")
    try:
        # Construct the BeginString from the version
        begin_string = f"FIX.{fix_version.replace('.', '')}".encode()
        market_sim_client.run_client(host, port, begin_string)
    except Exception as e:
        click.echo(f"An error occurred: {e}", err=True)

if __name__ == '__main__':
    cli()