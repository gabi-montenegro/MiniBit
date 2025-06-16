
# MiniBit

Implementação de um sistema de compartilhamento cooperativo de arquivos com estratégias distribuídas.

## Estrutura

- `tracker.py`
- `peers.py`
- `file.txt`
- `run_all_linux.sh`
- `run_all_windows.bat`
- `logs/`

## Como rodar

### Pré-requisitos

- Python (versão 3.8 ou superior)

### Passo a Passo

1. Abra um terminal e execute o Tracker:

```bash
python tracker.py
```

2. Abra outro terminal e execute o Peer. Você precisará fornecer um `peer_id` e uma `listen_port`:

```bash
python peer.py <peer_id> <listen_port>
```

**Exemplo:**

```bash
python peer.py peer1 5001
```

---

3. (Opcional) É possível iniciar o Tracker e vários Peers automaticamente executando os scrips: `run_all_windows.bat`(Windows) ou `run_all_linux.sh`(Linux/macOS). Acesse a área de configuração dos scripts para definir os parâmetros de execução.

## Tracker

O Tracker é implementado como um servidor de socket TCP em `tracker_socket.py`, encapsulado na classe `TrackerSocketServer`. Ele coordena o registro e a consulta de peers, bem como a manipulação de requisições de blocos (somente quando nenhum peer tiver o bloco).

### Principais Atributos da Classe `TrackerSocketServer`

- `self.host`: Host de escuta (padrão: `127.0.0.1`)
- `self.port`: Porta de escuta (padrão: `9000`)
- `self.connected_peers`: Dicionário com informações dos peers conectados
- `self.blocks_owned`: Lista booleana indicando posse de blocos (Tracker possui todos)
- `self.block_data`: Dicionário com o conteúdo dos blocos do arquivo completo

### Métodos Principais

- `__init__(self, host='127.0.0.1', port=9000)`: Inicializa o Tracker e carrega os blocos do arquivo.
- `load_file_blocks(self, filename)`: Carrega o conteúdo do arquivo em blocos e os armazena.
- `start(self)`: Inicia o servidor de socket do Tracker e começa a escutar por conexões.
- `handle_client(self, conn, addr)`: Processa as requisições recebidas de peers em uma nova thread.
- `register_peer(self, data, addr)`: Registra um novo peer, atribui blocos iniciais aleatórios e retorna a lista de peers conhecidos.
- `get_peers(self, data)`: Retorna uma lista de peers conhecidos para o peer solicitante (limitado a 5 peers aleatórios se houver mais).
- `handle_block_request(self, data)`: Responde a requisições de blocos, enviando o bloco solicitado se disponível.
- `handle_peer_offline(self, data)`: Remove um peer da lista de peers conectados quando ele é sinalizado como offline.


---

## Peers

O Peer é implementado na classe `PeerSocket` dentro de `peer_socket_v2.py`. Atua como cliente (fazendo requisições) e servidor (respondendo a outros peers) via sockets TCP.

### Principais Atributos da Classe `PeerSocket`

- `self.peer_id`: Identificador único do peer
- `self.listen_port`: Porta de escuta
- `self.blocks_owned`: Lista booleana indicando posse de blocos
- `self.block_data`: Conteúdo dos blocos possuídos
- `self.known_peers`: Dicionário de peers conhecidos
- `self.peer_blocks`: Informações de posse de blocos por peer conhecido
- `self.unchoked_peers`: Peers desbloqueados (unchoked)
- `self.file_complete`: Indica se o peer já possui o arquivo completo
- `self.is_running`: Booleano para controlar o estado de execução do peer


### Métodos Principais

- `__init__(self, peer_id, listen_port)`: Inicializa o peer com seu ID e porta de escuta.
- `listen_for_peers(self)`: Inicia um servidor de socket no peer para escutar requisições de outros peers.
- `handle_peer_request(self, conn, addr)`: Lida com as requisições recebidas de outros peers (e.g., solicitação de bloco, anúncio de blocos).
- `handle_have_blocks_info_request(self, conn, msg)`: Responde a requisições de outros peers sobre os blocos que este peer possui.
- `handle_block_request(self, conn, msg)`: Responde a requisições de blocos, enviando o bloco se possuído e o peer estiver "unchoked".
- `register_with_tracker(self)`: Registra o peer no Tracker e recebe informações iniciais, incluindo blocos e peers conhecidos.
- `notify_tracker_peer_offline(self, dead_peer_id)`: Notifica o tracker quando um peer é considerado offline.
- `get_peer_id_by_address(self, ip, port)`: Retorna o ID de um peer a partir de seu endereço IP e porta.
- `send_message(self, ip, port, msg)`: Envia mensagens JSON para outros peers via socket, tratando erros de conexão.
- `request_peer_blocks_info(self, target_pid)`: Solicita informações de posse de blocos a um peer específico.
- `get_rarest_blocks(self)`: Identifica e retorna uma lista dos blocos mais raros que o peer precisa.
- `tit_for_tat(self)`: Implementa a estratégia Tit-for-Tat para selecionar peers para "deschoke".
- `request_block_from_peer(self, target_pid, block_idx)`: Solicita um bloco específico a outro peer.
- `request_block_from_tracker(self, block_idx)`: Solicita um bloco específico ao Tracker, caso não consiga obtê-lo de outros peers.
- `announce_block(self, block_idx)`: Anuncia a aquisição de um novo bloco para os peers conhecidos.
- `reconstruct_file(self)`: Reconstrói o arquivo completo a partir dos blocos baixados.
- `update_peers_from_tracker(self)`: Atualiza a lista de peers conhecidos consultando o Tracker.
- `log_block_progress(self)`: Exibe o progresso do download dos blocos em porcentagem e uma barra de progresso.
- `log_detailed_blocks(self)`: Exibe uma representação visual dos blocos possuídos pelo peer.
- `shutdown(self)`: Inicia o processo de desligamento controlado do peer, notificando o tracker.
- `run(self)`: Loop principal de execução do peer, gerenciando o download, compartilhamento e reconstrução do arquivo.


---

## Estratégias Implementadas

- **Rarest First**: O peer dá prioridade a baixar os blocos mais raros na rede.
- **Tit-for-Tat**: O peer só atende pedidos de quem está colaborando (com exceção de um "optimistic unchoke" aleatório).

---
