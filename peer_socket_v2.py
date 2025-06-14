import socket
import threading
import json
import random
import time
from colorama import Fore, Style

TRACKER_HOST = '127.0.0.1'
TRACKER_PORT = 9000
TOTAL_FILE_BLOCKS = 50

class PeerSocket:
    def __init__(self, peer_id, listen_port):
        self.peer_id = peer_id
        self.listen_port = listen_port
        self.blocks_owned = [False] * TOTAL_FILE_BLOCKS
        self.block_data = {}
        self.known_peers = {}  # {peer_id: (ip, port)}
        self.peer_blocks = {}  # {peer_id: [bool, bool, ...]}
        self.unchoked_peers = set()
        self.file_complete = False

    def listen_for_peers(self):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind(('0.0.0.0', self.listen_port))
        server_socket.listen(5)
        print(f"{Fore.YELLOW}[{self.peer_id}] Listening on port {self.listen_port}...{Style.RESET_ALL}")

        while True:
            conn, addr = server_socket.accept()
            threading.Thread(target=self.handle_peer_request, args=(conn, addr)).start()

    def handle_peer_request(self, conn, addr):
        with conn:
            data = conn.recv(4096)
            if not data:
                return
            msg = json.loads(data.decode())
            action = msg.get("action")
            sender = msg.get("sender_id")

            if action == "request_block":
                self.handle_block_request(conn, msg)
            elif action == "have_blocks_info":
                self.peer_blocks[sender] = msg['blocks_info']
                print(f"{Fore.CYAN}[{self.peer_id}] Received blocks info from {sender}: {msg['blocks_info']}{Style.RESET_ALL}")
            elif action == "announce_block":
                if sender in self.peer_blocks and 0 <= msg['block_index'] < TOTAL_FILE_BLOCKS:
                    self.peer_blocks[sender][msg['block_index']] = True
                    print(f"{Fore.CYAN}[{self.peer_id}] Peer {sender} announced block {msg['block_index']}{Style.RESET_ALL}")

    def handle_block_request(self, conn, msg):
        block_idx = msg['block_index']
        sender_id = msg['sender_id']

        if self.blocks_owned[block_idx] and sender_id in self.unchoked_peers:
            response = {
                "status": "success",
                "block_index": block_idx,
                "block_data": self.block_data[block_idx]
            }
            print(f"{Fore.GREEN}[{self.peer_id}] Sending block {block_idx} to {sender_id}{Style.RESET_ALL}")
        else:
            response = {"status": "error", "reason": "Choked or block unavailable"}
            print(f"{Fore.RED}[{self.peer_id}] Denied block {block_idx} request from {sender_id} (choked or unavailable){Style.RESET_ALL}")
        conn.sendall(json.dumps(response).encode())

    def register_with_tracker(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((TRACKER_HOST, TRACKER_PORT))
            msg = {
                "action": "register",
                "peer_id": self.peer_id,
                "listen_port": self.listen_port
            }
            s.sendall(json.dumps(msg).encode())
            data = s.recv(4096)
            resp = json.loads(data.decode())

            print(f"{Fore.GREEN}[{self.peer_id}] Registered. Initial blocks: {resp['initial_blocks']}{Style.RESET_ALL}")

            for idx in resp['initial_blocks']:
                self.blocks_owned[idx] = True
                self.block_data[idx] = f"Block {idx} data"

            for peer in resp['peers']:
                pid = peer['peer_id']
                self.known_peers[pid] = (peer['ip'], peer['port'])
                self.peer_blocks[pid] = [False] * TOTAL_FILE_BLOCKS

    def send_blocks_info(self):
        for pid, (ip, port) in self.known_peers.items():
            msg = {
                "action": "have_blocks_info",
                "sender_id": self.peer_id,
                "blocks_info": self.blocks_owned
            }
            self.send_message(ip, port, msg)

    def send_message(self, ip, port, msg):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((ip, port))
                s.sendall(json.dumps(msg).encode())
        except Exception as e:
            print(f"{Fore.RED}[{self.peer_id}] Error sending to {ip}:{port} - {e}{Style.RESET_ALL}")

    def get_rarest_blocks(self):
        rarity = {}
        for idx in range(TOTAL_FILE_BLOCKS):
            if not self.blocks_owned[idx]:
                count = sum(1 for blocks in self.peer_blocks.values() if idx < len(blocks) and blocks[idx])
                if count > 0:
                    rarity[idx] = count

        for idx in range(TOTAL_FILE_BLOCKS):
            if not self.blocks_owned[idx] and idx not in rarity:
                rarity[idx] = 9999

        return sorted(rarity, key=lambda k: rarity[k])

    def tit_for_tat(self):
        rarity_count = {}
        rarest_blocks = self.get_rarest_blocks()

        for pid in self.peer_blocks:
            count = sum(1 for block_idx in rarest_blocks if self.peer_blocks[pid][block_idx])
            rarity_count[pid] = count

        sorted_peers = sorted(rarity_count.items(), key=lambda item: item[1], reverse=True)
        fixed_peers = set(pid for pid, count in sorted_peers if count > 0)
        fixed_peers = set(list(fixed_peers)[:4])

        candidates = [pid for pid in self.peer_blocks if pid not in fixed_peers]
        optimistic_peer = {random.choice(candidates)} if candidates else set()

        self.unchoked_peers = fixed_peers.union(optimistic_peer)

        print(f"{Fore.YELLOW}[{self.peer_id}] Unchoked peers: {self.unchoked_peers}{Style.RESET_ALL}")

    def request_block_from_peer(self, target_pid, block_idx):
        if target_pid not in self.known_peers:
            return

        ip, port = self.known_peers[target_pid]
        msg = {
            "action": "request_block",
            "sender_id": self.peer_id,
            "block_index": block_idx
        }
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((ip, port))
                s.sendall(json.dumps(msg).encode())
                data = s.recv(4096)
                resp = json.loads(data.decode())

                if resp["status"] == "success":
                    self.blocks_owned[block_idx] = True
                    self.block_data[block_idx] = resp["block_data"]
                    print(f"{Fore.GREEN}[{self.peer_id}] Received block {block_idx} from {target_pid}{Style.RESET_ALL}")
                    self.announce_block(block_idx)
                else:
                    print(f"{Fore.RED}[{self.peer_id}] Failed to get block {block_idx} from {target_pid}: {resp.get('reason')}{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.RED}[{self.peer_id}] Connection error to {target_pid}: {e}{Style.RESET_ALL}")

    def announce_block(self, block_idx):
        for pid, (ip, port) in self.known_peers.items():
            msg = {
                "action": "announce_block",
                "sender_id": self.peer_id,
                "block_index": block_idx
            }
            self.send_message(ip, port, msg)

    def reconstruct_file(self):
        output_file = f"output_{self.peer_id}.txt"
        with open(output_file, 'w') as f:
            for i in range(TOTAL_FILE_BLOCKS):
                content = self.block_data.get(i, f"[MISSING BLOCK {i}]")
                f.write(content)

        print(f"{Fore.GREEN}[{self.peer_id}] File saved as: {output_file}{Style.RESET_ALL}")

    def update_peers_from_tracker(self):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((TRACKER_HOST, TRACKER_PORT))
                msg = {
                    "action": "get_peers",
                    "peer_id": self.peer_id
                }
                s.sendall(json.dumps(msg).encode())
                data = s.recv(4096)
                resp = json.loads(data.decode())

                for peer in resp['peers']:
                    pid = peer['peer_id']
                    if pid != self.peer_id and pid not in self.known_peers:
                        self.known_peers[pid] = (peer['ip'], peer['port'])


                        blocks_list = peer.get('blocks_owned', [])
                        blocks_bool = [i in blocks_list for i in range(TOTAL_FILE_BLOCKS)]
                        self.peer_blocks[pid] = blocks_bool


                        print(f"{Fore.CYAN}[{self.peer_id}] Discovered peer {pid}{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.RED}[{self.peer_id}] Error contacting tracker: {e}{Style.RESET_ALL}")

    def run(self):
        last_unchoke_time = 0

        while not all(self.blocks_owned):
            print(f"{Fore.MAGENTA}[{self.peer_id}] Current blocks: {self.blocks_owned}{Style.RESET_ALL}")

            self.update_peers_from_tracker()
            self.send_blocks_info()

            now = time.time()
            if now - last_unchoke_time >= 10:
                self.tit_for_tat()
                last_unchoke_time = now

            rarest_blocks = self.get_rarest_blocks()
            block_downloaded = False

            for block_idx in rarest_blocks:
                for pid in self.unchoked_peers:
                    if pid in self.peer_blocks and self.peer_blocks[pid][block_idx]:
                        self.request_block_from_peer(pid, block_idx)
                        if self.blocks_owned[block_idx]:
                            block_downloaded = True
                            break
                if block_downloaded:
                    break

            time.sleep(3)

        self.file_complete = True
        print(f"{Fore.GREEN}[{self.peer_id}] Download complete! Reconstructing file...{Style.RESET_ALL}")
        self.reconstruct_file()

        while True:
            time.sleep(10)

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print(f"{Fore.RED}Usage: python peers_socket.py <peer_id> <listen_port>{Style.RESET_ALL}")
        sys.exit(1)

    peer_id = sys.argv[1]
    port = int(sys.argv[2])

    peer = PeerSocket(peer_id, port)
    threading.Thread(target=peer.listen_for_peers, daemon=True).start()
    time.sleep(1)
    peer.register_with_tracker()
    peer.run()
