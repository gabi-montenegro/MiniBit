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





