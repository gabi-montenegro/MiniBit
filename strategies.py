import random
from colorama import Fore, Style

def get_rarest_blocks(peer):
    rarity = {}
    for idx in range(peer.TOTAL_FILE_BLOCKS):
        if not peer.blocks_owned[idx]:
            count = sum(
                1 for blocks in peer.peer_blocks.values()
                if idx < len(blocks) and blocks[idx]
            )
            rarity[idx] = count if count > 0 else 9999
    return sorted(rarity, key=lambda k: rarity[k])

def tit_for_tat(peer):
    rarity_count = {}
    rarest_blocks = get_rarest_blocks(peer)

    peers_considered = [pid for pid in peer.peer_blocks if pid != 'tracker']

    for pid in peers_considered:
        count = sum(1 for block_idx in rarest_blocks if peer.peer_blocks[pid][block_idx])
        rarity_count[pid] = count

    sorted_peers = sorted(rarity_count.items(), key=lambda item: item[1], reverse=True)

    
    new_fixed_peers = set()
    top_peers = [pid for pid, count in sorted_peers if count > 0]

    for pid in top_peers:
        if pid in getattr(peer, "fixed_peers", set()):
            new_fixed_peers.add(pid)
        if len(new_fixed_peers) >= 4:
            break
    for pid in top_peers:
        if pid not in new_fixed_peers:
            new_fixed_peers.add(pid)
        if len(new_fixed_peers) >= 4:
            break

    candidates_for_optimistic = [pid for pid in peers_considered if pid not in new_fixed_peers]

    optimistic_peer = set()
    if candidates_for_optimistic:
        optimistic_peer = {random.choice(candidates_for_optimistic)}
        print(f"{Fore.MAGENTA}[{peer.peer_id}] Peer otimista escolhido: {optimistic_peer}{Style.RESET_ALL}")

    peer.fixed_peers = new_fixed_peers
    peer.unchoked_peers = new_fixed_peers.union(optimistic_peer)
    print(f"{Fore.YELLOW}[{peer.peer_id}] Unchoked peers: {peer.unchoked_peers}{Style.RESET_ALL}")
