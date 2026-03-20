import socket as skt
import os

HOST = "127.0.0.1"
PORT = 8080

"""
process: socket() -> bind() -> listen() -> accept

Currently a single connection can be made and a response packet will be sent
"""

def file_mapper(path):
    root_dir = os.getcwd() # get the current working directory
    web_dir = root_dir + "/web/"

    if path[-1] == "/":
        path = path + "index.html"

    file_path = web_dir + path
    return file_path

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
"""
def response_builder(path):
    file = file_mapper(path)

    # We need to open the file contents in binary mode due to the nature of HTTP
    try:
        with open(file, "rb") as f:
            file_contents = f.read()
        status = "200 OK"
    except FileNotFoundError:
        file_contents = b"<h1>404 File Not Found</h1>"
        status = "400 Not Found"

    # construct the headers
    # use text/html for .html files, but will need to integrate mime-types later
    header = (
        f"HTTP/1.1 {status}\r\n"
        "Content-Type: text/html\r\n"
        f"Content-Length: {len(file_contents)}\r\n"
        "Connection: close\r\n"
        "\r\n"
    )

    # combine the bytes: header (encoded) + body (already in bytes format)
    return header.encode("utf-8") + file_contents

def main():
    # the socket expects an address family and socket type
    # AF_NET is the family for IPV4
    # SOCK_STREAM is the socket type for TCP
    with skt.socket(skt.AF_INET, skt.SOCK_STREAM) as socket:
        socket.setsockopt(skt.SOL_SOCKET, skt.SO_REUSEADDR, 1) # allows the addr and port to be reused

        socket.bind((HOST, PORT))
        socket.listen(5) # allow up to five pooled connections

        # main client acceptance loop
        # socket.accept is a blocking method as expected
        while True:
            connection, address = socket.accept()
            with connection:
                print(f"Connected by {address}")

                data = connection.recv(1024)
                if data:
                    method, path, headers = parse_request(data)

                                    
                    connection.sendall(response_builder(path))

if __name__ == "__main__":
    main()