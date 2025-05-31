import socket
import threading
import random
import json
import time
import os

TRACKER_HOST = '127.0.0.1'
TRACKER_PORT = 9000
PEER_LISTEN_PORT_START = 50000 # Faixa de portas para peers
PEER_LISTEN_PORT_END = 60000

class Peer:
    def __init__(self, peer_id, total_blocks, file_name="shared_file.txt"):
        self.peer_id = peer_id
        self.total_blocks = total_blocks
        self.file_name = file_name
        self.blocks_owned = [False] * total_blocks # Representa se um bloco é possuído [cite: 4]
        self.block_data = {} # Armazena o conteúdo dos blocos
        self.known_peers = {} # {peer_id: {'ip': str, 'port': int, 'blocks_info': list}}
        self.listen_port = self._find_available_port()

        self.unchoked_peers = set() # Peers atualmente desbloqueados
        self.choked_peers = set() # Peers atualmente bloqueados
        self.optimistic_unchoke = None # O peer otimista
        self.last_unchoke_time = time.time() # Para o temporizador tit-for-tat [cite: 11]

        # Inicialização de blocos parciais (para simulação)
        self._initialize_partial_blocks()

    def _find_available_port(self):
        # Encontra uma porta disponível dinamicamente
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        for port in range(PEER_LISTEN_PORT_START, PEER_LISTEN_PORT_END + 1):
            try:
                s.bind(('0.0.0.0', port))
                s.close()
                return port
            except OSError:
                continue
        raise Exception("No available ports found!")

    def _initialize_partial_blocks(self):
        # Cada peer inicia com um subconjunto aleatório dos blocos [cite: 4]
        num_initial_blocks = random.randint(1, self.total_blocks // 4) # Exemplo: 1/4 dos blocos
        initial_block_indices = random.sample(range(self.total_blocks), num_initial_blocks)
        for idx in initial_block_indices:
            self.blocks_owned[idx] = True
            self.block_data[idx] = f"Conteúdo do bloco {idx} do peer {self.peer_id}" # Simular conteúdo

    def connect_to_tracker(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((TRACKER_HOST, TRACKER_PORT))
            message = {"type": "REGISTER", "peer_id": self.peer_id, "listen_port": self.listen_port}
            s.sendall(json.dumps(message).encode('utf-8'))
            response_data = s.recv(4096).decode('utf-8')
            response = json.loads(response_data)
            if response["status"] == "success":
                # O tracker enviará blocos iniciais (simulado) [cite: 5]
                for block_idx in response["initial_blocks"]:
                    self.blocks_owned[block_idx] = True
                    self.block_data[block_idx] = f"Conteúdo do bloco {block_idx} recebido do tracker"
                print(f"Peer {self.peer_id} conectado ao tracker. Blocos iniciais do tracker: {response['initial_blocks']}")
                for p_info in response["peers"]:
                    if p_info['port'] != self.listen_port: # Não adiciona a si mesmo [cite: 8]
                        self.known_peers[f"peer_{p_info['port']}"] = p_info # Usando a porta como ID temporário para simulação
                        # Na vida real, o tracker também daria a informação de blocos do peer.
                        # Aqui, vamos adicionar uma lista vazia e atualizar depois.
                        self.known_peers[f"peer_{p_info['port']}"]['blocks_info'] = [False] * self.total_blocks
            else:
                print(f"Erro ao registrar no tracker: {response['status']}")

    def request_peer_list_from_tracker(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((TRACKER_HOST, TRACKER_PORT))
            message = {"type": "GET_PEERS", "peer_id": self.peer_id}
            s.sendall(json.dumps(message).encode('utf-8'))
            response_data = s.recv(4096).decode('utf-8')
            response = json.loads(response_data)
            if response["status"] == "success":
                for p_info in response["peers"]:
                    if p_info['port'] != self.listen_port:
                        self.known_peers[f"peer_{p_info['port']}"] = p_info
                        self.known_peers[f"peer_{p_info['port']}"]['blocks_info'] = [False] * self.total_blocks # Inicializa
                print(f"Peer {self.peer_id} atualizou lista de peers do tracker.")
            else:
                print(f"Erro ao obter lista de peers do tracker: {response['status']}")

    def start_listening_for_peers(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # Reutiliza o endereço
            s.bind(('0.0.0.0', self.listen_port))
            s.listen()
            print(f"Peer {self.peer_id} listening on port {self.listen_port}")
            while not all(self.blocks_owned): # Continua ouvindo enquanto não tem o arquivo completo
                try:
                    conn, addr = s.accept()
                    peer_handler_thread = threading.Thread(target=self.handle_incoming_peer_connection, args=(conn, addr))
                    peer_handler_thread.start()
                except socket.timeout:
                    continue # Permite que o loop verifique a condição de encerramento
            print(f"Peer {self.peer_id} concluiu o arquivo e parou de ouvir.")

    def handle_incoming_peer_connection(self, conn, addr):
        try:
            data = conn.recv(4096).decode('utf-8')
            message = json.loads(data)
            sender_peer_id = message.get("sender_id", f"{addr[0]}:{addr[1]}") # Identifica o remetente

            if message["type"] == "REQUEST_BLOCK":
                block_idx = message["block_index"]
                if self.blocks_owned[block_idx] and sender_peer_id in self.unchoked_peers: # Verifica se está desbloqueado [cite: 15]
                    response = {
                        "type": "SEND_BLOCK",
                        "block_index": block_idx,
                        "block_data": self.block_data[block_idx],
                        "sender_id": self.peer_id
                    }
                    conn.sendall(json.dumps(response).encode('utf-8'))
                    print(f"Peer {self.peer_id} enviou bloco {block_idx} para {sender_peer_id}")
                else:
                    response = {"type": "ERROR", "message": "Block not available or peer choked", "sender_id": self.peer_id}
                    conn.sendall(json.dumps(response).encode('utf-8'))
                    print(f"Peer {self.peer_id} não enviou bloco {block_idx} para {sender_peer_id} (choked ou não tem)")

            elif message["type"] == "HAVE_BLOCKS_INFO":
                # Outro peer enviou a lista de blocos que ele possui
                remote_blocks = message["blocks_info"]
                if sender_peer_id in self.known_peers:
                    self.known_peers[sender_peer_id]['blocks_info'] = remote_blocks
                print(f"Peer {self.peer_id} recebeu info de blocos de {sender_peer_id}")

            elif message["type"] == "ANNOUNCE_BLOCK":
                block_idx = message["block_index"]
                if sender_peer_id in self.known_peers:
                    # Atualiza a info de blocos do peer que enviou o anúncio
                    if len(self.known_peers[sender_peer_id]['blocks_info']) > block_idx:
                        self.known_peers[sender_peer_id]['blocks_info'][block_idx] = True
                    else: # Se a lista de blocos ainda não tem o tamanho certo, ajusta
                        self.known_peers[sender_peer_id]['blocks_info'].extend([False] * (block_idx - len(self.known_peers[sender_peer_id]['blocks_info']) + 1))
                        self.known_peers[sender_peer_id]['blocks_info'][block_idx] = True
                print(f"Peer {self.peer_id} soube que {sender_peer_id} tem bloco {block_idx}")

        except Exception as e:
            print(f"Erro ao lidar com conexão de {addr}: {e}")
        finally:
            conn.close()

    def get_rarest_blocks(self):
        # Implementa a lógica "rarest first" [cite: 10]
        # Conta a frequência de cada bloco entre os peers conhecidos que possuem o bloco
        block_counts = {}
        for block_idx in range(self.total_blocks):
            if not self.blocks_owned[block_idx]: # Só interessa blocos que não possuo
                count = 0
                for peer_info in self.known_peers.values():
                    # Verifica se o peer tem info de blocos e se ele possui o bloco
                    if 'blocks_info' in peer_info and block_idx < len(peer_info['blocks_info']) and peer_info['blocks_info'][block_idx]:
                        count += 1
                if count > 0: # Apenas blocos que pelo menos um peer conhecido tem
                    block_counts[block_idx] = count

        # Ordena os blocos pela frequência (menor frequência primeiro)
        sorted_blocks = sorted(block_counts.items(), key=lambda item: item[1])
        return [block_idx for block_idx, count in sorted_blocks]

    def request_block(self, target_peer_info, block_idx):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((target_peer_info['ip'], target_peer_info['port']))
                message = {
                    "type": "REQUEST_BLOCK",
                    "block_index": block_idx,
                    "sender_id": self.peer_id
                }
                s.sendall(json.dumps(message).encode('utf-8'))
                response_data = s.recv(4096).decode('utf-8')
                response = json.loads(response_data)

                if response["type"] == "SEND_BLOCK":
                    self.blocks_owned[response["block_index"]] = True
                    self.block_data[response["block_index"]] = response["block_data"]
                    print(f"Peer {self.peer_id} recebeu bloco {block_idx} de {target_peer_info['ip']}:{target_peer_info['port']}")
                    self.announce_block_to_peers(block_idx) # Anuncia que agora tem o bloco
                else:
                    print(f"Peer {self.peer_id} falhou ao receber bloco {block_idx} de {target_peer_info['ip']}:{target_peer_info['port']}: {response.get('message', 'Erro desconhecido')}")
        except Exception as e:
            print(f"Erro ao solicitar bloco {block_idx} de {target_peer_info['ip']}:{target_peer_info['port']}: {e}")

    def announce_block_to_peers(self, block_idx):
        # Notifica peers conhecidos que este peer agora possui um novo bloco
        message = {"type": "ANNOUNCE_BLOCK", "block_index": block_idx, "sender_id": self.peer_id}
        for peer_id, peer_info in self.known_peers.items():
            if peer_id == self.peer_id: # Não envia para si mesmo
                continue
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.connect((peer_info['ip'], peer_info['port']))
                    s.sendall(json.dumps(message).encode('utf-8'))
            except Exception as e:
                print(f"Erro ao anunciar bloco {block_idx} para {peer_id}: {e}")

    def send_blocks_info_to_peer(self, target_peer_info):
        # Envia a lista completa de blocos que este peer possui para outro peer
        message = {"type": "HAVE_BLOCKS_INFO", "blocks_info": self.blocks_owned, "sender_id": self.peer_id}
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((target_peer_info['ip'], target_peer_info['port']))
                s.sendall(json.dumps(message).encode('utf-8'))
        except Exception as e:
            print(f"Erro ao enviar info de blocos para {target_peer_info['ip']}:{target_peer_info['port']}: {e}")

    def tit_for_tat_strategy(self):
        # Implementa a lógica "olho por olho" simplificada [cite: 11]
        current_time = time.time()
        if current_time - self.last_unchoke_time >= 10: # A cada 10 segundos [cite: 11]
            self.last_unchoke_time = current_time

            # Desbloqueia um novo peer aleatório [cite: 11]
            eligible_peers = [p_id for p_id in self.known_peers if p_id not in self.unchoked_peers]
            if self.optimistic_unchoke and self.optimistic_unchoke in self.unchoked_peers:
                # Remove o otimista anterior se ele ainda estiver na lista de unchoked
                self.unchoked_peers.discard(self.optimistic_unchoke)
                self.choked_peers.add(self.optimistic_unchoke)

            if eligible_peers:
                self.optimistic_unchoke = random.choice(eligible_peers)
                self.unchoked_peers.add(self.optimistic_unchoke)
                self.choked_peers.discard(self.optimistic_unchoke)
                print(f"Peer {self.peer_id}: Optimistic unchoke: {self.optimistic_unchoke}")

            # Avalia peers para promoção a "unchoked fixos" [cite: 12, 13]
            # Prioriza peers que possuem blocos raros que este peer não tem
            # Calcula a "raridade" de cada peer (quantos blocos raros ele tem que eu não tenho)
            peer_rarity_scores = {}
            for peer_id, peer_info in self.known_peers.items():
                if peer_id == self.peer_id: continue
                score = 0
                if 'blocks_info' in peer_info:
                    for i in range(self.total_blocks):
                        if not self.blocks_owned[i] and peer_info['blocks_info'][i]:
                            # Contar blocos raros que o outro peer tem e eu não tenho
                            # Para uma lógica mais robusta, você precisaria de uma contagem global de raridade
                            # Aqui, simplificamos contando o número de blocos que ele tem e eu não.
                            score += 1
                peer_rarity_scores[peer_id] = score

            # Seleciona os 4 peers com maior pontuação de raridade para serem fixos [cite: 13]
            sorted_by_rarity = sorted(peer_rarity_scores.items(), key=lambda item: item[1], reverse=True)
            fixed_unchoked_candidates = [peer_id for peer_id, score in sorted_by_rarity[:4]]

            # Monta o conjunto final de unchoked
            new_unchoked = set(fixed_unchoked_candidates)
            if self.optimistic_unchoke:
                new_unchoked.add(self.optimistic_unchoke)

            self.unchoked_peers = new_unchoked
            self.choked_peers = set(self.known_peers.keys()) - self.unchoked_peers

            print(f"Peer {self.peer_id}: Unchoked peers: {self.unchoked_peers}")
            print(f"Peer {self.peer_id}: Choked peers: {self.choked_peers}")


    def reconstruct_file(self):
        # Reconstroi o arquivo completo a partir dos blocos
        if all(self.blocks_owned):
            output_file_name = f"{self.file_name}_reconstructed_by_{self.peer_id}.txt"
            with open(output_file_name, 'w') as f:
                for i in range(self.total_blocks):
                    f.write(self.block_data[i] + "\n")
            print(f"Peer {self.peer_id} reconstruiu o arquivo completo: {output_file_name}")
            return True
        return False

    def run(self):
        print(f"Peer {self.peer_id} (Porta: {self.listen_port}) iniciando...")
        # Inicia a escuta por conexões de entrada em uma thread separada
        threading.Thread(target=self.start_listening_for_peers).start()
        
        # Conecta ao tracker
        self.connect_to_tracker()
        
        # Loop principal para solicitar blocos e aplicar tit-for-tat
        while not all(self.blocks_owned): # Enquanto o arquivo não estiver completo [cite: 17]
            self.request_peer_list_from_tracker() # Periodicamente atualiza a lista de peers

            # Envia suas informações de blocos para peers conhecidos
            for peer_id, peer_info in list(self.known_peers.items()):
                if peer_id != self.peer_id:
                    self.send_blocks_info_to_peer(peer_info)

            rarest_blocks = self.get_rarest_blocks() # Obtém os blocos mais raros [cite: 10]
            
            # Solicita blocos dos peers unchoked
            for block_idx in rarest_blocks:
                if not self.blocks_owned[block_idx]:
                    # Encontrar um peer unchoked que tenha este bloco
                    for peer_id in list(self.unchoked_peers):
                        if peer_id in self.known_peers:
                            peer_info = self.known_peers[peer_id]
                            if 'blocks_info' in peer_info and block_idx < len(peer_info['blocks_info']) and peer_info['blocks_info'][block_idx]:
                                self.request_block(peer_info, block_idx)
                                break # Solicita um bloco por vez para simplificar

            self.tit_for_tat_strategy() # Aplica a estratégia tit-for-tat [cite: 11]

            time.sleep(1) # Pequeno atraso para não sobrecarregar

        # Após ter todos os blocos, tenta reconstruir e encerra [cite: 17]
        self.reconstruct_file()
        print(f"Peer {self.peer_id} encerrou. Arquivo completo.")

# Exemplo de uso:
if __name__ == "__main__":
    # Para simular, você pode iniciar o tracker em um terminal e os peers em outros.
    # Certifique-se de que o TOTAL_FILE_BLOCKS no tracker e nos peers seja o mesmo.
    TOTAL_FILE_BLOCKS = 20 # Número total de blocos do arquivo
    
    # Exemplo de como iniciar um peer
    # No seu ambiente de execução, você precisaria de um script para iniciar múltiplos peers
    # e um para iniciar o tracker.
    
    # Peer 1
    # peer1 = Peer(peer_id="peer_A", total_blocks=TOTAL_FILE_BLOCKS)
    # peer1_thread = threading.Thread(target=peer1.run)
    # peer1_thread.start()

    # Peer 2
    # peer2 = Peer(peer_id="peer_B", total_blocks=TOTAL_FILE_BLOCKS)
    # peer2_thread = threading.Thread(target=peer2.run)
    # peer2_thread.start()

    # E assim por diante para 3-5 peers.
    # O tracker deve ser iniciado primeiro.
    pass # Remova esta linha para executar o exemplo