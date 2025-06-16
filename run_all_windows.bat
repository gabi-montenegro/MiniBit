@echo off
setlocal enabledelayedexpansion

REM Define o título da janela principal do script
title BitTorrent Test Environment Launcher

REM Define cores para a saída no console
color 0E

echo =======================================================
echo     Iniciando Ambiente de Teste BitTorrent
echo =======================================================
echo.

REM --- Configurações ---
REM Porta padrão do Tracker
set TRACKER_HOST=127.0.0.1
set TRACKER_PORT=9000

REM Porta inicial para os Peers
set INITIAL_PEER_PORT=5001
REM Número de Peers a iniciar
set NUM_PEERS=5

REM Nome do arquivo a ser compartilhado pelo Tracker (deve existir no mesmo diretorio)
set FILE_TO_SHARE=file.txt

REM =======================================================

echo.
echo.
echo Verificando se o arquivo "%FILE_TO_SHARE%" existe...
if not exist "%FILE_TO_SHARE%" (
    goto FILE_NOT_FOUND
)

echo Arquivo "%FILE_TO_SHARE%" encontrado.
goto CONTINUE

:FILE_NOT_FOUND
echo.
echo ERRO: O arquivo "%FILE_TO_SHARE%" nao foi encontrado no diretorio atual.
echo Crie este arquivo antes de iniciar o Tracker e os Peers.
echo.
echo Exemplo de como criar um arquivo vazio para teste (1KB):
echo fsutil file createnew %FILE_TO_SHARE% 1024
echo.
pause
exit /b 1

:CONTINUE


echo.
echo Iniciando o Tracker (em nova janela)...
start "Tracker" cmd /k python tracker.py

REM Espera alguns segundos para o Tracker inicializar completamente
echo Esperando 2 segundos para o Tracker iniciar...
timeout /t 2 /nobreak > nul

echo.
echo Iniciando os Peers (cada um em sua propria janela)...
echo.

REM Loop para iniciar cada Peer
for /l %%i in (1,1,%NUM_PEERS%) do (
    set /a CURRENT_PORT=!INITIAL_PEER_PORT! + %%i - 1
    set PEER_ID=peer%%i

    echo Iniciando !PEER_ID! na porta !CURRENT_PORT!...
    start "Peer !PEER_ID!" cmd /k python peer.py !PEER_ID! !CURRENT_PORT!

    timeout /t 1 /nobreak > nul
)

echo.
echo =======================================================
echo     Ambiente BitTorrent Iniciado!
echo     Verifique as janelas separadas para o Tracker e os Peers.
echo =======================================================
echo.
pause
