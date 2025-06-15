import socket
import json
from colorama import Fore, Style

def notify_tracker_peer_offline(peer, dead_peer_id):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((TRACKER_HOST, TRACKER_PORT))
            msg = {
                "action": "peer_offline",
                "dead_peer_id": dead_peer_id,
                "sender_id": peer.peer_id
            }
            s.sendall(json.dumps(msg).encode())
    except:
        print(f"[{peer.peer_id}] Falha ao notificar o tracker sobre o peer morto: {dead_peer_id}")

def send_message(peer, ip, port, msg):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((ip, port))
            s.sendall(json.dumps(msg).encode())
    except ConnectionRefusedError:
        target_peer_id = peer.get_peer_id_by_address(ip, port)
        if target_peer_id:
            print(f"[{peer.peer_id}] Não foi possível conectar ao peer {target_peer_id} ({ip}:{port}). Removendo da lista.")
            peer.peer_blocks.pop(target_peer_id, None)
            peer.known_peers.pop(target_peer_id, None)
            peer.notify_tracker_peer_offline(target_peer_id)
        else:
            print(f"[{peer.peer_id}] Não foi possível conectar ao peer desconhecido ({ip}:{port}). Sem ação.")
            print(f"{Fore.RED}[{peer.peer_id}] Connection error to {target_pid}: {e}{Style.RESET_ALL}")

def announce_block(peer, block_idx):
    for pid, (ip, port) in peer.known_peers.items():
        msg = {
            "action": "announce_block",
            "sender_id": peer.peer_id,
            "block_index": block_idx
        }
        send_message(peer, ip, port, msg)

def request_block_from_peer(peer, target_pid, block_idx):
    if target_pid not in peer.known_peers:
        return

    ip, port = peer.known_peers[target_pid]
    msg = {
        "action": "request_block",
        "sender_id": peer.peer_id,
        "block_index": block_idx
    }
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((ip, port))
            s.sendall(json.dumps(msg).encode())
            data = s.recv(4096)
            resp = json.loads(data.decode())

            if resp["status"] == "success":
                peer.blocks_owned[block_idx] = True
                peer.block_data[block_idx] = resp["block_data"]
                print(f"{Fore.GREEN}[{peer.peer_id}] Received block {block_idx} from {target_pid}{Style.RESET_ALL}")
                announce_block(peer, block_idx)
            else:
                print(f"{Fore.RED}[{peer.peer_id}] Failed to get block {block_idx} from {target_pid}: {resp.get('reason')}{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}[{peer.peer_id}] Failed to get block {block_idx} from {target_pid}: {e}{Style.RESET_ALL}")

def request_block_from_tracker(peer, block_idx):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((peer.TRACKER_HOST, peer.TRACKER_PORT))
            msg = {
                "action": "request_block",
                "sender_id": peer.peer_id,
                "block_index": block_idx
            }
            s.sendall(json.dumps(msg).encode())
            data = s.recv(4096)
            resp = json.loads(data.decode())

            if resp["status"] == "success":
                peer.blocks_owned[block_idx] = True
                peer.block_data[block_idx] = resp["block_data"]
                print(f"{Fore.GREEN}[{peer.peer_id}] Received block {block_idx} from TRACKER{Style.RESET_ALL}")
                announce_block(block_idx)
            else:
                print(f"{Fore.RED}[{peer.peer_id}] Failed to get block {block_idx} from TRACKER: {resp.get('reason')}{Style.RESET_ALL}")

    except Exception as e:
        print(f"{Fore.RED}[{peer.peer_id}] Error contacting tracker for block {block_idx}: {e}{Style.RESET_ALL}")



def register_with_tracker(peer):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((peer.TRACKER_HOST, peer.TRACKER_PORT))
        msg = {
            "action": "register",
            "peer_id": peer.peer_id,
            "listen_port": peer.listen_port
        }
        s.sendall(json.dumps(msg).encode())
        data = s.recv(4096)
        resp = json.loads(data.decode())

        print(f"{Fore.GREEN}[{peer.peer_id}] Registered. Initial blocks: {resp['initial_blocks']}{Style.RESET_ALL}")

        for idx in resp['initial_blocks']:
            peer.blocks_owned[idx] = True
            peer.block_data[idx] = f"Block {idx} data"

        for peer in resp['peers']:
            pid = peer['peer_id']
            peer.known_peers[pid] = (peer['ip'], peer['port'])
            peer.peer_blocks[pid] = [False] * TOTAL_FILE_BLOCKS

def send_blocks_info(peer):
    for pid, (ip, port) in list(peer.known_peers.items()):
        msg = {
            "action": "have_blocks_info",
            "sender_id": peer.peer_id,
            "blocks_info": peer.blocks_owned
        }
        send_message(peer, ip, port, msg)

def update_peers_from_tracker(peer):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((peer.TRACKER_HOST, peer.TRACKER_PORT))
            msg = {
                "action": "get_peers",
                "peer_id": peer.peer_id
            }
            s.sendall(json.dumps(msg).encode())
            data = s.recv(4096)
            resp = json.loads(data.decode())

            for peer in resp['peers']:
                pid = peer['peer_id']
                if pid == peer.peer_id:
                    continue
                if pid not in peer.known_peers:
                    peer.known_peers[pid] = (peer['ip'], peer['port'])
                    blocks_list = peer.get('blocks_owned', [])
                    blocks_bool = [i in blocks_list for i in range(TOTAL_FILE_BLOCKS)]
                    peer.peer_blocks[pid] = blocks_bool
                    print(f"{Fore.CYAN}[{peer.peer_id}] Discovered peer {pid}{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}[{peer.peer_id}] Error contacting tracker: {e}{Style.RESET_ALL}")

# def get_peer_id_by_address(self, ip, port):
#     for pid, (peer_ip, peer_port) in self.known_peers.items():
#         if peer_ip == ip and peer_port == port:
#             return pid
#     return None

