"""Deny external Python socket connects during isolated review tests."""
import ipaddress
import socket

_connect = socket.socket.connect
_connect_ex = socket.socket.connect_ex

def permitted(address):
    if isinstance(address, str):
        return True
    host = address[0]
    if host == 'localhost':
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False

def connect(self, address):
    if not permitted(address):
        raise OSError('External network disabled for review7195')
    return _connect(self, address)

def connect_ex(self, address):
    if not permitted(address):
        return 101
    return _connect_ex(self, address)

socket.socket.connect = connect
socket.socket.connect_ex = connect_ex
