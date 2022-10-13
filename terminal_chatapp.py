from collections import namedtuple
from logging import exception
import socket
import selectors
import sys
from time import sleep
import traceback
from typing import Union
from requests import get


Connection = namedtuple('Connection', ['id', 'addr', 'port'])
id = 0

class PROGRAM_EXIT(Exception):
    pass

# wrappper used to hold the selection menu of the chat applciation
def menu(selector: selectors.DefaultSelector, connection_list: list, listen: socket.socket):

    # reads input from stdin and strips whitespaces
    input = (sys.stdin.readline()).rstrip()

    # catch error to prevent app crash
    try:
        # splits the string by " " so addtional input arguments can be read.
        input = input.split(" ")
        if input[0] == "help":
            help()
        elif input[0] == "myip":
            print(f"The IP address is {get_ip()}")
        elif input[0] == "myport":
            print(f"The program runs on port number {get_port(listen)}")
        elif input[0] == "connect":
            connect(selector, connection_list, input[1], int(input[2]), listen)
        elif input[0] == "list":
            list_connections(selector, connection_list)
        elif input[0] == "send":
            send_message(selector, connection_list, int(input[1]), " ".join(input[2:len(input)]))
        elif input[0] == "terminate":
            terminate(selector, connection_list, int(input[1]))
        elif input[0] == "exit":
            exit_program(selector, connection_list)
            raise PROGRAM_EXIT
        else:
            print(  "invalid command: use command "
                    "help to display valid commands" )
    except IndexError:
        print(  "invalid usage: use command "
                "help to display valid usage")

# wrapper, display menu
def help():
    print("myip - display IP address\n"
          "myport - display Port\n"
          "connect <ip> <port> - connect to another peer \n"
          "send <id> <msg> - send messages to peers\n"
          "………….\nexit - exit the program")

def get_ip() -> str:
    return socket.gethostbyname(socket.gethostname() + ".local")

def get_port(sock: socket.socket):
    return sock.getsockname()[1]

def connect(selector: selectors.DefaultSelector, connection_list: list, ip: str, port: int, listen: socket.socket):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, )
        sock.setblocking(False)
        sock.connect_ex((ip, port))
        events = selectors.EVENT_READ

        id = get_id()

        data = Connection(id, ip, port)

        connection_list.append((id, sock))
        selector.register(sock, events, data=data)

        sleep(0.1)
        sock.sendall(f"\n\r\n\rlisten {get_port(listen)}".encode())
        print(f"The connection to peer {ip} is succeessfully established;")
    except ConnectionError:
        connection_list.remove((id, sock))
        selector.unregister(sock)
        print(f"The connection to peer failed;")

    except:
        connection_list.remove((id, sock))
        selector.unregister(sock)
        traceback.print_exc()

def list_connections(selector: selectors.DefaultSelector, connection_list: list):
    print(f"id:\tIP Addresss\tPort")
    for entry in connection_list:
        sel_key = selector.get_key(entry[1])
        print(f"{entry[0]}:\t{sel_key.data.addr}\t{sel_key.data.port}")

def send_message(selector: selectors.DefaultSelector, connection_list: list, conn_id: int, msg: str) -> None:
    try:
        target_sock: socket.socket
        target_sock = None

        for entry in connection_list:
            if(entry[0] == conn_id):
                target_sock = entry[1]
        
        if target_sock is None:
            print("No corresponding connection was found")    
            return
            
        target_sock.sendall(msg.encode())
        return
    except:
        print("Message failed to send")
        return

def terminate(selector: selectors.DefaultSelector, connection_list: list, conn_id: int):
    try:
        target_sock: socket.socket
        target_sock = None

        for entry in connection_list:
            if(entry[0] == conn_id):
                target_sock = entry[1]

        if target_sock is None:
            print("No corresponding connection was found")
            return    

        target_sock.sendall(b"\n\r\n\rterminate\n\r\n\r")
        selector.unregister(target_sock)
        target_sock.close()
        connection_list.remove((conn_id, target_sock))

    except BrokenPipeError:
            target_sock.close()
            selector.unregister(target_sock)
            connection_list.remove((conn_id, target_sock))
    except:
        traceback.print_exc()


def exit_program(selector: selectors.DefaultSelector, connection_list: list) -> Union[selectors.DefaultSelector, list]:
        for entry in connection_list:
            (selector, connection_list) = terminate(selector, connection_list, entry[0])

        return selector, connection_list

def get_id():
    global id
    id += 1
    return id

def accept_wrapper(selector: selectors.DefaultSelector, connection_list: list, sock: socket.socket, listen: socket.socket):
    try:
        
        conn, addr = sock.accept()
        print(conn.getpeername())
        conn.setblocking(False)
        events = selectors.EVENT_READ
        
        id = get_id()
        data = Connection(id, addr[0], addr[1])
        selector.register(conn, events, data=data)
        connection_list.append((id,conn))
        
        print(f"The connection to peer {addr[0]} is succeessfully established;")
    except:
        print("The connection to peer was not established;")

def receive_msg(selector: selectors.DefaultSelector, connection_list: list, sock: socket.socket, data: any, mask: any):
    if mask & selectors.EVENT_READ:
        recv_data = sock.recv(1024)
        if recv_data:

            if recv_data == b"\n\r\n\rterminate\n\r\n\r":
                print(f"Peer {data.addr} terminates the connection")
                terminate(selector, connection_list, data.id)
                return
            
            dec_rd = recv_data.decode()
            dec_rdata_sp = dec_rd.split(" ")
            if dec_rdata_sp[0] == "\n\r\n\rlisten":
                sel_key = selector.get_key(sock)
                id = sel_key.data.id
                ip = sel_key.data.addr
                port = dec_rdata_sp[1]
                selector.unregister(sock)
                selector.register(sock, selectors.EVENT_READ, data=Connection(id, ip, port))
                return
            
            print(f"Message received from {data.addr}:")
            print("\"" + dec_rd + "\"")
            #selector.unregister(sock)


            

def main():

    if len(sys.argv) != 2:
        print("usage: python3 terminal_chatapp <port number>")
        exit()

    # Grabs port from program arguments
    SEVER_PORT = sys.argv[1]
    conn_list = list()
    sel = selectors.DefaultSelector()

    lsocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    lsocket.bind((get_ip(), int(SEVER_PORT)))
    lsocket.listen()
    lsocket.setblocking(False)

    sel.register(lsocket, selectors.EVENT_READ, data=None)
    sel.register(sys.stdin, selectors.EVENT_READ, data="STDIN")

    try:
        while True:

            #print(">>", flush=True, end=" ")
            event = sel.select(timeout=None)

            for key, mask in event:
                
                if key.data == "STDIN":
                    menu(sel,conn_list, lsocket)
                else:
                    if key.data is None:
                        accept_wrapper(sel, conn_list, key.fileobj, lsocket)
                    else:
                        receive_msg(sel, conn_list, key.fileobj, key.data, mask)
    except PROGRAM_EXIT:
        print("Exiting program...")
        lsocket.close()
        sel.close()
        exit()
    except (KeyboardInterrupt):
        exit_program(sel, conn_list)
        lsocket.close()
        sel.close()
        exit()
    except Exception:
        exit_program(sel, conn_list)
        lsocket.close()
        sel.close()
        traceback.print_exc()
        exit()

main()
