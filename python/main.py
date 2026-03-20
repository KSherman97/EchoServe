"""
Author: Kyle Sherman
Details:

Note: No AI was used in the production of this application

This is a learning project to immitate a very rudimentary version of a webserver
Think Apache or NGINX in Python.

Because my focus is on the workings of HTTP and TCP, there will likely be imperfections
throughout the code.
"""
import os
import threading
import socket as skt
import mimetypes
import logging
import json
import struct

"""
TODO:

[x] We need to implement chunking (standard is 4kb or 8kb)
[x] We will need to implement some form of multithreading as well
[x] We need to implement logging
[x] We need to load from a config

[ ] Investigate using Async IO over threads (for now threads are fine)
[ ] As it stands too many items are hard coded
[ ] We need to allow default pages to be set for error handling
[ ] We need routing logic, IE. .php serves php pages and everything else is static
"""
CONFIG = {}
HOST = None
PORT = None
CHUNK_SIZE = None
BACKLOG = None
WEB_ROOT = None
DEFAULT_PAGE = "index.html"
ERROR_404 = "404.html"

# FastCGI Constants
FCGI_VERSION = 1
FCGI_BEGIN_REQUEST = 1
FCGI_PARAMS = 4
FCGI_RESPONDER = 1
FCGI_KEEP_CONN = 1

logger = logging.getLogger(__name__)
logging.basicConfig(
    filename='output.log',
    filemode='w', 
    encoding='utf-8', 
    level=logging.DEBUG,
    format='%(asctime)s [%(threadName)s] %(levelname)s: %(message)s'
    )
# logger levels(debug, info, warning, error)

"""
process: socket() -> bind() -> listen() -> accept

Currently a single connection can be made and a response packet will be sent
"""

"""
Try to load the config file, but set sensible defaults just in case
"""
def load_config():
    base_path = os.getcwd()
    config_path = os.path.join(base_path, "config.json")

    defaults = {
        "HOST": "127.0.0.1",
        "PORT": 8080,
        "CHUNK_SIZE": 8192,
        "WEB_ROOT": "web",
        "DEFAULT_PAGE": "index.html",
        "ERROR_404": "404.html"
    }

    if os.path.exists(config_path):
        with open(config_path, "r") as config:
            user_config = json.load(config)
            defaults.update(user_config)
    return defaults

"""
Packs a standard FCGI record per the FCGI docs: 8-byte header + content
"""
def pack_fcgi_record(type, req_id, content):
    length = len(content)
    # header format - slot(bytes): Version(1), Type(1), ReqID(2), ContentLen(2), Padding(1), Reserved(1)
    header = struct.pack("!BBHHBx", FCGI_VERSION, type, req_id, length, 0)
    return header + content

"""
Pack name-value paris into the FastCGI format per the docs
"""
def pack_fcgi_params(params):
    body = b"" # set into byte format
    for name, value in params.items():
        name, value = name.encode(), str(value).encode()
        # encode lengths: assuming < 127 bytes for example
        body += struct.pack("!BB", len(name), len(value)) + name + value
    return body


"""
Run processing the connection pool in its own thread. Each connection is
assigned its own thread to prevent blocking connections from larger files
"""
def handle_client(connection, address):
    try:
        logger.info(f"Connected by {address}")
        connection.settimeout(10)
        data = connection.recv(1024)

        if not data:
            return
        
        method, path, _ = parse_request(data)
        response_type, target, extra = response_builder(path)

        if response_type == "STATIC_CHUNK":
            connection.sendall(extra) # extra is the header
            chunk_file(target, connection)
            connection.sendall(b'0\r\n\r\n')

        elif response_type == "PHP_EXEC":
            # PHP CGI logic will go here
            logger.info(f"Attempting to execute PHP: {target}")
            begin_body = struct.pack("!HB5x", FCGI_RESPONDER, FCGI_KEEP_CONN)

            params = {
                "SCRIPT_FILENAME": target,
                "REQUEST_METHOD": method,
                "QUERY_STRING": "",
                "CONTENT_TYPE": "",
                "CONTENT_LENGTH": "0",
                "GATEWAY_INTERFACE": "CGI/1.1",
                "REMOTE_ADDR": address[0],
                "SERVER_PROTOCOL": "HTTP/1.1"
            }

            try:
                with skt.socket(skt.AF_INET, skt.SOCK_STREAM) as php_socket:
                    php_socket.connect(("127.0.0.1", 9000))

                    # send records
                    php_socket.sendall(pack_fcgi_record(FCGI_BEGIN_REQUEST, 1, begin_body))
                    php_socket.sendall(pack_fcgi_record(FCGI_PARAMS, 1, pack_fcgi_params(params)))
                    php_socket.sendall(pack_fcgi_record(FCGI_PARAMS, 1, b"")) # end of params

                    headers_sent = False

                    while True:
                        # read the 8 byte header
                        header_data = php_socket.recv(8)
                        if not header_data or len(header_data) < 8:
                            break

                        # unpack
                        _, r_type, _, content_len, padding_len, _ = struct.unpack("!BBHHBB", header_data)

                        # read the content based on the len in the header
                        if content_len > 0:
                            payload = php_socket.recv(content_len)

                            if not headers_sent:
                                if b"\r\n\r\n" in payload:
                                    php_headers, php_body = payload.split(b"\r\n\r\n", 1)

                                    # send the real HTTP response start
                                    connection.sendall(b"HTTP/1.1 200 OK\r\n")
                                    connection.sendall(php_headers + b"\r\n")
                                    connection.sendall(b"Transfer-Encoding: chunked\r\n")
                                    connection.sendall(b"\r\n")

                                    if php_body:
                                        chunk_h = f"{hex(len(php_body))[2:]}\r\n".encode()
                                        connection.sendall(chunk_h + php_body + b"\r\n")

                                    headers_sent = True

                            else:
                                chunk_h = f"{hex(content_len)[2:]}\r\n".encode()
                                connection.sendall(chunk_h + payload + b"\r\n")

                        # skip padding bytes
                        if padding_len > 0:
                            php_socket.recv(padding_len)

                        # if type is FCGI_END_REQ we are done
                        if r_type == 3:
                            break
                    
                    connection.sendall(b"0\r\n\r\n")
            except Exception as e:
                logger.error(f"PHP-FPM Connection Error: {e}")
                connection.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\nPHP-FPM Error")

        elif response_type == "DIRECT_RESPONSE":
            # all hardcoded fallbacks will live heer
            connection.sendall(b"HTTP/1.1 404 Not Found\r\n\r\n" + target)

    except Exception as e:
        logger.error(f"Error handling client {address}: {e}")

    finally:
        connection.close()
        logger.info(f"Close connection from {address}")

"""
file_mapper is tasked with mapping a url request path to a physical dir
on the system. Also fetches the mimetype for the file and returns
the path and the type
"""
def file_mapper(path):
    root_dir = os.getcwd() # get the current working directory
    web_dir = os.path.join(root_dir, WEB_ROOT)

    requested_path = path.lstrip("/")
    full_path = os.path.abspath(os.path.join(web_dir, requested_path))

    # sanity check: Don't allow a path outside of our designated web path
    if not full_path.startswith(os.path.abspath(web_dir)):
        # fallback to index or raise error
        full_path = os.path.join(web_dir, DEFAULT_PAGE)

    # if the path is a directory, no file specified then we will return the default page
    if os.path.isdir(full_path):
        full_path = os.path.join(full_path, DEFAULT_PAGE)

    file_type = mimetypes.guess_type(full_path)
    return full_path, file_type

"""
Takes in a request as a argument
Returns the request method (POST, GET, etc...), the path(/index.html, ...),
and any request headers
"""
def parse_request(request):
    request = request.decode()

    parsed_request = request.split("\n")
    return_value = parsed_request[0].split(" ")

    return return_value[0], return_value[1], []

"""
    HTTP Response Builder Components:
    Status Line
    Headers
    Blank Line
    Body (page, etc.)

    When we are sending chunks, we will need to also determine the length of each chunk
    and append it to the front of the header in hex format, but we must also strup the 0x
    for example: 0x1f40 -> 1f40
"""
def response_builder(path):
    file_path, file_type_tuple = file_mapper(path)
    file_type = file_type_tuple[0] if file_type_tuple[0] else "application/octet-stream"
    status = "200 OK"

    # routing logic: check for php extension
    if file_path.endswith(".php"):
        # we return none for extra (header) becuase PHP-fpm generates its own headers
        return "PHP_EXEC", file_path, None

    # static logic to handle missing files with config error page
    if not os.path.exists(file_path):
        status = "404 Not Found"
        file_type = "text/html"
        web_dir = os.path.join(os.getcwd(), WEB_ROOT)
        file_path = os.path.join(web_dir, ERROR_404)

        # absolute fallback if the 404 page is missing as well
        if not os.path.exists(file_path):
            return "DIRECT_RESPONSE", RESPONSE_404, "text/html"

    # construct the headers
    # use text/html for .html files, but will need to integrate mime-types later
    header = (
        f"HTTP/1.1 {status}\r\n"
        f"Content-Type: {file_type}\r\n"
        # f"Content-Length: {len(file_contents)}\r\n"
        f"Transfer-Encoding: chunked\r\n"
        "Connection: close\r\n"
        "\r\n"
    )

    # combine the bytes: header (encoded) + body (already in bytes format)
    return "STATIC_CHUNK", file_path, header.encode("utf-8"), # file_contents

def chunk_file(full_file, connection):
    try:
        with open(full_file, 'rb') as file:
            while True:
                chunk = file.read(CHUNK_SIZE)
                if not chunk:
                    break

                header_size = f"{len(chunk):x}\r\n".encode('utf-8')
                # send the chunk
                connection.sendall(header_size)
                connection.sendall(chunk + b'\r\n')
    except Exception as e:
        logger.error(f"Error reading file: {e}")


def main():
    # the socket expects an address family and socket type
    # AF_NET is the family for IPV4
    # SOCK_STREAM is the socket type for TCP
    with skt.socket(skt.AF_INET, skt.SOCK_STREAM) as socket:
        socket.setsockopt(skt.SOL_SOCKET, skt.SO_REUSEADDR, 1) # allows the addr and port to be reused

        socket.bind((HOST, PORT))
        socket.listen(5) # allow up to five pooled connections
        logger.info(f"Server started on {HOST}:{PORT}")

        # main client acceptance loop
        # socket.accept is a blocking method as expected
        while True:
            connection, address = socket.accept()

            # handle thread creation ot handle each specific connectino
            client_thread = threading.Thread(
                target = handle_client,
                args = (connection, address)
            )

            client_thread.daemon = True
            client_thread.start()

if __name__ == "__main__":
    CONFIG = load_config()

    HOST = CONFIG.get("HOST")
    PORT = CONFIG.get("PORT")
    CHUNK_SIZE = CONFIG.get("CHUNK_SIZE")
    BACKLOG = CONFIG.get("BACKLOG_CLIENTS", 5)
    WEB_ROOT = CONFIG.get("WEB_ROOT")
    DEFAULT_PAGE = CONFIG.get("DEFAULT_PAGE")
    ERROR_404 = CONFIG.get("ERROR_404")

    main()