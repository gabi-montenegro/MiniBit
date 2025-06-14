import os
import random
import json
import time
import threading
import requests
from flask import Flask, request, jsonify
import sys

# Configuração para o Tracker e portas dos Peers
TRACKER_HOST = os.getenv("TRACKER_HOST", '127.0.0.1')
TRACKER_PORT = int(os.getenv("TRACKER_PORT", 9000))
PEER_LISTEN_PORT_START = 50000
PEER_LISTEN_PORT_END = 60000

# URL base para o tracker
TRACKER_URL = f"http://{TRACKER_HOST}:{TRACKER_PORT}"

class Peer:
    """
    Classe que implementa a funcionalidade de um Peer em um sistema BitTorrent-like,
    usando API REST para comunicação.
    """
    def __init__(self, peer_id, total_blocks, file_name="shared_file.txt"):
        """
        Inicializa um Peer com suas propriedades e configurações.

        Args:
            peer_id (str): Identificador único do peer.
            total_blocks (int): Número total de blocos do arquivo a ser compartilhado.
            file_name (str): Nome do arquivo a ser reconstruído.
        """
        self.peer_id = peer_id
        self.total_blocks = total_blocks
        self.file_name = file_name
        self.blocks_owned = [False] * total_blocks  # Representa se um bloco é possuído
        self.block_data = {}  # Armazena o conteúdo dos blocos
        # {peer_key: {'ip': str, 'port': int, 'blocks_info': list}}
        self.known_peers = {}
        self.listen_port = self._find_available_port()
        self.peer_url = f"http://127.0.0.1:{self.listen_port}" # URL para a própria API REST deste peer

        self.unchoked_peers = set()  # Peers atualmente desbloqueados (podem receber blocos)
        self.choked_peers = set()    # Peers atualmente bloqueados (não podem receber blocos)
        self.optimistic_unchoke = None  # O peer otimista (desbloqueado aleatoriamente)
        self.last_unchoke_time = time.time()  # Para o temporizador tit-for-tat

        self.app = Flask(f"peer_app_{peer_id}") # Cada peer executa sua própria aplicação Flask
        self._setup_peer_api_routes() # Configura as rotas da API para este peer

        # Inicialização de blocos parciais (para simulação)
        self._initialize_partial_blocks()

        # Flag para indicar se o arquivo está completo
        self.file_complete = False

    def _find_available_port(self):
        """
        Encontra uma porta disponível dinamicamente para o servidor Flask do peer.
        """
        return random.randint(PEER_LISTEN_PORT_START, PEER_LISTEN_PORT_END)

    def _setup_peer_api_routes(self):
        """
        Configura todas as rotas da API REST para este peer (servidor).
        """
        self.app.add_url_rule('/request_block', 'request_block_handler', self.request_block_handler, methods=['POST'])
        self.app.add_url_rule('/have_blocks_info', 'have_blocks_info_handler', self.have_blocks_info_handler, methods=['POST'])
        self.app.add_url_rule('/announce_block', 'announce_block_handler', self.announce_block_handler, methods=['POST'])

    def request_block_handler(self):
        """
        Manipulador de requisições POST para /request_block.
        Lida com requisições de blocos de outros peers.
        Verifica se o peer solicitante está desbloqueado e se o bloco é possuído.
        """
        data = request.get_json()
        if not data:
            return jsonify({"type": "ERROR", "message": "JSON inválido", "sender_id": self.peer_id}), 400

        block_idx = data.get("block_index")
        sender_peer_id = data.get("sender_id")

        if block_idx is None or sender_peer_id is None:
            return jsonify({"type": "ERROR", "message": "block_index ou sender_id ausentes", "sender_id": self.peer_id}), 400

        if self.blocks_owned[block_idx] and sender_peer_id in self.unchoked_peers:
            response = {
                "type": "SEND_BLOCK",
                "block_index": block_idx,
                "block_data": self.block_data[block_idx],
                "sender_id": self.peer_id
            }
            print(f"Peer {self.peer_id} enviou bloco {block_idx} para {sender_peer_id}")
            return jsonify(response), 200
        else:
            message = "Bloco não disponível ou peer bloqueado"
            if not self.blocks_owned[block_idx]:
                message = "Bloco não disponível"
            elif sender_peer_id not in self.unchoked_peers:
                message = "Peer bloqueado"
            print(f"Peer {self.peer_id} não enviou bloco {block_idx} para {sender_peer_id} ({message})")
            return jsonify({"type": "ERROR", "message": message, "sender_id": self.peer_id}), 403 # 403 Proibido

    def have_blocks_info_handler(self):
        """
        Manipulador de requisições POST para /have_blocks_info.
        Recebe informações de posse de blocos de outro peer.
        Atualiza as informações de blocos dos peers conhecidos.
        """
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "JSON inválido"}), 400

        remote_blocks = data.get("blocks_info")
        sender_peer_id = data.get("sender_id")

        if remote_blocks is None or sender_peer_id is None:
            return jsonify({"status": "error", "message": "blocks_info ou sender_id ausentes"}), 400

        # Converte o sender_peer_id para a chave usada em self.known_peers
        # Assumindo que o sender_peer_id enviado é a chave que o peer local usa para o peer remoto (ip:port)
        # Para um sistema mais robusto, o sender_peer_id deveria ser o ID único do peer,
        # e o peer local mapearia isso para o ip:port.
        # Por simplicidade na simulação, vamos assumir que o sender_peer_id é o ip:port do remetente.
        # No entanto, para que isso funcione, o peer remetente precisaria enviar seu próprio ip:port como sender_id.
        # Ajuste: A chave em known_peers é "ip:port", então precisamos garantir que o sender_peer_id seja formatado assim.
        # O sender_peer_id na requisição de entrada é o peer_id do remetente (ex: "peer_A").
        # Precisamos encontrar a chave 'ip:port' correspondente em self.known_peers.
        
        # Uma abordagem mais segura seria o peer remoto enviar seu próprio IP e Porta junto com o sender_id.
        # Para este exemplo, vamos simplificar e procurar pelo peer_id dentro dos valores de known_peers.
        found_peer_key = None
        # {peer_key: {'ip': str, 'port': int, 'blocks_info': list}}
        for key, info in self.known_peers.items():
            # Se o peer_id do remetente corresponder ao peer_id que temos em nossos conhecidos
            # e a porta também corresponder (para evitar colisões de ID se IPs forem diferentes)

            # Se a chave eh o ID do Peer, poderia simplesmente fazer key == sender_peer_id
            # Por outro se o serder_id for ip:port,a abordagem eh outra
            if info.get('peer_id') == sender_peer_id:
                found_peer_key = key
                break
        
        if found_peer_key:
            self.known_peers[found_peer_key]['blocks_info'] = remote_blocks
            print(f"Peer {self.peer_id} recebeu informações de blocos de {sender_peer_id}")
            return jsonify({"status": "success"}), 200
        else:
            print(f"Peer {self.peer_id} recebeu informações de blocos de um peer desconhecido: {sender_peer_id}")
            return jsonify({"status": "error", "message": "Peer desconhecido"}), 404

    def announce_block_handler(self):
        """
        Manipulador de requisições POST para /announce_block.
        Recebe um anúncio de que outro peer adquiriu um novo bloco.
        Atualiza as informações de blocos dos peers conhecidos para aquele peer.
        """
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "JSON inválido"}), 400

        block_idx = data.get("block_index")
        sender_peer_id = data.get("sender_id")

        if block_idx is None or sender_peer_id is None:
            return jsonify({"status": "error", "message": "block_index ou sender_id ausentes"}), 400

        found_peer_key = None
        for key, info in self.known_peers.items():
            if info.get('peer_id') == sender_peer_id:
                found_peer_key = key
                break

        if found_peer_key:
            # Atualiza a informação de blocos do peer que enviou o anúncio
            if len(self.known_peers[found_peer_key]['blocks_info']) > block_idx:
                self.known_peers[found_peer_key]['blocks_info'][block_idx] = True
            else:
                # Se a lista de blocos ainda não tem o tamanho certo, ajusta
                self.known_peers[found_peer_key]['blocks_info'].extend(
                    [False] * (block_idx - len(self.known_peers[found_peer_key]['blocks_info']) + 1)
                )
                self.known_peers[found_peer_key]['blocks_info'][block_idx] = True
            print(f"Peer {self.peer_id} soube que {sender_peer_id} tem o bloco {block_idx}")
            return jsonify({"status": "success"}), 200
        else:
            print(f"Peer {self.peer_id} recebeu anúncio de bloco de um peer desconhecido: {sender_peer_id}")
            return jsonify({"status": "error", "message": "Peer desconhecido"}), 404

    def connect_to_tracker(self):
        """
        Registra este peer no tracker e obtém blocos iniciais e a lista de peers.
        Usa requisição HTTP POST.
        """
        try:
            response = requests.post(
                f"{TRACKER_URL}/register",
                json={"peer_id": self.peer_id, "listen_port": self.listen_port}
            )
            response.raise_for_status()  # Levanta uma exceção para erros HTTP (4xx ou 5xx)
            data = response.json()

            if data["status"] == "success":
                for block_idx in data["initial_blocks"]:
                    self.blocks_owned[block_idx] = True
                    self.block_data[block_idx] = f"Conteúdo do bloco {block_idx} recebido do tracker"
                print(f"Peer {self.peer_id} conectado ao tracker. Blocos iniciais do tracker: {data['initial_blocks']}")

                for p_info in data["peers"]:
                    # Não adiciona a si mesmo aos peers conhecidos
                    if p_info['port'] != self.listen_port:
                        # Usa uma chave única para o peer, por exemplo, "ip:port"
                        peer_key = f"{p_info['ip']}:{p_info['port']}"
                        # Adiciona o peer_id ao dicionário p_info para facilitar a busca posterior
                        p_info['peer_id'] = f"peer_{p_info['port']}" # Simplificação para simulação
                        self.known_peers[peer_key] = p_info
                        # Inicializa blocks_info para novos peers conhecidos
                        self.known_peers[peer_key]['blocks_info'] = [False] * self.total_blocks
            else:
                print(f"Erro ao registrar com o tracker: {data['status']}")
        except requests.exceptions.RequestException as e:
            print(f"Erro ao conectar ao tracker: {e}")

    def request_peer_list_from_tracker(self):
        """
        Solicita uma lista atualizada de peers do tracker.
        Usa requisição HTTP GET.
        """
        try:
            response = requests.get(
                f"{TRACKER_URL}/peers",
                params={"peer_id": self.peer_id}
            )
            response.raise_for_status()
            data = response.json()

            if data["status"] == "success":
                for p_info in data["peers"]:
                    if p_info['port'] != self.listen_port:
                        peer_key = f"{p_info['ip']}:{p_info['port']}"
                        if peer_key not in self.known_peers:
                            p_info['peer_id'] = f"peer_{p_info['port']}" # Simplificação para simulação
                            self.known_peers[peer_key] = p_info
                            self.known_peers[peer_key]['blocks_info'] = [False] * self.total_blocks
                print(f"Peer {self.peer_id} atualizou a lista de peers do tracker.")
            else:
                print(f"Erro ao obter a lista de peers do tracker: {data['status']}")
        except requests.exceptions.RequestException as e:
            print(f"Erro ao solicitar lista de peers do tracker: {e}")

    def start_listening_for_peers(self):
        """
        Inicia a aplicação Flask para este peer escutar por requisições de entrada.
        Executada em uma thread separada para não bloquear o loop principal do peer.
        """
        print(f"Peer {self.peer_id} escutando na porta {self.listen_port}")
        # Usa 0.0.0.0 para torná-lo acessível de outras máquinas em uma rede
        self.app.run(host='0.0.0.0', port=self.listen_port, debug=False, use_reloader=False) # use_reloader=False para threads

    def _initialize_partial_blocks(self):
        """Cada peer inicia com um subconjunto aleatório de blocos. ---- Mas quem determina isso é o Tracker!"""
        num_initial_blocks = random.randint(1, self.total_blocks // 4)
        initial_block_indices = random.sample(range(self.total_blocks), num_initial_blocks)
        for idx in initial_block_indices:
            self.blocks_owned[idx] = True
            self.block_data[idx] = f"Conteúdo do bloco {idx} do peer {self.peer_id}"

    def get_rarest_blocks(self):
        """
        Implementa a lógica "rarest first".
        Conta a frequência de cada bloco entre os peers conhecidos que possuem o bloco.
        """
        block_counts = {}
        for block_idx in range(self.total_blocks):
            if not self.blocks_owned[block_idx]:  # Só interessa blocos que não possuo
                count = 0
                for peer_info in self.known_peers.values():
                    if 'blocks_info' in peer_info and block_idx < len(peer_info['blocks_info']) and peer_info['blocks_info'][block_idx]:
                        count += 1
                if count > 0:  # Apenas blocos que pelo menos um peer conhecido tem
                    block_counts[block_idx] = count

        # Ordena os blocos pela frequência (menor frequência primeiro)
        sorted_blocks = sorted(block_counts.items(), key=lambda item: item[1])
        return [block_idx for block_idx, count in sorted_blocks]

    def request_block(self, target_peer_key, block_idx):
        """
        Solicita um bloco específico de um peer alvo.
        Usa requisição HTTP POST.
        """
        target_peer_info = self.known_peers.get(target_peer_key)
        if not target_peer_info:
            print(f"Peer {self.peer_id}: Peer alvo {target_peer_key} não encontrado para o bloco {block_idx}.")
            return

        try:
            response = requests.post(
                f"http://{target_peer_info['ip']}:{target_peer_info['port']}/request_block",
                json={"block_index": block_idx, "sender_id": self.peer_id}
            )
            response.raise_for_status()
            data = response.json()

            if data["type"] == "SEND_BLOCK":
                self.blocks_owned[data["block_index"]] = True
                self.block_data[data["block_index"]] = data["block_data"]
                print(f"Peer {self.peer_id} recebeu bloco {block_idx} de {target_peer_info['ip']}:{target_peer_info['port']}")
                self.announce_block_to_peers(block_idx)  # Anuncia que este peer agora tem o bloco
                if all(self.blocks_owned):
                    self.file_complete = True # Define a flag quando o arquivo está completo
            else:
                print(f"Peer {self.peer_id} falhou ao receber bloco {block_idx} de {target_peer_info['ip']}:{target_peer_info['port']}: {data.get('message', 'Erro desconhecido')}")
        except requests.exceptions.RequestException as e:
            print(f"Erro ao solicitar bloco {block_idx} de {target_peer_info['ip']}:{target_peer_info['port']}: {e}")

    def announce_block_to_peers(self, block_idx):
        """
        Notifica os peers conhecidos que este peer agora possui um novo bloco.
        Usa requisição HTTP POST.
        """
        message = {"block_index": block_idx, "sender_id": self.peer_id}
        for peer_key, peer_info in list(self.known_peers.items()):
            # Não envia para si mesmo
            if peer_info.get('peer_id') == self.peer_id:
                continue
            try:
                requests.post(
                    f"http://{peer_info['ip']}:{peer_info['port']}/announce_block",
                    json=message,
                    timeout=1 # Pequeno timeout para evitar bloqueio
                )
            except requests.exceptions.RequestException as e:
                print(f"Erro ao anunciar bloco {block_idx} para {peer_key}: {e}")

    def send_blocks_info_to_peer(self, target_peer_key):
        """
        Envia a lista completa de blocos que este peer possui para outro peer.
        Usa requisição HTTP POST.
        """
        target_peer_info = self.known_peers.get(target_peer_key)
        if not target_peer_info:
            return

        message = {"blocks_info": self.blocks_owned, "sender_id": self.peer_id}
        try:
            requests.post(
                f"http://{target_peer_info['ip']}:{target_peer_info['port']}/have_blocks_info",
                json=message,
                timeout=1
            )
        except requests.exceptions.RequestException as e:
            print(f"Erro ao enviar informações de blocos para {target_peer_key}: {e}")

    def tit_for_tat_strategy(self):
        """
        Implementa a lógica simplificada "olho por olho".
        Desbloqueia periodicamente um novo peer aleatório (desbloqueio otimista) e
        promove peers com blocos raros para slots de desbloqueio fixos.
        """
        current_time = time.time()
        if current_time - self.last_unchoke_time >= 10:  # A cada 10 segundos
            self.last_unchoke_time = current_time

            # Desbloqueio otimista: desbloqueia um novo peer aleatório
            eligible_peers = [p_id for p_id in self.known_peers if p_id not in self.unchoked_peers]
            if self.optimistic_unchoke and self.optimistic_unchoke in self.unchoked_peers:
                # Remove o desbloqueio otimista anterior se ele ainda estiver desbloqueado
                self.unchoked_peers.discard(self.optimistic_unchoke)
                self.choked_peers.add(self.optimistic_unchoke)

            if eligible_peers:
                self.optimistic_unchoke = random.choice(eligible_peers)
                self.unchoked_peers.add(self.optimistic_unchoke)
                self.choked_peers.discard(self.optimistic_unchoke)
                print(f"Peer {self.peer_id}: Desbloqueio otimista: {self.optimistic_unchoke}")

            # Avalia peers para promoção a "desbloqueados fixos"
            # Prioriza peers que possuem blocos raros que este peer não tem
            peer_rarity_scores = {}
            for peer_key, peer_info in self.known_peers.items():
                if peer_info.get('peer_id') == self.peer_id: continue # Não avalia a si mesmo
                score = 0
                if 'blocks_info' in peer_info:
                    for i in range(self.total_blocks):
                        if not self.blocks_owned[i] and peer_info['blocks_info'][i]:
                            score += 1
                peer_rarity_scores[peer_key] = score # Usa a chave do peer (ip:port) para o score

            # Seleciona os 4 peers com maior pontuação de raridade para serem desbloqueados fixos
            sorted_by_rarity = sorted(peer_rarity_scores.items(), key=lambda item: item[1], reverse=True)
            fixed_unchoked_candidates = [peer_key for peer_key, score in sorted_by_rarity[:4]]

            # Monta o conjunto final de peers desbloqueados
            new_unchoked = set(fixed_unchoked_candidates)
            if self.optimistic_unchoke:
                new_unchoked.add(self.optimistic_unchoke)

            self.unchoked_peers = new_unchoked
            # Todos os outros peers conhecidos que não estão desbloqueados se tornam bloqueados
            self.choked_peers = set(self.known_peers.keys()) - self.unchoked_peers

            print(f"Peer {self.peer_id}: Peers desbloqueados: {self.unchoked_peers}")
            print(f"Peer {self.peer_id}: Peers bloqueados: {self.choked_peers}")

    def reconstruct_file(self):
        """Reconstrói o arquivo completo a partir dos blocos adquiridos."""
        if all(self.blocks_owned):
            output_file_name = f"{self.file_name}_reconstructed_by_{self.peer_id}.txt"
            with open(output_file_name, 'w') as f:
                for i in range(self.total_blocks):
                    f.write(self.block_data[i] + "\n")
            print(f"Peer {self.peer_id} reconstruiu o arquivo completo: {output_file_name}")
            return True
        return False

    def run(self):
        """Loop principal da operação do peer."""
        print(f"Peer {self.peer_id} (Porta: {self.listen_port}) iniciando...")

        # Inicia o servidor Flask para requisições de entrada em uma thread separada
        threading.Thread(target=self.start_listening_for_peers, daemon=True).start()

        # Dá um momento para o servidor Flask iniciar
        time.sleep(2)

        # Conecta ao tracker
        self.connect_to_tracker()

        # Loop principal para solicitar blocos e aplicar tit-for-tat
        while not self.file_complete: # Continua até que o arquivo esteja completo
            self.request_peer_list_from_tracker()  # Periodicamente atualiza a lista de peers

            # Envia informações de blocos para peers conhecidos
            for peer_key in list(self.known_peers.keys()):
                # Evita enviar para si mesmo. A chave 'peer_id' em p_info é uma simplificação.
                # O ideal seria usar o peer_key (ip:port) para identificar unicamente.
                if self.known_peers[peer_key].get('peer_id') != self.peer_id:
                    self.send_blocks_info_to_peer(peer_key)

            rarest_blocks = self.get_rarest_blocks()  # Obtém os blocos mais raros

            # Solicita blocos dos peers desbloqueados
            for block_idx in rarest_blocks:
                if not self.blocks_owned[block_idx]:
                    # Encontra um peer desbloqueado que tenha este bloco
                    for peer_key in list(self.unchoked_peers):
                        if peer_key in self.known_peers:
                            peer_info = self.known_peers[peer_key]
                            if 'blocks_info' in peer_info and \
                               block_idx < len(peer_info['blocks_info']) and \
                               peer_info['blocks_info'][block_idx]:
                                self.request_block(peer_key, block_idx)
                                break  # Solicita um bloco por vez para simplificar

            self.tit_for_tat_strategy()  # Aplica a estratégia tit-for-tat

            time.sleep(1)  # Pequeno atraso para não sobrecarregar

        # Após ter todos os blocos, reconstrói e encerra
        self.reconstruct_file()
        print(f"Peer {self.peer_id} finalizou. Arquivo completo.")

# Exemplo de uso:
if __name__ == "__main__":
    TOTAL_FILE_BLOCKS = 20  # Número total de blocos do arquivo

    if len(sys.argv) < 2:
        print("Uso: python peers.py <peer_id>")
        sys.exit(1)
    
    peer_id_arg = sys.argv[1] # Pega o primeiro argumento como peer_id

    peer = Peer(peer_id=peer_id_arg, total_blocks=TOTAL_FILE_BLOCKS)
    peer.run()
