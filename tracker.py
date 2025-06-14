import os
import random
from flask import Flask, request, jsonify
import threading

class TrackerApp:
    """
    Classe que implementa o servidor Tracker usando Flask, seguindo o paradigma de Orientação a Objetos.
    Gerencia o registro de peers e a distribuição de suas informações.
    """
    def __init__(self, host='127.0.0.1', port=9000, total_file_blocks=50):
        """
        Inicializa a aplicação Flask do Tracker e seu estado interno.

        Args:
            host (str): O host em que o tracker irá escutar.
            port (int): A porta em que o tracker irá escutar.
            total_file_blocks (int): O número total de blocos do arquivo a ser compartilhado.
        """
        self.app = Flask(__name__)
        self.host = os.getenv("TRACKER_HOST", host)
        self.port = int(os.getenv("TRACKER_PORT", port))
        self.total_file_blocks = 20

        # {peer_id: {'ip': str, 'port': int, 'blocks_owned': list}}
        self.connected_peers = {}

        # Configura as rotas da API REST
        self._setup_routes()

    def _setup_routes(self):
        """
        Configura todas as rotas da API REST para o Tracker.
        """
        self.app.add_url_rule('/register', 'register_peer', self.register_peer, methods=['POST'])
        self.app.add_url_rule('/peers', 'get_peers', self.get_peers, methods=['GET'])

    def register_peer(self):
        """
        Endpoint para registrar um novo peer no tracker.
        Recebe um payload JSON com 'peer_id' e 'listen_port'.
        Atribui blocos iniciais aleatórios ao peer e retorna uma lista de peers conhecidos.
        """
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "JSON inválido"}), 400

        peer_id = data.get("peer_id")
        listen_port = data.get("listen_port")
        peer_ip = request.remote_addr # Obtém o endereço IP do peer que fez a requisição

        if not peer_id or not listen_port:
            return jsonify({"status": "error", "message": "peer_id ou listen_port ausentes"}), 400

        # Simula a atribuição de blocos iniciais aleatórios
        initial_blocks_count = 2  # Cada peer começa com 2 blocos aleatórios
        initial_blocks = random.sample(range(self.total_file_blocks), initial_blocks_count)

        self.connected_peers[peer_id] = {
            'ip': peer_ip,
            'port': listen_port,
            'blocks_owned': initial_blocks # O tracker mantém uma visão simplificada dos blocos
        }
        print(f"Peer {peer_id} registrado de {peer_ip}:{listen_port}. Blocos iniciais: {initial_blocks}")

        # Retorna os blocos iniciais e a lista atual de peers conectados (excluindo o próprio)
        peers_list = list(self.connected_peers.values())
        response_peers = [p for p in peers_list if p['port'] != listen_port] # Exclui o peer que está se registrando
        return jsonify({
            "status": "success",
            "initial_blocks": initial_blocks,
            "peers": response_peers
        }), 200

    def get_peers(self):
        """
        Endpoint para retornar uma lista de peers conhecidos ao peer solicitante.
        Opcionalmente aceita 'peer_id' para excluir o peer solicitante da lista.
        Retorna um subconjunto aleatório de até 5 peers se houver mais disponíveis.
        """
        requesting_peer_id = request.args.get("peer_id")

        filtered_peers = [
            p for p_id, p in self.connected_peers.items()
            if p_id != requesting_peer_id
        ]

        if len(filtered_peers) < 5:
            response_peers = filtered_peers
        else:
            response_peers = random.sample(filtered_peers, k=5)

        return jsonify({"status": "success", "peers": response_peers}), 200

    def run(self):
        """
        Inicia a aplicação Flask do Tracker.
        """
        print(f"Tracker escutando em {self.host}:{self.port}")
        # Usa 0.0.0.0 para torná-lo acessível de outras máquinas em uma rede
        self.app.run(host='0.0.0.0', port=self.port, debug=False)

if __name__ == "__main__":
    tracker = TrackerApp()
    tracker.run()
