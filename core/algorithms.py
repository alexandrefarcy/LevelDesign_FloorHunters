"""
core/algorithms.py
Algorithmes de generation procedurale pour Tower Dungeon.

Contient :
  - flood_fill        : detection des salles contigues (GROUND)
  - filter_rooms      : filtre par taille minimale
  - room_center       : centre geometrique d'une salle
  - build_mst         : arbre couvrant minimal (Kruskal via networkx)
  - add_extra_edges   : +30% connexions aleatoires supplementaires
  - trace_corridor    : trace un couloir droit ou en L entre deux points
  - blob_room         : salle de transition a croissance organique (blob)
  - corridor_length   : longueur d'un couloir entre deux points
"""

from __future__ import annotations

import math
import random
from typing import Optional

import networkx as nx

from core.grid import CellType, Floor, GridModel, GRID_SIZE, HALF


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

MIN_ROOM_CELLS = 2          # taille minimale : 2x1 = 2 cellules
CORRIDOR_TRANSITION_LEN = 7 # couloir > 7 cases -> salle de transition
TRANSITION_MIN = 3          # taille min salle de transition (cote du blob)
TRANSITION_MAX = 8          # taille max salle de transition
TRANSITION_ATTEMPTS = 25    # tentatives max de placement
TRANSITION_MIN_DIST = 3     # distance min (en cases) aux autres salles


# ---------------------------------------------------------------------------
# Flood fill
# ---------------------------------------------------------------------------

def flood_fill(floor: Floor) -> list[set[tuple[int, int]]]:
    """Detecte toutes les salles contigues de type GROUND par flood fill iteratif.

    Utilise une pile explicite (pas de recursion) pour eviter RecursionError
    sur les grandes surfaces.

    Args:
        floor: L'etage a analyser.

    Returns:
        Liste de sets, chaque set contenant les (row, col) d'une salle contigues.
    """
    visited: set[tuple[int, int]] = set()
    rooms: list[set[tuple[int, int]]] = []

    for start_row in range(GRID_SIZE):
        for start_col in range(GRID_SIZE):
            if (start_row, start_col) in visited:
                continue
            if floor.grid[start_row][start_col].cell_type != CellType.GROUND:
                continue

            # BFS iteratif
            room: set[tuple[int, int]] = set()
            stack = [(start_row, start_col)]
            while stack:
                row, col = stack.pop()
                if (row, col) in visited:
                    continue
                if not (0 <= row < GRID_SIZE and 0 <= col < GRID_SIZE):
                    continue
                if floor.grid[row][col].cell_type != CellType.GROUND:
                    continue
                visited.add((row, col))
                room.add((row, col))
                # 4 voisins cardinaux
                stack.append((row - 1, col))
                stack.append((row + 1, col))
                stack.append((row, col - 1))
                stack.append((row, col + 1))

            if room:
                rooms.append(room)

    return rooms


# ---------------------------------------------------------------------------
# Filtre de taille
# ---------------------------------------------------------------------------

def filter_rooms(
    rooms: list[set[tuple[int, int]]],
    min_cells: int = MIN_ROOM_CELLS,
) -> list[set[tuple[int, int]]]:
    """Retourne uniquement les salles ayant au moins min_cells cellules.

    Args:
        rooms:     Liste de salles issues de flood_fill.
        min_cells: Nombre minimum de cellules (defaut : 2 pour 2x1).

    Returns:
        Sous-liste des salles conformes.
    """
    return [r for r in rooms if len(r) >= min_cells]


# ---------------------------------------------------------------------------
# Centre geometrique
# ---------------------------------------------------------------------------

def room_center(room: set[tuple[int, int]]) -> tuple[float, float]:
    """Calcule le centre geometrique (barycentre) d'une salle en index (row, col).

    Args:
        room: Set de (row, col).

    Returns:
        (center_row, center_col) en flottants.
    """
    total = len(room)
    sum_row = sum(r for r, _ in room)
    sum_col = sum(c for _, c in room)
    return sum_row / total, sum_col / total


# ---------------------------------------------------------------------------
# MST Kruskal
# ---------------------------------------------------------------------------

def build_mst(
    rooms: list[set[tuple[int, int]]],
) -> list[tuple[int, int]]:
    """Construit un arbre couvrant minimal (MST) entre les centres des salles.

    Utilise networkx.minimum_spanning_tree (algorithme de Kruskal).

    Args:
        rooms: Liste de salles (chaque salle = set de (row, col)).

    Returns:
        Liste de paires d'indices (i, j) representant les aretes du MST.
        Retourne [] si moins de 2 salles.
    """
    if len(rooms) < 2:
        return []

    centers = [room_center(r) for r in rooms]

    G = nx.Graph()
    for i in range(len(rooms)):
        G.add_node(i)

    for i in range(len(rooms)):
        for j in range(i + 1, len(rooms)):
            cr, cc = centers[i]
            dr, dc = centers[j]
            dist = math.hypot(cr - dr, cc - dc)
            G.add_edge(i, j, weight=dist)

    mst = nx.minimum_spanning_tree(G, algorithm="kruskal")
    return list(mst.edges())


# ---------------------------------------------------------------------------
# Connexions supplementaires (+30%)
# ---------------------------------------------------------------------------

def add_extra_edges(
    edges: list[tuple[int, int]],
    rooms: list[set[tuple[int, int]]],
    ratio: float = 0.30,
) -> list[tuple[int, int]]:
    """Ajoute des connexions aleatoires supplementaires (en plus du MST).

    Le nombre de connexions ajoutees est ratio * len(edges), arrondi.
    Les doublons et boucles sont exclus.

    Args:
        edges:  Aretes existantes (MST).
        rooms:  Liste des salles (pour connaitre le nombre de noeuds).
        ratio:  Proportion supplementaire (defaut 0.30 = +30%).

    Returns:
        Nouvelle liste d'aretes (MST + extras), sans doublons.
    """
    n = len(rooms)
    if n < 2:
        return list(edges)

    existing = set(tuple(sorted(e)) for e in edges)
    all_pairs = [
        (i, j)
        for i in range(n)
        for j in range(i + 1, n)
        if (i, j) not in existing
    ]

    extra_count = max(1, round(len(edges) * ratio))
    extra_count = min(extra_count, len(all_pairs))

    extras = random.sample(all_pairs, extra_count)
    return list(edges) + extras


# ---------------------------------------------------------------------------
# Longueur de couloir
# ---------------------------------------------------------------------------

def corridor_length(
    a: tuple[int, int],
    b: tuple[int, int],
) -> int:
    """Retourne la longueur Manhattan du couloir entre deux points (row, col).

    Pour un couloir droit : distance directe.
    Pour un couloir en L : somme des deux segments.

    Args:
        a: (row, col) du point de depart.
        b: (row, col) du point d'arrivee.

    Returns:
        Longueur en nombre de cases.
    """
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


# ---------------------------------------------------------------------------
# Trace de couloir
# ---------------------------------------------------------------------------

def trace_corridor(
    floor: Floor,
    a: tuple[int, int],
    b: tuple[int, int],
    rng: Optional[random.Random] = None,
) -> list[tuple[int, int]]:
    """Trace un couloir GROUND entre deux points (row, col).

    Regles :
      - Meme ligne OU meme colonne -> couloir droit
      - Sinon -> couloir en L avec coude aleatoire
        (horizontal-first OU vertical-first, tire au sort)

    Les cellules non-EMPTY existantes ne sont pas ecrasees
    (on ne pose GROUND que sur les cases EMPTY).

    Args:
        floor: L'etage ou tracer le couloir.
        a:     (row, col) de depart.
        b:     (row, col) d'arrivee.
        rng:   Instance random optionnelle (pour reproductibilite).

    Returns:
        Liste des (row, col) poses en GROUND (nouvelles cases uniquement).
    """
    if rng is None:
        rng = random

    ar, ac = a
    br, bc = b
    posed: list[tuple[int, int]] = []

    def place(row: int, col: int) -> None:
        if not (0 <= row < GRID_SIZE and 0 <= col < GRID_SIZE):
            return
        if floor.grid[row][col].cell_type == CellType.EMPTY:
            floor.grid[row][col].cell_type = CellType.GROUND
            posed.append((row, col))

    def segment_h(row: int, c1: int, c2: int) -> None:
        """Segment horizontal de c1 a c2 inclus."""
        step = 1 if c2 >= c1 else -1
        for col in range(c1, c2 + step, step):
            place(row, col)

    def segment_v(col: int, r1: int, r2: int) -> None:
        """Segment vertical de r1 a r2 inclus."""
        step = 1 if r2 >= r1 else -1
        for row in range(r1, r2 + step, step):
            place(row, col)

    if ar == br:
        # Meme ligne -> couloir horizontal droit
        segment_h(ar, ac, bc)
    elif ac == bc:
        # Meme colonne -> couloir vertical droit
        segment_v(ac, ar, br)
    else:
        # Couloir en L : coude aleatoire
        if rng.random() < 0.5:
            # Horizontal d'abord, puis vertical
            segment_h(ar, ac, bc)
            segment_v(bc, ar, br)
        else:
            # Vertical d'abord, puis horizontal
            segment_v(ac, ar, br)
            segment_h(br, ac, bc)

    return posed


# ---------------------------------------------------------------------------
# Salle de transition (blob organique)
# ---------------------------------------------------------------------------

def blob_room(
    floor: Floor,
    center_row: int,
    center_col: int,
    min_size: int = TRANSITION_MIN,
    max_size: int = TRANSITION_MAX,
    existing_rooms: Optional[list[set[tuple[int, int]]]] = None,
    min_dist: int = TRANSITION_MIN_DIST,
    rng: Optional[random.Random] = None,
) -> Optional[set[tuple[int, int]]]:
    """Tente de generer une salle de transition organique (blob) au point donne.

    La forme est obtenue par croissance cellule par cellule a partir du centre.
    La salle ne doit pas :
      - Superposer une cellule deja non-EMPTY sur la grille
      - Etre a moins de min_dist cases d'une cellule de existing_rooms

    Args:
        floor:         L'etage cible.
        center_row:    Ligne du centre desire.
        center_col:    Colonne du centre desire.
        min_size:      Nombre minimum de cellules du blob.
        max_size:      Nombre maximum de cellules du blob.
        existing_rooms: Salles manuelles a respecter (distance min).
        min_dist:      Distance minimale aux autres salles.
        rng:           Instance random optionnelle.

    Returns:
        Set des (row, col) du blob si succes, None si echec.
    """
    if rng is None:
        rng = random

    target_size = rng.randint(min_size * min_size, max_size * max_size)
    target_size = max(min_size, min(target_size, max_size * max_size))

    # Verifie si une cellule candidate est a distance suffisante
    def too_close(row: int, col: int) -> bool:
        if existing_rooms is None:
            return False
        for room in existing_rooms:
            for rr, rc in room:
                if abs(rr - row) < min_dist and abs(rc - col) < min_dist:
                    return True
        return False

    # Verifie si une cellule peut etre posee
    def can_place(row: int, col: int) -> bool:
        if not (0 <= row < GRID_SIZE and 0 <= col < GRID_SIZE):
            return False
        if floor.grid[row][col].cell_type != CellType.EMPTY:
            return False
        if too_close(row, col):
            return False
        return True

    if not can_place(center_row, center_col):
        return None

    # Croissance organique
    blob: set[tuple[int, int]] = {(center_row, center_col)}
    frontier: list[tuple[int, int]] = []

    # Initialise la frontiere avec les 4 voisins du centre
    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        nr, nc = center_row + dr, center_col + dc
        if can_place(nr, nc) and (nr, nc) not in blob:
            frontier.append((nr, nc))

    while len(blob) < target_size and frontier:
        # Choisit un voisin aleatoire de la frontiere
        idx = rng.randrange(len(frontier))
        row, col = frontier[idx]
        frontier[idx] = frontier[-1]
        frontier.pop()

        if (row, col) in blob:
            continue
        if not can_place(row, col):
            continue

        blob.add((row, col))

        # Ajoute les voisins de la nouvelle cellule a la frontiere
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = row + dr, col + dc
            if (nr, nc) not in blob and can_place(nr, nc):
                frontier.append((nr, nc))

    # Verifie la taille minimale
    if len(blob) < min_size:
        return None

    # Pose les cellules sur la grille
    for row, col in blob:
        floor.grid[row][col].cell_type = CellType.GROUND

    return blob


# ---------------------------------------------------------------------------
# Point de connexion entre deux salles
# ---------------------------------------------------------------------------

def find_connection_points(
    room_a: set[tuple[int, int]],
    room_b: set[tuple[int, int]],
) -> tuple[tuple[int, int], tuple[int, int]]:
    """Trouve les deux cellules (une par salle) les plus proches l'une de l'autre.

    Utilisees comme points de depart et d'arrivee pour trace_corridor.

    Args:
        room_a: Premiere salle.
        room_b: Deuxieme salle.

    Returns:
        (point_in_a, point_in_b) les plus proches.
    """
    best_dist = float("inf")
    best_a: tuple[int, int] = next(iter(room_a))
    best_b: tuple[int, int] = next(iter(room_b))

    # Optimisation : on compare les barycentres d'abord pour restreindre
    # la recherche aux cellules proches du bord interieur
    ca_r, ca_c = room_center(room_a)
    cb_r, cb_c = room_center(room_b)

    # Direction approximative de B vers A et inversement
    dir_r = cb_r - ca_r
    dir_c = cb_c - ca_c

    # Candidats : cellules de room_a dans la direction de room_b
    candidates_a = sorted(
        room_a,
        key=lambda rc: -(rc[0] * dir_r + rc[1] * dir_c),
    )[:max(1, len(room_a) // 4)]

    candidates_b = sorted(
        room_b,
        key=lambda rc: (rc[0] * dir_r + rc[1] * dir_c),
    )[:max(1, len(room_b) // 4)]

    for ar, ac in candidates_a:
        for br, bc in candidates_b:
            d = abs(ar - br) + abs(ac - bc)
            if d < best_dist:
                best_dist = d
                best_a = (ar, ac)
                best_b = (br, bc)

    return best_a, best_b
