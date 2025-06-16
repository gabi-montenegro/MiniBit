import socket
import threading
import json
import random
from colorama import Fore, Style, init
import base64

init(autoreset=True)

TOTAL_FILE_BLOCKS = 25

class TrackerSocketServer:
    def __init__(self, host='127.0.0.1', port=9000):
        self.host = host
        self.port = port
        self.connected_peers = {}  # {peer_id: {'ip': str, 'port': int, 'blocks_owned': list}}
        self.blocks_owned = [False] * TOTAL_FILE_BLOCKS
        self.block_data = {}

        self.load_file_blocks("file.txt")



    def load_file_blocks(self, filename):
        try:
            with open(filename, 'rb') as f:
                data = f.read()
            block_size = max(1, len(data) // TOTAL_FILE_BLOCKS)

            for i in range(TOTAL_FILE_BLOCKS):
                start = i * block_size
                end = start + block_size if i < TOTAL_FILE_BLOCKS - 1 else len(data)
                self.block_data[i] = data[start:end].decode('utf-8', errors='ignore')
                self.blocks_owned[i] = True
            print(f"{Fore.GREEN}[TRACKER] Arquivo '{filename}' carregado em {TOTAL_FILE_BLOCKS} blocos.{Style.RESET_ALL}")

        except Exception as e:
            print(f"{Fore.RED}[TRACKER] Erro ao carregar arquivo: {e}{Style.RESET_ALL}")

    def start(self):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.bind((self.host, self.port))
        server_socket.listen(5)
        print(f"{Fore.MAGENTA}[TRACKER] Escutando em {self.host}:{self.port}...{Style.RESET_ALL}")

        while True:
            conn, addr = server_socket.accept()
            threading.Thread(target=self.handle_client, args=(conn, addr)).start()

    def handle_client(self, conn, addr):
        with conn:
            try:
                data = conn.recv(4096)
                if not data:
                    return

                request = json.loads(data.decode())
                action = request.get("action")

                if action == "register":
                    response = self.register_peer(request, addr)
                elif action == "get_peers":
                    response = self.get_peers(request)
                elif action == "request_block_tracker":
                    response = self.handle_block_request(request)
                elif action == "peer_offline":
                    response = self.handle_peer_offline(request)
                else:
                    response = {"status": "error", "message": "Ação desconhecida"}
                    print(f"{Fore.RED}[TRACKER] Ação desconhecida recebida de {addr}{Style.RESET_ALL}")

                conn.sendall(json.dumps(response).encode())

            except Exception as e:
                print(f"{Fore.RED}[TRACKER] Erro ao processar conexão de {addr}: {e}{Style.RESET_ALL}")

    def register_peer(self, data, addr):
        peer_id = data.get("peer_id")
        listen_port = data.get("listen_port")

        if not peer_id or not listen_port:
            print(f"{Fore.RED}[TRACKER] peer_id ou listen_port ausentes na requisição de {addr}{Style.RESET_ALL}")
            return {"status": "error", "message": "peer_id ou listen_port ausentes"}

        # Sorteia alguns blocos iniciais (exemplo: 2 blocos aleatórios)
        initial_blocks_count = 2
        initial_blocks = random.sample(range(TOTAL_FILE_BLOCKS), initial_blocks_count)

        initial_blocks_data = {idx: self.block_data[idx] for idx in initial_blocks}

        self.connected_peers[peer_id] = {
            'ip': addr[0],
            'port': listen_port
        }

        print(f"{Fore.GREEN}[TRACKER] Peer {peer_id} registrado de {addr[0]}:{listen_port} com blocos {initial_blocks}{Style.RESET_ALL}")

        # Envia lista de outros peers (excluindo o próprio peer)
        response_peers = [
            {"peer_id": pid, **peer}
            for pid, peer in self.connected_peers.items()
            if pid != peer_id
        ]

        return {
            "status": "success",
            "initial_blocks": initial_blocks,
            "initial_blocks_data": initial_blocks_data,
            "peers": response_peers
        }

    def get_peers(self, data):
        requesting_peer_id = data.get("peer_id")


        # Primeiro monta a lista de peers, incluindo o tracker
        filtered_peers = [
            {"peer_id": pid, **peer}
            for pid, peer in self.connected_peers.items()
            if pid != requesting_peer_id
        ]


        # Agora faz a seleção: se tem menos de 5, devolve todos; senão, sorteia
        if len(filtered_peers) <= 5:
            selected_peers = filtered_peers
        else:
            selected_peers = random.sample(filtered_peers, k=5)

        print(f"{Fore.CYAN}[TRACKER] Peer {requesting_peer_id} solicitou lista de peers.{Style.RESET_ALL}")

        return {
            "status": "success",
            "peers": selected_peers
        }



    def handle_block_request(self, data):
        block_idx = data.get("block_index")
        sender_id = data.get("sender_id")

        if block_idx is None or sender_id is None:
            return {"status": "error", "message": "Campos faltando na requisição de bloco"}

        if 0 <= block_idx < TOTAL_FILE_BLOCKS and self.blocks_owned[block_idx]:
            print(f"{Fore.GREEN}[TRACKER] Enviando bloco {block_idx} para {sender_id}{Style.RESET_ALL}")
            return {
                "status": "success",
                "block_index": block_idx,
                "block_data": self.block_data[block_idx]
            }
        else:
            print(f"{Fore.RED}[TRACKER] Não possui bloco {block_idx} solicitado por {sender_id}{Style.RESET_ALL}")
            return {
                "status": "error",
                "reason": "Bloco não disponível no tracker"
            }

    # def receive_have_blocks_info(self, data):
    #     peer_id = data.get("sender_id")
    #     blocks_owned = data.get("blocks_owned", [])

    #     if peer_id in self.connected_peers:
    #         self.connected_peers[peer_id]['blocks_owned'] = blocks_owned
    #         return {"status": "success"}
    #     else:
    #         print(f"{Fore.RED}[TRACKER] Peer {peer_id} não registrado tentou enviar have_blocks_info.{Style.RESET_ALL}")
    #         return {"status": "error", "message": "Peer não registrado"}

    # def receive_announce_block(self, data):
    #     peer_id = data.get("sender_id")
    #     block_idx = data.get("block_index")

    #     if peer_id in self.connected_peers and block_idx is not None:
    #         if block_idx not in self.connected_peers[peer_id]['blocks_owned']:
    #             self.connected_peers[peer_id]['blocks_owned'].append(block_idx)
    #             print(f"{Fore.YELLOW}[TRACKER] Peer {peer_id} anunciou novo bloco {block_idx}{Style.RESET_ALL}")
    #         return {"status": "success"}
    #     else:
    #         print(f"{Fore.RED}[TRACKER] Erro ao processar announce_block de {peer_id}{Style.RESET_ALL}")
    #         return {"status": "error", "message": "Erro no announce_block"}

    def handle_peer_offline(self, data):
        dead_peer_id = data.get("dead_peer_id")
        if dead_peer_id and dead_peer_id in self.connected_peers:
            self.connected_peers.pop(dead_peer_id)
            print(f"[TRACKER] Peer {dead_peer_id} removido da lista (offline informado por {data.get('sender_id')})")
            return {"status": "success"}
        else:
            return {"status": "error", "message": "Peer desconhecido ou inválido"}



if __name__ == "__main__":
    tracker = TrackerSocketServer()
    tracker.start()
