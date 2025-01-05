#!/usr/bin/env python3

"""Run the printer simulator."""

import socket
import sys
import threading
import time
import uuid
from hashlib import sha512

from snmpsim.commands.responder import main as snmpsim_main
from zeroconf import InterfaceChoice, ServiceInfo, Zeroconf

PRINTER_IP = "127.0.0.1"
PDL_DATASTREAM_PORT = 9100
SNMP_PORT = 1161

PDL_BUF_SIZE = 1024


class PdlDsStreamServer(threading.Thread):
    """A single threaded blocking TCP server as a Thread."""

    def __init__(self):
        self._server_socket = socket.create_server(
            (PRINTER_IP, PDL_DATASTREAM_PORT), reuse_port=True
        )
        self._stopping = False
        super().__init__(target=self.target)

    def start(self):
        self._server_socket.listen()
        self._stopping = False
        print(
            f"PDL Datastream server is listening at TCP/IPv4 endpoint {PRINTER_IP}:{PDL_DATASTREAM_PORT}"
        )
        super().start()

    def target(self):
        """Thread function."""

        while True:
            client_socket, client_info = self._server_socket.accept()

            if self._stopping:
                print("Shutting down PDL Datastream server...")
                client_socket.close()

                break
            self.__class__.handle_connection(client_socket, client_info)

    @staticmethod
    def handle_connection(client_socket: socket.socket, client_info: tuple[str, int]) -> None:
        """Handle a client connection."""
        checksum = sha512()
        size = 0
        print(f"Accepted connection from {client_info[0]}:{client_info[1]}")
        print('"Updating..."')

        while True:
            chunk = client_socket.recv(PDL_BUF_SIZE)

            if not chunk:
                break
            checksum.update(chunk)
            size += len(chunk)
            if len(chunk) < PDL_BUF_SIZE:
                break

        print(f"Received {size} bytes, sha512: {checksum.hexdigest()}")
        client_socket.close()

    def stop(self):
        """Stop the server."""
        self._stopping = True
        closing_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        closing_socket.connect((PRINTER_IP, PDL_DATASTREAM_PORT))
        closing_socket.close()
        self._server_socket.close()


def publish_mdns(ip_address: str, name: str) -> None:
    """
    Publish the MDNS entry.

    The entry is published as long as the program runs.
    """
    printer_uuid = uuid.uuid4()
    zeroconf = Zeroconf(interfaces=InterfaceChoice.All)

    ip_address_encoded = socket.inet_aton(ip_address)

    ws_info = ServiceInfo(
        type_="_pdl-datastream._tcp.local.",
        name=f"{name}._pdl-datastream._tcp.local.",
        port=PDL_DATASTREAM_PORT,
        # weight: int = 0,
        # priority: int = 0,
        properties={
            b"product": name.encode("utf-8"),
            b"note": b"Printer",
            b"UUID": str(printer_uuid).encode("utf-8"),
        },
        addresses=[ip_address_encoded],
        # server: Optional[str] = None,
        # host_ttl: int = 120,
        # other_ttl: int = 4500,
        # *,
        # addresses: Optional[List[bytes]] = None,
        # parsed_addresses: Optional[List[str]] = None,
        # interface_index: Optional[int] = None,
    )
    zeroconf.register_service(ws_info)


def run_snmpsim() -> None:
    """Run snmpsim as if called from command line."""
    # Arguments for snmpsim-command-responder
    # Same as
    # uv run snmpsim-command-responder --data-dir=./data/ --agent-udpv4-endpoint=127.0.0.1:1024
    sys.argv.extend(
        [
            "--data-dir=./data/",
            f"--agent-udpv4-endpoint={PRINTER_IP}:{SNMP_PORT}",
            #  "--log-level=debug",
            #  "--debug=all",
        ]
    )
    snmpsim_main()


def main() -> None:
    """Publish MDNS entry via zeroconf and run snmpsim."""
    print("Publishing MDNS entry...")

    def publish_mdns_delayed() -> None:
        time.sleep(10)
        print("Publishing delayed dummy MDNS entry...")
        publish_mdns("1.2.3.4", "DUMMY")

    publish_mdns(PRINTER_IP, "MFC-9332CDW")
    delayed_mdns_thread = threading.Thread(target=publish_mdns_delayed)
    delayed_mdns_thread.start()

    print("Starting PDL Datastream Server...")
    pdl_ds_stream_thread = PdlDsStreamServer()
    pdl_ds_stream_thread.start()

    print("Starting SNMP Server...")
    run_snmpsim()

    pdl_ds_stream_thread.stop()
    delayed_mdns_thread.join()
    pdl_ds_stream_thread.join()


if __name__ == "__main__":
    main()
