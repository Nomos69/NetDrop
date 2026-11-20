"""LAN-only NetDrop host discovery used by the Windows companion.

The browser never sends multicast traffic.  A native companion discovers the
``_netdrop._tcp.local.`` mDNS service and opens the selected local host.
"""

import ipaddress
import socket
from dataclasses import dataclass

try:
    from zeroconf import ServiceBrowser, ServiceInfo, Zeroconf
except ImportError:  # Allows the Online-only server to start before local extras are installed.
    ServiceBrowser = ServiceInfo = Zeroconf = None


SERVICE_TYPE = "_netdrop._tcp.local."


@dataclass(frozen=True)
class LocalHost:
    name: str
    url: str


def local_ipv4_addresses():
    """Return usable private IPv4 addresses without publishing loopback."""
    addresses = set()
    try:
        candidates = socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
    except socket.gaierror:
        candidates = []
    for candidate in candidates:
        address = candidate[4][0]
        if ipaddress.ip_address(address).is_private and not address.startswith("127."):
            addresses.add(address)
    return sorted(addresses)


class LocalAdvertiser:
    """Advertise one local NetDrop host for the lifetime of its server."""

    def __init__(self, port):
        self.port = port
        self.zeroconf = None
        self.info = None

    def start(self):
        if Zeroconf is None:
            return False
        addresses = local_ipv4_addresses()
        if not addresses:
            return False
        label = socket.gethostname().replace(".", "-")[:48] or "NetDrop"
        self.info = ServiceInfo(
            SERVICE_TYPE,
            f"NetDrop on {label}.{SERVICE_TYPE}",
            addresses=[socket.inet_aton(address) for address in addresses],
            port=self.port,
            properties={b"path": b"/", b"product": b"NetDrop"},
            server=f"{label}.local.",
        )
        self.zeroconf = Zeroconf()
        self.zeroconf.register_service(self.info)
        return True

    def stop(self):
        if self.zeroconf is not None:
            try:
                if self.info is not None:
                    self.zeroconf.unregister_service(self.info)
            finally:
                self.zeroconf.close()
                self.zeroconf = None


class _Listener:
    def __init__(self, zeroconf, hosts):
        self.zeroconf = zeroconf
        self.hosts = hosts

    def add_service(self, _zeroconf, service_type, name):
        info = self.zeroconf.get_service_info(service_type, name, timeout=1500)
        if info is None:
            return
        addresses = [socket.inet_ntoa(address) for address in info.addresses]
        private = next((address for address in addresses
                        if ipaddress.ip_address(address).is_private and not address.startswith("127.")), None)
        if private:
            label = name.removesuffix(SERVICE_TYPE).rstrip(".")
            self.hosts[f"http://{private}:{info.port}"] = LocalHost(label, f"http://{private}:{info.port}")

    def update_service(self, *_args):
        return None

    def remove_service(self, *_args):
        return None


def discover_local_hosts(timeout_seconds=3):
    """Return NetDrop hosts visible on the current LAN; no cloud request occurs."""
    if Zeroconf is None:
        raise RuntimeError("Local discovery is unavailable. Reinstall NetDrop Local.")
    import time
    hosts = {}
    zeroconf = Zeroconf()
    try:
        ServiceBrowser(zeroconf, SERVICE_TYPE, _Listener(zeroconf, hosts))
        time.sleep(timeout_seconds)
        return sorted(hosts.values(), key=lambda host: host.name.lower())
    finally:
        zeroconf.close()
