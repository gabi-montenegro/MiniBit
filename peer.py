import threading
import time
import socket
import json
from colorama import Fore, Style
from peer_server import listen_for_peers
from strategies import tit_for_tat, get_rarest_blocks
from peer_client import register_with_tracker, update_peers_from_tracker, send_blocks_info, request_block_from_peer, request_block_from_tracker

TOTAL_FILE_BLOCKS = 50

class Peer:
    def __init__(self, peer_id, listen_port):
        self.peer_id = peer_id
        self.listen_port = listen_port
        self.TOTAL_FILE_BLOCKS = TOTAL_FILE_BLOCKS

        self.blocks_owned = [False] * TOTAL_FILE_BLOCKS
        self.block_data = {}
        self.known_peers = {}        # {peer_id: (ip, port)}
        self.peer_blocks = {}        # {peer_id: [bool, bool, ...]}
        self.unchoked_peers = set()
        self.fixed_peers = set()
        self.file_complete = False
        self.TRACKER_HOST = '127.0.0.1'
        self.TRACKER_PORT = 9000


    
    def run(self):
        threading.Thread(target=listen_for_peers, args=(self,), daemon=True).start()
        time.sleep(1)
        register_with_tracker(self)

        last_unchoke_time = 0

        while not all(self.blocks_owned):
            print(f"{Fore.MAGENTA}[{self.peer_id}] Blocos atuais: {self.blocks_owned}{Style.RESET_ALL}")

            update_peers_from_tracker(self)
            send_blocks_info(self)

            now = time.time()
            if now - last_unchoke_time >= 10:
                tit_for_tat(self)
                last_unchoke_time = now

            rarest_blocks = get_rarest_blocks(self)
            block_downloaded = False

            # Tenta baixar dos peers unchoked
            for block_idx in rarest_blocks:
                for pid in self.unchoked_peers:
                    if pid in self.peer_blocks and self.peer_blocks[pid][block_idx]:
                        print(f"{Fore.CYAN}[{self.peer_id}] Requesting block {block_idx} from peer {pid}{Style.RESET_ALL}")
                        request_block_from_peer(self, block_idx)
                        if self.blocks_owned[block_idx]:
                            block_downloaded = True
                            break
                if block_downloaded:
                    break

            # Se ninguém tinha, tenta pegar do tracker
            if not block_downloaded:
                for block_idx in rarest_blocks:
                    no_peer_has = all(
                        not blocks[block_idx]
                        for pid, blocks in self.peer_blocks.items()
                        if pid != "tracker"
                    )
                    if no_peer_has and not self.blocks_owned[block_idx]:
                        print(f"{Fore.MAGENTA}[{self.peer_id}] Nobody has block {block_idx}. Requesting from Tracker.{Style.RESET_ALL}")
                        request_block_from_tracker(self, block_idx)
                        break

            time.sleep(3)

        self.file_complete = True
        print(f"{Fore.GREEN}[{self.peer_id}] Download completo! Reconstruindo arquivo...{Style.RESET_ALL}")
        self.reconstruct_file()

        while True:
            time.sleep(10)


    def reconstruct_file(self):
        output_file = f"output_{self.peer_id}.txt"
        with open(output_file, 'w') as f:
            for i in range(TOTAL_FILE_BLOCKS):
                content = self.block_data.get(i, f"[MISSING BLOCK {i}]")
                f.write(content)
        print(f"{Fore.GREEN}[{self.peer_id}] File saved as: {output_file}{Style.RESET_ALL}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print(f"{Fore.RED}Usage: python peer.py <peer_id> <listen_port>{Style.RESET_ALL}")
        sys.exit(1)

    peer_id = sys.argv[1]
    port = int(sys.argv[2])

    peer = Peer(peer_id, port)
    peer.run()
