import socket
import threading
import json
import random
import time
from colorama import Fore, Style
import base64


TRACKER_HOST = '127.0.0.1'
TRACKER_PORT = 9000
TOTAL_FILE_BLOCKS = 25 

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
        self.is_running = False

    def listen_for_peers(self):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind(('0.0.0.0', self.listen_port))
        server_socket.listen(5)
        print(f"{Fore.YELLOW}[{self.peer_id}] Escutando na porta {self.listen_port}...{Style.RESET_ALL}")
        self.is_running = True

        while self.is_running:
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
                self.handle_have_blocks_info_request(conn, msg)
            elif action == "announce_block":
                if sender in self.peer_blocks and 0 <= msg['block_index'] < TOTAL_FILE_BLOCKS:
                    self.peer_blocks[sender][msg['block_index']] = True
                    print(f"{Fore.CYAN}[{self.peer_id}] Peer {sender} anunciou bloco {msg['block_index']}{Style.RESET_ALL}")

    def handle_have_blocks_info_request(self, conn, msg):
        sender_id = msg.get("sender_id")
        response = {
            "status": "success",
            "peer_id": self.peer_id,
            "blocks_info": self.blocks_owned
        }
        print(f"{Fore.CYAN}[{self.peer_id}] Enviando informação de blocos para {sender_id}{Style.RESET_ALL}")
        conn.sendall(json.dumps(response).encode())

    def handle_block_request(self, conn, msg):
        block_idx = msg['block_index']
        sender_id = msg['sender_id']

        if self.blocks_owned[block_idx] and sender_id in self.unchoked_peers:
            response = {
                "status": "success",
                "block_index": block_idx,
                "block_data": self.block_data[block_idx]
            }
            print(f"{Fore.GREEN}[{self.peer_id}] Enviando bloco {block_idx} para {sender_id}{Style.RESET_ALL}")
        else:
            response = {"status": "error", "reason": "Choked or block unavailable"}
            print(f"{Fore.RED}[{self.peer_id}] Bloco {block_idx} negado, request de {sender_id} (choked){Style.RESET_ALL}")
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

            global TOTAL_FILE_BLOCKS
            print(f"{Fore.GREEN}[{self.peer_id}] Registrado. Blocos iniciais (do tracker): {resp['initial_blocks']}{Style.RESET_ALL}")
            for idx in resp['initial_blocks']: 
                self.blocks_owned[idx] = True
                self.block_data[idx] = resp['initial_blocks_data'][str(idx)]

        
            for peer in resp['peers']:
                pid = peer['peer_id']
                if pid == self.peer_id: 
                    continue

                self.known_peers[pid] = (peer['ip'], peer['port'])
                self.peer_blocks[pid] = [False] * TOTAL_FILE_BLOCKS 


    def notify_tracker_peer_offline(self, dead_peer_id):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((TRACKER_HOST, TRACKER_PORT))
                msg = {
                    "action": "peer_offline",
                    "dead_peer_id": dead_peer_id,
                    "sender_id": self.peer_id
                }
                s.sendall(json.dumps(msg).encode())
        except Exception: 
            print(f"[{self.peer_id}] Falha ao notificar o tracker sobre o peer morto: {dead_peer_id}")


    def get_peer_id_by_address(self, ip, port):
        for pid, (peer_ip, peer_port) in list(self.known_peers.items()):
            if peer_ip == ip and peer_port == port:
                return pid
        return None

    def send_message(self, ip, port, msg):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((ip, port))
                s.sendall(json.dumps(msg).encode())
                
                if msg.get("action") == "have_blocks_info":
                    data = s.recv(4096)
                    resp = json.loads(data.decode())
                    return resp 
                return {"status": "success"} 
        except ConnectionRefusedError as e:
            target_peer_id = self.get_peer_id_by_address(ip, port)
            if target_peer_id:
                print(f"[{self.peer_id}] Não foi possível conectar ao peer {target_peer_id} ({ip}:{port}). Removendo da lista.")
                self.peer_blocks.pop(target_peer_id, None)
                self.known_peers.pop(target_peer_id, None)
                self.notify_tracker_peer_offline(target_peer_id)
            else:
                print(f"[{self.peer_id}] Não foi possível conectar ao peer desconhecido ({ip}:{port}). Sem ação.")
            return {"status": "error", "reason": "Connection refused"}
        except Exception as e:
            print(f"[{self.peer_id}] Erro ao enviar mensagem para {ip}:{port}: {e}")
            return {"status": "error", "reason": str(e)}

    
    def request_peer_blocks_info(self, target_pid):
        if target_pid not in self.known_peers:
            return False

        ip, port = self.known_peers[target_pid]
        msg = {
            "action": "have_blocks_info",
            "sender_id": self.peer_id 
        }
        print(f"{Fore.CYAN}[{self.peer_id}] Requisitando blocos de {target_pid}{Style.RESET_ALL}")
        response = self.send_message(ip, port, msg) 

        if response and response.get("status") == "success":
            self.peer_blocks[target_pid] = response['blocks_info']
            print(f"{Fore.CYAN}[{self.peer_id}] Recebimento de blocos de {target_pid}{Style.RESET_ALL}")
            return True
        else:
            print(f"{Fore.RED}[{self.peer_id}] Falha ao obter blocos de {target_pid}: {response.get('reason', 'Unknown error')}{Style.RESET_ALL}")
            return False


    def get_rarest_blocks(self):
        rarity = {}

        for idx in range(TOTAL_FILE_BLOCKS):
            if not self.blocks_owned[idx]:
                
                count = sum(
                    1 for blocks_list in self.peer_blocks.values() 
                    if idx < len(blocks_list) and blocks_list[idx]
                )

                # Se ninguém tem, usa um valor alto (9999)
                rarity[idx] = count if count > 0 else 9999

        
        return sorted(rarity, key=lambda k: rarity[k])


    def tit_for_tat(self):
        rarity_count = {}
        rarest_blocks = self.get_rarest_blocks()

        
        peers_for_tit_for_tat = [pid for pid in self.peer_blocks if pid != 'tracker']

        
        for pid in peers_for_tit_for_tat:
            if pid in self.peer_blocks:
                count = sum(1 for block_idx in rarest_blocks if self.peer_blocks[pid][block_idx])
                rarity_count[pid] = count

        sorted_peers = sorted(rarity_count.items(), key=lambda item: item[1], reverse=True)
        fixed_peers = set(pid for pid, count in sorted_peers if count > 0)
        fixed_peers = set(list(fixed_peers)[:4])

        print(f"{Fore.CYAN}[{self.peer_id}] Top peers (fixos) por blocos raros: {sorted_peers}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}[{self.peer_id}] Fixos selecionados: {fixed_peers}{Style.RESET_ALL}")

        candidates = [pid for pid in peers_for_tit_for_tat if pid not in fixed_peers]
        optimistic_peer = set()

        if candidates:
            optimistic_peer = {random.choice(candidates)}
            print(f"{Fore.MAGENTA}[{self.peer_id}] Peer otimista escolhido: {optimistic_peer}{Style.RESET_ALL}")
        else:
            print(f"{Fore.MAGENTA}[{self.peer_id}] Sem candidatos para otimista.{Style.RESET_ALL}")

        self.unchoked_peers = fixed_peers.union(optimistic_peer)

        print(f"{Fore.YELLOW}[{self.peer_id}] Unchoked peers: {self.unchoked_peers}{Style.RESET_ALL}")

    def request_block_from_peer(self, target_pid, block_idx):
        if target_pid in self.known_peers:
            ip, port = self.known_peers[target_pid]
        else:
            print(f"{Fore.RED}[{self.peer_id}] Peer {target_pid} não conhecido.{Style.RESET_ALL}")
            return

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
                    print(f"{Fore.GREEN}[{self.peer_id}] Recebimento do bloco {block_idx} do {target_pid}{Style.RESET_ALL}")
                    self.announce_block(block_idx)
                else:
                    print(f"{Fore.RED}[{self.peer_id}] Falha ao obter bloco {block_idx} do {target_pid}: {resp.get('reason')}{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.RED}[{self.peer_id}] Erro ao se conectar com {target_pid}: {e}{Style.RESET_ALL}")


    def request_block_from_tracker(self, block_idx):
        msg = {
            "action": "request_block_tracker",
            "sender_id": self.peer_id,
            "block_index": block_idx
        }
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((TRACKER_HOST, TRACKER_PORT))
                s.sendall(json.dumps(msg).encode())
                data = s.recv(4096)
                resp = json.loads(data.decode())

                if resp["status"] == "success":
                    self.blocks_owned[block_idx] = True
                    self.block_data[block_idx] = resp["block_data"]
                    print(f"{Fore.GREEN}[{self.peer_id}] Recebimento de bloco {block_idx} do tracker{Style.RESET_ALL}")
                    self.announce_block(block_idx)
                else:
                    print(f"{Fore.RED}[{self.peer_id}] Falha ao obter bloco {block_idx} do tracker: {resp.get('reason')}{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.RED}[{self.peer_id}] Erro de conexão ao tracker: {e}{Style.RESET_ALL}")

    def announce_block(self, block_idx):
        for pid, (ip, port) in list(self.known_peers.items()):
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
                content = self.block_data.get(i)
                if content is None:
                    print(f"[{self.peer_id}] WARNING: Bloco {i} faltante para reconstrução.")
                    f.write('[MISSING BLOCK]\n')
                else:
                    f.write(content)

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

                    if pid == self.peer_id:
                        continue

                    
                    if pid not in list(self.known_peers):
                        self.known_peers[pid] = (peer['ip'], peer['port'])
                        print(f"{Fore.CYAN}[{self.peer_id}] Novo peer descoberto: {pid}{Style.RESET_ALL}")
                        self.request_peer_blocks_info(pid)

        except Exception as e:
            print(f"{Fore.RED}[{self.peer_id}] Erro ao se conectar com o tracker: {e}{Style.RESET_ALL}")

    def log_block_progress(self):
        total = TOTAL_FILE_BLOCKS
        owned = sum(1 for b in self.blocks_owned if b)
        percent = (owned / total) * 100

        filled = int(percent / 2)
        bar = f"[{'#' * filled}{'.' * (50 - filled)}]"

        print(f"{Fore.BLUE}[{self.peer_id}] Progresso: {owned}/{total} blocos ({percent:.2f}%) {bar}{Style.RESET_ALL}")

    def log_detailed_blocks(self):
        status = ''.join(['█' if b else '.' for b in self.blocks_owned])
        print(f"{Fore.YELLOW}[{self.peer_id}] Blocos: {status}{Style.RESET_ALL}")

    def shutdown(self):
        print(f"{Fore.RED}[{self.peer_id}] Iniciando desligamento controlado...{Style.RESET_ALL}")
        self.is_running = False 

        self.notify_tracker_peer_offline(self.peer_id)

        time.sleep(1) 
        
        print(f"{Fore.RED}[{self.peer_id}] Desligamento do peer completo.{Style.RESET_ALL}")
        sys.exit(0)

    def run(self):
        last_unchoke_time = 0
        last_peer_info_update = 0 

        while not all(self.blocks_owned):

            self.update_peers_from_tracker()

            now = time.time()
            if now - last_unchoke_time >= 10:
                self.tit_for_tat()
                last_unchoke_time = now

            
            if now - last_peer_info_update >= 15: 
                for pid in list(self.known_peers.keys()):
                    self.request_peer_blocks_info(pid)
                last_peer_info_update = now


            rarest_blocks = self.get_rarest_blocks()

            block_downloaded = False

            for block_idx in rarest_blocks:
                for pid in list(self.unchoked_peers): 
                    if pid in self.peer_blocks and self.peer_blocks[pid][block_idx]:
                        print(f"{Fore.CYAN}[{self.peer_id}] Requisitando bloco {block_idx} do peer {pid}{Style.RESET_ALL}")
                        self.request_block_from_peer(pid, block_idx)

                        if self.blocks_owned[block_idx]:
                            block_downloaded = True
                            break

                if block_downloaded:
                    break

            # Se não conseguiu baixar de nenhum peer, tenta o tracker 
            if not block_downloaded:
                for block_idx in rarest_blocks:
                    no_peer_has = all(
                        not blocks[block_idx]
                        for pid, blocks in self.peer_blocks.items()
                    )
                    if no_peer_has and not self.blocks_owned[block_idx]:
                        print(f"{Fore.MAGENTA}[{self.peer_id}] Nenhum peer tem o bloco {block_idx}. Requisitando ao Tracker.{Style.RESET_ALL}")
                        self.request_block_from_tracker(block_idx)
                        break


            self.log_block_progress()
            self.log_detailed_blocks()
            time.sleep(3)
            
        self.file_complete = True
        print(f"{Fore.GREEN}[{self.peer_id}] Download completo! Reconstruindo arquivo...{Style.RESET_ALL}")
        self.reconstruct_file()
        self.shutdown()

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