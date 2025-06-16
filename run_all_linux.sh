#!/bin/bash

# --- Cores para melhor visualização no terminal ---
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Define o título da janela principal do script
echo -e "\033]0;BitTorrent Test Environment Launcher\007"

echo -e "${BLUE}=======================================================${NC}"
echo -e "${BLUE}    Iniciando Ambiente de Teste BitTorrent (Linux)${NC}"
echo -e "${BLUE}=======================================================${NC}"


# --- Configurações ---
# Host e porta do Tracker
TRACKER_HOST="127.0.0.1"
TRACKER_PORT=9000

# Porta inicial para os Peers
INITIAL_PEER_PORT=5001
# Número de Peers a iniciar
NUM_PEERS=5

# Nome do arquivo a ser compartilhado pelo Tracker (deve existir no mesmo diretório)
FILE_TO_SHARE="file.txt"

# Comando para abrir um novo terminal.
# Ajuste este comando para o seu emulador de terminal se não for gnome-terminal.
# Exemplos:
# gnome-terminal --title="$TITLE" -- bash -c "$COMMAND; exec bash"
# xterm -title "$TITLE" -hold -e "$COMMAND"
# konsole --new-tab -p "tabtitle=$TITLE" -e "bash -c '$COMMAND; read -p \"Pressione Enter para fechar.\"'"
start_new_terminal_command() {
    local TITLE="$1"
    local COMMAND="$2"
    gnome-terminal --tab --title="$TITLE" -- bash -c "$COMMAND; exec bash"
}

# =======================================================


echo -e "${YELLOW}Verificando se o arquivo \"${FILE_TO_SHARE}\" existe...${NC}"
if [ ! -f "${FILE_TO_SHARE}" ]; then
    
    echo -e "${RED}ERRO: O arquivo \"${FILE_TO_SHARE}\" não foi encontrado no diretório atual.${NC}"
    echo -e "${YELLOW}Crie este arquivo antes de iniciar o Tracker e os Peers.${NC}"
    
    echo -e "${YELLOW}Exemplo de como criar um arquivo vazio para teste (1KB):${NC}"
    echo -e "${YELLOW}dd if=/dev/zero of=${FILE_TO_SHARE} bs=1K count=1${NC}"
    
    read -p "Pressione Enter para sair."
    exit 1
else
    echo -e "${GREEN}Arquivo \"${FILE_TO_SHARE}\" encontrado.${NC}"
fi


echo -e "${YELLOW}Iniciando o Tracker (em nova janela)...${NC}"
start_new_terminal_command "Tracker" "python3 tracker.py" &

# Espera alguns segundos para o Tracker inicializar completamente
echo -e "${YELLOW}Esperando 2 segundos para o Tracker iniciar...${NC}"
sleep 2


echo -e "${YELLOW}Iniciando os Peers (cada um em sua própria janela)...${NC}"


# Loop para iniciar cada Peer
for (( i=1; i<=NUM_PEERS; i++ )); do
    PEER_ID="peer$i"
    PORT=$((INITIAL_PEER_PORT + i - 1))
    
    echo -e "${YELLOW}Iniciando ${PEER_ID} na porta ${PORT}...${NC}"
    start_new_terminal_command "${PEER_ID}" "python3 peer.py ${PEER_ID} ${PORT}" &
    
    # Pequena pausa entre o início de cada peer para evitar sobrecarga ou problemas de inicialização
    sleep 0.5
done


echo -e "${GREEN}=======================================================${NC}"
echo -e "${GREEN}    Ambiente BitTorrent Iniciado!${NC}"
echo -e "${GREEN}    Verifique as janelas separadas para o Tracker e os Peers.${NC}"
echo -e "${GREEN}=======================================================${NC}"

read -p "Pressione Enter para fechar este terminal de controle."