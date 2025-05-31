# MiniBit
Implementação de um sistema de compartilhamento cooperativo de arquivos com estratégias distribuídas.

## Estrutura Inicial
- tracker.py
- peers.py
- serializer.py

## Trackers
Coordena o registro e consulta de peers. Na consulta de peers, se houver menos de 5 peers, todos os peers (exceto o peer que está solicitando a listagem) são enviados.

É composto por uma classe que contém os seguintes atributos:
1. self.host: Variável de ambiente que possui o host do tracker, 127.0.0.1 de fallback.

2. self.port: Variável de ambiente quecontém a porta do tracker, 9000 de fallback.

3. self.connected_peers: Dicionário de tuplas para armazenar informações sobre todos os peers atualmente registrados no Tracker. A chave consiste no ID do Peer e a tupla contém IP, porta e uma lista de blocos pertencentes do Peer. ´{peer_id: (ip, port, [blocks_owned])}´

4. self.total_file_blocks: Inteiro que contém o total de blocos do arquivo.

O programa principal consiste na instanciação da classe do Tracker e chamada à função start_tracker.

### Métodos de Classe
#### start_tracker(self): 
- Propósito: Inicia o servidor do Tracker. 

- Funcionalidade: Entra em loop infinito com criação de Threads para aceitar múltiplas conexões. Para cada conexão aceita, cria uma nova thread (handle_peer_connection) para lidar com a comunicação com aquele peer, permitindo que o Tracker gerencie múltiplos peers simultaneamente.

#### handle_peer_connection(self, conn, addr)
- Propósito: Gerencia as conexões de entrada de peers e as mensagens que eles enviam ao Tracker.

- Funcionalidade:
Recebe e desserializa a mensagem recebida. A mensagem consiste em dois tipos:
1. REGISTER:  Se a mensagem for um registro (REGISTER), extrai o peer_id e a listen_port. Simula a atribuição de alguns "blocos iniciais" aleatórios para este peer. Armazena as informações do peer em Tracker.connected_peers (dicionário de peers atualmente registrados). Envia uma resposta de success contendo os blocos iniciais atribuídos e a lista de todos os peers atualmente conectados.

2. GET_PEERS: Se a mensagem for uma solicitação de lista de peers (GET_PEERS), filtra a lista Tracker.connected_peers para excluir o peer solicitante. Se houver menos de 5 peers restantes, retorna todos eles. Caso contrário, retorna um subconjunto aleatório de 5 peers. Envia uma resposta de success com a lista filtrada de peers. Lista de tuplas com os peers no seguinte formato: [(IP PEER, PORT PEER, [LIST BLOCKS OWNED])]





