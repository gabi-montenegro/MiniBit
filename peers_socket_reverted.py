import socket
import threading
import json
import random
import time
from colorama import Fore, Style
import base64
TRACKER_HOST = '127.0.0.1'
TRACKER_PORT = 9000
TOTAL_FILE_BLOCKS = 50 # Este deve ser atualizado pelo tracker quando ele carrega o arquivo

class PeerSocket:
    def __init__(self, peer_id, listen_port):
        self.peer_id = peer_id
        self.listen_port = listen_port
        self.blocks_owned = [False] * TOTAL_FILE_BLOCKS
        self.block_data = {}
        self.known_peers = {}  # {peer_id: (ip, port)}
        self.peer_blocks = {}  # {peer_id: [bool, bool, ...]} - Isso será preenchido por requisições diretas aos peers
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
                # Este é o novo endpoint para peers pedirem a informação de blocos uns aos outros
                self.handle_have_blocks_info_request(conn, msg)
            elif action == "announce_block":
                # Announce_block ainda é útil para peers atualizarem uns aos outros
                if sender in self.peer_blocks and 0 <= msg['block_index'] < TOTAL_FILE_BLOCKS:
                    self.peer_blocks[sender][msg['block_index']] = True
                    print(f"{Fore.CYAN}[{self.peer_id}] Peer {sender} announced block {msg['block_index']}{Style.RESET_ALL}")

    def handle_have_blocks_info_request(self, conn, msg):
        sender_id = msg.get("sender_id")
        response = {
            "status": "success",
            "peer_id": self.peer_id,
            "blocks_info": self.blocks_owned
        }
        print(f"{Fore.CYAN}[{self.peer_id}] Sending own blocks info to {sender_id}{Style.RESET_ALL}")
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

            global TOTAL_FILE_BLOCKS
            print(f"{Fore.GREEN}[{self.peer_id}] Registered. Initial blocks (from tracker): {resp['initial_blocks']}{Style.RESET_ALL}")
            for idx in resp['initial_blocks']: # Se o tracker ainda passa alguns blocos, ele os terá
                self.blocks_owned[idx] = True
                self.block_data[idx] = f"Block {idx} data"

            # O tracker agora envia informações mais simples dos peers
            for peer in resp['peers']:
                pid = peer['peer_id']
                if pid == self.peer_id: # Evita adicionar a si mesmo
                    continue

                self.known_peers[pid] = (peer['ip'], peer['port'])
                if pid == 'tracker': # O tracker ainda pode ter todos os blocos
                    self.peer_blocks[pid] = [True] * TOTAL_FILE_BLOCKS
                else:
                    self.peer_blocks[pid] = [False] * TOTAL_FILE_BLOCKS # Inicializa para peers reais, será preenchido

    # REMOVIDO: send_blocks_info não vai mais para o tracker
    # def send_blocks_info(self):
    #    pass

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
        except Exception: # Captura exceção mais genérica para logging
            print(f"[{self.peer_id}] Falha ao notificar o tracker sobre o peer morto: {dead_peer_id}")


    def get_peer_id_by_address(self, ip, port):
        for pid, (peer_ip, peer_port) in self.known_peers.items():
            if peer_ip == ip and peer_port == port:
                return pid
        return None

    def send_message(self, ip, port, msg):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((ip, port))
                s.sendall(json.dumps(msg).encode())
                # Se for uma requisição de blocos (have_blocks_info), espera a resposta
                if msg.get("action") == "have_blocks_info":
                    data = s.recv(4096)
                    resp = json.loads(data.decode())
                    return resp # Retorna a resposta para quem chamou
                return {"status": "success"} # Para outras mensagens que não esperam resposta de conteúdo
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

    # NOVA FUNÇÃO: Solicitar a lista de blocos de um peer específico
    def request_peer_blocks_info(self, target_pid):
        if target_pid not in self.known_peers:
            return False

        ip, port = self.known_peers[target_pid]
        msg = {
            "action": "have_blocks_info",
            "sender_id": self.peer_id # Quem está pedindo
        }
        print(f"{Fore.CYAN}[{self.peer_id}] Requesting blocks info from {target_pid}{Style.RESET_ALL}")
        response = self.send_message(ip, port, msg) # send_message agora retorna a resposta

        if response and response.get("status") == "success":
            self.peer_blocks[target_pid] = response['blocks_info']
            print(f"{Fore.CYAN}[{self.peer_id}] Received blocks info from {target_pid}{Style.RESET_ALL}")
            return True
        else:
            print(f"{Fore.RED}[{self.peer_id}] Failed to get blocks info from {target_pid}: {response.get('reason', 'Unknown error')}{Style.RESET_ALL}")
            return False


    def get_rarest_blocks(self):
        rarity = {}

        for idx in range(TOTAL_FILE_BLOCKS):
            if not self.blocks_owned[idx]:
                # Conta quantos peers (que já tiveram seus blocos consultados) têm esse bloco
                count = sum(
                    1 for blocks_list in self.peer_blocks.values() # Itera sobre as listas de blocos conhecidas
                    if idx < len(blocks_list) and blocks_list[idx]
                )

                # Se ninguém tem, usa um valor alto (9999)
                rarity[idx] = count if count > 0 else 9999

        # Retorna os blocos ordenados do mais raro para o mais comum
        return sorted(rarity, key=lambda k: rarity[k])


    def tit_for_tat(self):
        rarity_count = {}
        rarest_blocks = self.get_rarest_blocks()

        # Agora, 'peer_blocks' pode conter 'tracker' e outros peers.
        # 'tracker' é uma fonte de todos os blocos, mas não é um peer para "choke/unchoke" normal.
        # Desconsideramos o 'tracker' da lógica de tit-for-tat e choking.
        peers_for_tit_for_tat = [pid for pid in self.peer_blocks if pid != 'tracker']

        # Somente considera peers que já temos informações de blocos.
        # É crucial que request_peer_blocks_info seja chamado antes.
        for pid in peers_for_tit_for_tat:
            if pid in self.peer_blocks: # Certifica-se de que temos a lista de blocos para este peer
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
        # Agora o tracker é tratado como um peer especial que SEMPRE tem blocos.
        # E ele não está sujeito a "choke".
        if target_pid == 'tracker':
            ip, port = TRACKER_HOST, TRACKER_PORT
        elif target_pid in self.known_peers:
            ip, port = self.known_peers[target_pid]
        else:
            print(f"{Fore.RED}[{self.peer_id}] Target peer {target_pid} not in known_peers.{Style.RESET_ALL}")
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
                    # Decode block_data from string back to bytes
                    self.block_data[block_idx] = resp["block_data"]
                    print(f"{Fore.GREEN}[{self.peer_id}] Received block {block_idx} from {target_pid}{Style.RESET_ALL}")
                    self.announce_block(block_idx)
                else:
                    print(f"{Fore.RED}[{self.peer_id}] Failed to get block {block_idx} from {target_pid}: {resp.get('reason')}{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.RED}[{self.peer_id}] Connection error to {target_pid}: {e}{Style.RESET_ALL}")

    def announce_block(self, block_idx):
        # Agora, o announce_block é para avisar os outros peers diretamente
        # (e o tracker, se ele ainda precisar saber para algum propósito, mas a premissa é que não).
        # Para simplificar, vamos enviar para todos os known_peers (exceto o tracker para esta função, se ele não precisar saber).
        # Neste novo modelo, o tracker não precisa ser avisado de cada bloco.
        for pid, (ip, port) in self.known_peers.items():
            if pid != 'tracker': # Não anuncia blocos para o tracker nesta lógica
                msg = {
                    "action": "announce_block",
                    "sender_id": self.peer_id,
                    "block_index": block_idx
                }
                self.send_message(ip, port, msg)

    def reconstruct_file(self):
        output_file = f"output_{self.peer_id}.txt"
        with open(output_file, 'wb') as f: # Abrir em modo binário 'wb' para dados de bloco
            for i in range(TOTAL_FILE_BLOCKS):
                content = self.block_data.get(i)
                if content is None:
                    print(f"[{self.peer_id}] WARNING: Missing block {i} for reconstruction.")
                    # Pode preencher com bytes vazios ou levantar um erro
                    f.write(b'[MISSING BLOCK]\n') # Escreve um placeholder binário
                else:
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

                    if pid == self.peer_id:
                        continue

                    # Novo peer descoberto
                    if pid not in self.known_peers:
                        self.known_peers[pid] = (peer['ip'], peer['port'])
                        print(f"{Fore.CYAN}[{self.peer_id}] Discovered new peer {pid}{Style.RESET_ALL}")
                        
                        # SOLICITAR BLOCOS DO NOVO PEER
                        # Se for o tracker, já temos a info de blocos dele
                        if pid == 'tracker':
                            # O tracker envia blocks_info para si mesmo na resposta do get_peers
                            self.peer_blocks[pid] = peer.get('blocks_info', [True] * TOTAL_FILE_BLOCKS)
                            print(f"{Fore.CYAN}[{self.peer_id}] Received initial blocks info from tracker.{Style.RESET_ALL}")
                        else:
                            # Para outros peers, solicitar a informação de blocos diretamente
                            self.request_peer_blocks_info(pid)
                    # Peer já conhecido, mas talvez precisamos atualizar a lista de blocos dele
                    # ou re-solicitar se estiver desatualizada (aqui, vamos manter a simples,
                    # apenas solicitando na descoberta ou periodicamente no loop principal se necessário)

        except Exception as e:
            print(f"{Fore.RED}[{self.peer_id}] Error contacting tracker: {e}{Style.RESET_ALL}")

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

    def run(self):
        last_unchoke_time = 0
        last_peer_info_update = 0 # Novo contador para atualizar informações de blocos dos peers

        while not all(self.blocks_owned):

            self.update_peers_from_tracker()
            # REMOVIDO: send_blocks_info() - Não envia mais para o tracker

            now = time.time()
            if now - last_unchoke_time >= 10:
                self.tit_for_tat()
                last_unchoke_time = now

            # Nova lógica: Atualiza informações de blocos de peers a cada X segundos
            # Isso é importante porque peers estão sempre adquirindo novos blocos
            if now - last_peer_info_update >= 15: # Exemplo: a cada 15 segundos
                for pid in list(self.known_peers.keys()): # Itera sobre uma cópia, pois pode remover peers
                    if pid != 'tracker': # Não pede ao tracker, pois ele já se auto-anuncia via get_peers
                        self.request_peer_blocks_info(pid)
                last_peer_info_update = now


            rarest_blocks = self.get_rarest_blocks()

            block_downloaded = False

            # Tenta pegar de peers unchoked primeiro
            for block_idx in rarest_blocks:
                for pid in list(self.unchoked_peers): # Itera sobre uma cópia caso o peer saia da lista
                    if pid in self.peer_blocks and self.peer_blocks[pid][block_idx]:
                        print(f"{Fore.CYAN}[{self.peer_id}] Requesting block {block_idx} from peer {pid}{Style.RESET_ALL}")
                        self.request_block_from_peer(pid, block_idx)

                        if self.blocks_owned[block_idx]:
                            block_downloaded = True
                            break

                if block_downloaded:
                    break

            # Se não conseguiu baixar de nenhum peer, tenta o tracker (que é uma fonte primária)
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


            self.log_block_progress()
            self.log_detailed_blocks()
            time.sleep(3)

        self.file_complete = True
        print(f"{Fore.GREEN}[{self.peer_id}] Download completo! Reconstruindo arquivo...{Style.RESET_ALL}")
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