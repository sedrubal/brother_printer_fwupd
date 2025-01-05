# Brother Printer MDNS & SNMP Simulator

MDNS and SNMP simulator for Brother Printers using
[Zeroconf](https://github.com/python-zeroconf/python-zeroconf) and
[snmpsim](https://docs.lextudio.com/snmpsim/).

## Run the simulator

```bash
uv run ./run.py
```

## Test the simulator

```bash
# Test MDNS
avahi-resolve --name MFC-9332CDW._pdl-datastream._tcp.local
avahi-browse --all --resolve
# Test SNMP
snmpwalk -v 2c -c public 127.0.0.1:1161 1.3.6.1.4.1.2435.2.4.3.99.3.1.6.1.2
```
