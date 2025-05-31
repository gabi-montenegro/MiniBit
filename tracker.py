import socket
import threading
import random
import json
from .serializer import serialize, deserialize
import os


class Tracker():

    def __init__(self):
        self.host = os.getenv("TRACKER_HOST", '127.0.0.1')
        self.port = os.getenv("TRACKER_PORT", 9000)

        self.connected_peers = {} # {peer_id: (ip, port, blocks_owned)}

        # Defina o número total de blocos do arquivo aqui
        self.total_file_blocks = 50 # Exemplo

    def handle_peer_connection(self, conn, addr):
        try:
            # Lógica para receber o registro do peer,
            # enviar blocos iniciais, lidar com solicitações de descoberta de peers
            data = conn.recv(4096)
            message = deserialize(data)

            if message["type"] == "REGISTER":
                peer_id = message["peer_id"]
                listen_port = message["listen_port"]
                # Simular o envio de um subconjunto inicial de blocos
                initial_blocks_count = 2 # Exemplo: cada peer começa com 2 blocos aleatórios
                initial_blocks = random.sample(range(self.total_file_blocks), initial_blocks_count)
                self.connected_peers[peer_id] = {'ip': addr[0], 'port': listen_port, 'blocks_owned': initial_blocks}
                print(f"Peer {peer_id} registrado de {addr[0]}:{listen_port}. Blocos iniciais: {initial_blocks}")

                response = {"status": "success", "initial_blocks": initial_blocks, "peers": list(self.connected_peers.values())}
                conn.sendall(serialize(response))

            elif message["type"] == "GET_PEERS":
                # Retorna uma lista aleatória de peers
                peers_list = list(self.connected_peers.values())
                # Excluir o próprio peer solicitante
                requesting_peer_id = message.get("peer_id")
                filtered_peers = [p for p_id, p in self.connected_peers.items() if p_id != requesting_peer_id] # lista das tuplas [(IP PEER, PORT PEER, [LIST BLOCKS OWNED])]

                if len(filtered_peers) < 5: # [cite: 9]
                    response_peers = filtered_peers
                else:
                    response_peers = random.sample(filtered_peers, k=5) # Retorna um subconjunto aleatório de peers [cite: 8]

                response = {"status": "success", "peers": response_peers}
                conn.sendall(serialize(response))

        except Exception as e:
            print(f"Erro na conexão com o peer {addr}: {e}")
        finally:
            conn.close()

    def start_tracker(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((self.host, self.host))
            s.listen()
            print(f"Tracker listening on {self.host}:{self.host}")
            while True:
                try:
                    conn, addr = s.accept()
                    peer_thread = threading.Thread(target=self.handle_peer_connection, args=(conn, addr), daemon=True)
                    peer_thread.start()
                except KeyboardInterrupt:
                    print("\nTracker closing...")


    

# Para executar o tracker:
if __name__ == "__main__":
    tracker = Tracker()
    tracker.start_tracker()