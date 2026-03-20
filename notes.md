## TCP & SOCKETS

### What is a webserver
A program that reads bytes from a socket and writes bytes back as a response (call & response).

### What is a TCP connection
TCP - Transmission Control Protocol is a reliable, ordered, and error-checked communication session between two networked devices, ensuring data packets are delivered intact using a three way handshake. It is the foundation of the internet (TCP/IP): HTTP (Web), email (IMAP/SMTP), Secure Shell (SSH)

Aspects:
- Reliable Delivery: no errors and restransmitting lost packets
- Three way handshake: Establishes a connection using packets
    - SYN: Synchronize packet to server
    - SYN-ACK: server Acknowledge synchronized packet
    - ACK: Client sends acknowledgement back to server establishing connection
- flow control & congestion control: Manages data transmission rates to prevent network overload
- full duplex: Allows data in both directions independently

### Client <-> Server lifecycle
consists of five main stages: 
1. connection init
2. request submission
3. server processing
4. response transmission
5. connection termination

### Actions (bind, listen, accept)
socket(): create a new unnamed socket endpoint in the OS for TCP stream communication

bind(): Assign address - associates a socket with a local address and port

listen(): Marks the socket as a server socket and transitions into a passive mode to wait for incoming client connections

accept(): Blocks the server program until a client connects. Once a client is connected, accept creates a new socket for the data transfer with that client, 
allowing the original socket to continue listening

connect(): Used by the client to request a connection to a server ip and port initiating a handshake

send() / recv(): Data exchange; transmits and receives data over a connection socket

close(): Terminate; closes the socket, releasing resources and terminating the connection

Typical Flow:
1. server: socket() -> bind() -> listen() -> accept()
2. client: socket() -> connect()
3. both: send() / recv() -> close()

### What is a socket
A socket is effectively a file descriptor that you r/w bytes from