#!/usr/bin/python3
"""Start MPI children inside this container using the launcher's ssh conventions."""
import os
import socket
import sys


def main():
    args = sys.argv[1:]
    while args and args[0].startswith('-'):
        option = args.pop(0)
        if option == '-l' and args:
            args.pop(0)
        elif option != '-n':
            raise SystemExit('Unsupported MPI local-shell option')
    if len(args) < 2 or args.pop(0) not in (socket.gethostname(), 'localhost', '127.0.0.1'):
        raise SystemExit('MPI local shell refuses another host')
    os.execv('/bin/sh', ['sh', '-c', ' '.join(args)])


if __name__ == '__main__':
    main()
