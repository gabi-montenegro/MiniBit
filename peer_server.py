import json
from colorama import Fore, Style

def handle_block_request(peer, conn, msg):
        block_idx = msg['block_index']
        sender_id = msg['sender_id']

        if peer.blocks_owned[block_idx] and sender_id in peer.unchoked_peers:
            response = {
                "status": "success",
                "block_index": block_idx,
                "block_data": peer.block_data[block_idx]
            }
            print(f"{Fore.GREEN}[{peer.peer_id}] Sending block {block_idx} to {sender_id}{Style.RESET_ALL}")
        else:
            response = {"status": "error", "reason": "Choked or block unavailable"}
            print(f"{Fore.RED}[{peer.peer_id}] Denied block {block_idx} request from {sender_id} (choked or unavailable){Style.RESET_ALL}")
        conn.sendall(json.dumps(response).encode())


def handle_have_blocks_info_request(peer, conn, msg):
        sender_id = msg.get("sender_id")
        response = {
            "status": "success",
            "peer_id": peer.peer_id,
            "blocks_info": peer.blocks_owned
        }
        print(f"{Fore.CYAN}[{peer.peer_id}] Sending own blocks info to {sender_id}{Style.RESET_ALL}")
        conn.sendall(json.dumps(response).encode())
        
def handle_peer_request(peer, conn, addr):
    with conn:
        data = conn.recv(4096)
        if not data:
            return
        msg = json.loads(data.decode())
        action = msg.get("action")
        sender = msg.get("sender_id")

        if action == "request_block":
            handle_block_request(peer,conn, msg)
        elif action == "have_blocks_info":
            peer.peer_blocks[sender] = msg['blocks_info']
        elif action == "have_blocks_info":
            handle_have_blocks_info_request(peer, conn, msg)
        elif action == "announce_block":
            if sender in peer.peer_blocks and 0 <= msg['block_index'] < peer.TOTAL_FILE_BLOCKS:
                peer.peer_blocks[sender][msg['block_index']] = True
                print(f"{Fore.CYAN}[{peer.peer_id}] Peer {sender} announced block {msg['block_index']}{Style.RESET_ALL}")


def listen_for_peers(peer):
    import socket
    import threading

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(('0.0.0.0', peer.listen_port))
    server_socket.listen(5)
    print(f"{Fore.YELLOW}[{peer.peer_id}] Listening on port {peer.listen_port}...{Style.RESET_ALL}")

    while True:
        conn, addr = server_socket.accept()
        threading.Thread(target=handle_peer_request, args=(peer, conn, addr)).start()


