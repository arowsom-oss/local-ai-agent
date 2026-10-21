"""Python socket audit tripwire for CI tests; not an OS network sandbox."""
import sys

BLOCKED={'socket.connect','socket.bind','socket.getaddrinfo','socket.gethostbyname',
         'socket.gethostbyaddr','socket.getnameinfo','socket.sendto','socket.sendmsg'}

def reject_network(event,args):
    if event in BLOCKED:
        raise RuntimeError('Offline CI refused a real socket/DNS operation')

sys.addaudithook(reject_network)
