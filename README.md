# MiniBit
Implementação de um sistema de compartilhamento cooperativo de arquivos com estratégias distribuídas.

## Estrutura Inicial
- `tracker.py`
- `peers.py`

## Tracker
O Tracker agora é implementado como uma aplicação web RESTful usando Flask, encapsulada na classe TrackerApp. Ele coordena o registro e a consulta de peers através de endpoints HTTP. Na consulta de peers, se houver menos de 5 peers, todos os peers (exceto o peer que está solicitando a listagem) são enviados.

É composto por uma classe `TrackerApp` que contém os seguintes atributos:

1. `self.app`: Instância da aplicação Flask que gerencia as rotas HTTP e o servidor web para o Tracker.

2. `self.host`: String que contém o host em que o tracker irá escutar. O valor é obtido da variável de ambiente `TRACKER_HOST`, com 127.0.0.1 como fallback.

3. `self.port`: Inteiro que contém a porta em que o tracker irá escutar. O valor é obtido da variável de ambiente `TRACKER_PORT`, com 9000 como fallback.

4. `self.total_file_blocks`: Inteiro que contém o número total de blocos do arquivo a ser compartilhado.

5. `self.connected_peers`: Dicionário que armazena informações sobre todos os peers atualmente registrados no Tracker. A chave é o peer_id (identificador único do peer) e o valor é um dicionário contendo o IP (`ip`), a porta de escuta (`port`) e uma lista simplificada dos blocos que o peer possui (`blocks_owned`). Exemplo: `{'peer_id': {'ip': '192.168.1.10', 'port': 50001, 'blocks_owned': [0, 5, 12]}}`.

O programa principal consiste na instanciação da classe `TrackerApp` e na chamada ao método de instância `run()`.

### Métodos da Classe TrackerApp
#### __init__(self, host='127.0.0.1', port=9000, total_file_blocks=50)

- **Propósito:** Construtor da classe `TrackerApp`. 

- **Funcionalidade:** Inicializa a instância da aplicação Flask (`self.app`), define o host, a porta e o número total de blocos. Também inicializa o dicionário `self.connected_peers` e chama `_setup_routes()`.

### _setup_routes(self)

- **Propósito:** Configura as rotas da API REST para o Tracker.

- **Funcionalidade:** Associa os métodos de manipulação de requisições (`register_peer` e `get_peers`) aos seus respectivos URLs (`/register` e `/peers`) e métodos HTTP (POST e GET) dentro da aplicação Flask.

### register_peer(self) - Endpoint POST /register

- **Propósito:** Permite que um novo peer se registre no Tracker.

- **Funcionalidade:**

    - Recebe uma requisição POST com um payload JSON contendo o `peer_id` e a `listen_port` do peer.

    - Obtém o endereço IP do peer solicitante através de `request.remote_addr`.

    - Simula a atribuição de um número aleatório de "blocos iniciais" para o peer.

    - Armazena as informações do peer (IP, porta de escuta e blocos iniciais) no dicionário `self.connected_peers`.

    - Retorna uma resposta JSON de sucesso, incluindo os `initial_blocks` atribuídos e uma lista dos peers atualmente conectados (excluindo o peer que acabou de se registrar).

### get_peers(self) - Endpoint GET /peers

- **Propósito:** Permite que um peer solicite uma lista de outros peers conhecidos pelo Tracker.

- **Funcionalidade:**

    - Recebe uma requisição GET. O `peer_id` do peer solicitante pode ser passado como um parâmetro de consulta.

    - Filtra a lista `self.connected_peers` para excluir o peer solicitante.

    - Se houver menos de 5 peers restantes, retorna todos eles. Caso contrário, retorna um subconjunto aleatório de 5 peers.

    - Envia uma resposta JSON de sucesso com a lista filtrada de peers.

### run(self)

- **Propósito:** Inicia o servidor web Flask para o Tracker.

- **Funcionalidade:** Inicia a aplicação Flask, fazendo com que o Tracker comece a escutar por requisições HTTP no host e porta configurados. Utiliza `host='0.0.0.0'` para permitir acesso de outras máquinas na rede.


## Peers
O Peer é implementado como uma classe `Peer` que atua tanto como cliente (fazendo requisições ao Tracker e a outros Peers) quanto como servidor (respondendo a requisições de outros Peers), tudo isso usando uma API REST com Flask e a biblioteca `requests`.

É composto por uma classe `Peer` que contém os seguintes atributos:

1. `self.peer_id`: String que é o identificador único deste peer.

2. `self.total_blocks`: Inteiro que representa o número total de blocos do arquivo completo a ser compartilhado/reconstruído.

3. `self.file_name`: String que é o nome do arquivo a ser reconstruído por este peer.

4. `self.blocks_owned`: Lista booleana que representa a posse dos blocos pelo peer. True se o bloco for possuído, False caso contrário. Exemplo: `[True, False, True, ...]`.

5. `self.block_data`: Dicionário que armazena o conteúdo real (simulado) de cada bloco que o peer possui. A chave é o índice do bloco e o valor é o conteúdo. Exemplo: `{0: "Conteúdo do bloco 0", 2: "Conteúdo do bloco 2"}`.

6. `self.known_peers`: Dicionário que armazena informações sobre os peers conhecidos por este peer. A chave é uma string no formato `'ip:port'` (chave única para cada peer conhecido) e o valor é um dicionário contendo o IP, a porta e uma lista booleana (`'blocks_info'`) dos blocos que o peer conhecido possui.

7. `self.listen_port`: Inteiro que contém a porta em que o servidor Flask interno deste peer irá escutar por requisições de outros peers.

8. `self.peer_url`: String que é a URL base para a própria API REST deste peer (ex: `http://127.0.0.1:50001`).

9. `self.unchoked_peers`: Conjunto (set) de chaves de peers (`'ip:port'`) que este peer considera "desbloqueados", ou seja, pode fazer requisições a eles.

10. `self.choked_peers`: Conjunto (set) de chaves de peers (`'ip:port'`) que este peer considera "bloqueados".

11. `self.optimistic_unchoke`: String que armazena a chave (`'ip:port'`) do peer que está sendo otimisticamente desbloqueado na estratégia Tit-for-Tat.

12. `self.last_unchoke_time`: Float que registra o último timestamp em que a estratégia Tit-for-Tat foi aplicada para o desbloqueio.

13. `self.app`: Instância da aplicação Flask específica para este peer, usada para lidar com requisições de outros peers.

14. `self.file_complete`: Booleano que indica se o peer já possui todos os blocos do arquivo e, portanto, já o reconstruiu.


O programa principal para a simulação consiste na instanciação da classe `Peer` para cada peer e na chamada ao método de instância `run()` em threads separadas.



### __init__(self, peer_id, total_blocks, file_name="shared_file.txt")

- **Propósito**: Construtor da classe `Peer`.

- **Funcionalidade**: Inicializa todos os atributos do peer, incluindo a própra instância Flask (`self.app`), define as rotas da API interna (`_setup_peer_api_routes()`) e simula a posse inicial de blocos.

### _find_available_port(self)

- **Propósito**: Encontra uma porta disponível para o servidor Flask interno do peer.

- **Funcionalidade**: Seleciona uma porta aleatória dentro de uma faixa predefinida (`PEER_LISTEN_PORT_START` a `PEER_LISTEN_PORT`).

### _setup_peer_api_routes(self)

- **Propósito**: Configura as rotas da API REST que este peer expõe para outros peers.

- **Funcionalidade**: Associa os métodos de manipulação de requisições de entrada (`request_block_handler`, `have_blocks_info_handler`, `announce_block_handler`) aos seus respectivos URLs e métodos HTTP.

### request_block_handler(self) - Endpoint POST /request_block 

- **Propósito**: Manipula requisições de outros peers para obter um bloco específico.

- **Funcionalidade**:

    - Recebe um payload JSON com `block_index`e `sender_id`.
    - Verifica se o peer possui o bloco solicitado e se o peer remetente está na lista de `unchoked_peers`.
    - Se ambas as condições forem verdadeiras, retorna uma resposta JSON com o conteúdo do bloco (`block_data`). Caso contrário, retorna um erro indicando que o bloco não está disponível ou o peer está bloqueado.


### have_blocks_info_handler(self) - Endpoint POST /have_blocks_info

- **Propósito**: Recebe e processa informações sobre os blocos que outro peer possui.

- **Funcionalidade**:

    - Recebe um payload JSON com `blocks_info` (a lista booleana de posse de blocos do peer remetente) e `sender_id`.
    - Atualiza a entrada correspondente no dicionário `self.known_peers` com a nova informação de blocos.

### announce_block_handler(self) - Endpoint POST /announce_block

- **Propósito**: Recebe um anúncio de outro peer informando que ele adquiriu um novo bloco.

- **Funcionalidade**:

    - Recebe um payload JSON com `block_index` e `sender_id`.
    - Atualiza o `blocks_info` do peer remetente em `self.known_peers` para marcar que ele agora possui o bloco anunciado.

### connect_to_tracker(self):

 - **Propósito**: Registra o peer no Tracker central.

 - **Funcionalidade**: Faz uma requisição POST para o endpoint `/register` do Tracker, enviando seu `peer_id` e `listen_port`. Recebe e processa a resposta, que inclui blocos iniciais atribuídos (simulados) e uma lista de peers já conectados.

### request_peer_list_from_tracker(self):
- **Propósito**: Solicita uma lista atualizada de peers do Tracker.

- **Funcionalidade**: Faz uma requisição GET para o endpoint `/peers` do Tracker. Atualiza `self.known_peers` com as informações dos novos peers recebidos.

### start_listening_for_peers(self):

- **Propósito**: Inicia o servidor Flask interno do peer.

- **Funcionalidade**: Executa `self.app.run()` em uma thread separada, permitindo que o peer receba requisições de outros peers em segundo plano.

### _initialize_partial_blocks(self): ((Avaliar necessidade))

- **Propósito**: Simula a posse inicial de um subconjunto aleatório de blocos pelo peer para fins de inicialização na simulação.

- **Funcionalidade**: Atribui aleatoriamente um número de blocos ao `self.blocks_owned` e preenche `self.block_data` com conteúdo simulado para esses blocos.













