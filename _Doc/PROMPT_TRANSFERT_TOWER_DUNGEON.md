# PROMPT DE TRANSFERT — Tower Dungeon Level Editor (v1)

---

## ⚠️ INSTRUCTIONS POUR LE NOUVEAU CLAUDE

Tu reprends un projet Python en cours de développement. Avant de coder quoi que ce soit :
1. Lis ce prompt **intégralement**
2. Demande à l'utilisateur d'uploader les fichiers listés dans la section **FICHIERS À UPLOADER** correspondant à la phase en cours
3. Fais un **audit rapide** de conformité code vs prompt
4. Confirme l'étape suivante avant de toucher une seule ligne
5. **Ne jamais coder plusieurs phases d'un coup** — une phase à la fois, validation obligatoire entre chaque
6. **Fournir un message de commit Git** pour chaque livrable, format : `type(scope): description`
7. **Toujours `ast.parse()` le code Python livré avant de le soumettre**

---

## 📦 NOTE DÉVELOPPEUR — INSTALLATION SUR UN NOUVEAU PC

### Prérequis système
- **Python 3.12+** (vérifier : `python --version`)
- **pip** à jour : `python -m pip install --upgrade pip`

### Installation des dépendances

```bash
pip install PyQt6 networkx jsonschema pytest pytest-qt
```

### Détail des packages

| Package | Version min | Usage dans le projet |
|---------|-------------|----------------------|
| `PyQt6` | 6.4+ | Interface graphique complète (fenêtre, canvas, toolbar) |
| `networkx` | 3.0+ | MST de Kruskal (génération procédurale des couloirs) |
| `jsonschema` | 4.0+ | Validation schéma JSON à l'import |
| `pytest` | 7.0+ | Tests unitaires core/ |
| `pytest-qt` | 4.0+ | Tests intégration UI PyQt6 |

> **Note :** `json`, `os`, `sys`, `copy`, `random`, `math`, `enum`, `dataclasses` sont des modules stdlib Python — pas besoin de les installer.

### Vérification rapide
```bash
python -c "import PyQt6; import networkx; import jsonschema; print('OK')"
```

### Lancer l'application en développement
```bash
python app.py
```

---

## 🎯 VISION DU PROJET

Éditeur de level design **desktop local** (PyQt6) pour un jeu mobile **Tower Dungeon**.

- L'utilisateur dessine manuellement des salles sur une grille 72×72
- Un générateur procédural crée automatiquement les couloirs, murs et salles de transition
- Un futur système de peuplement placera les entités (ennemis, boss, coffres, pièges…)
- Export/import JSON pour intégration dans le moteur de jeu
- Interface desktop ergonomique, **pas tactile** (contrairement au projet React original)
- Sauvegarde automatique locale — un seul utilisateur, tout local, pas d'auth

---

## 🏗️ ARCHITECTURE DES MODULES

```
app.py                          <- Point d'entrée, instanciation QApplication
core/
  grid.py                       <- Modèle de données : Cell, Floor, GridModel
  generator.py                  <- Génération procédurale (flood fill + MST Kruskal + couloirs)
  populator.py                  <- Peuplement d'entités (Phase 5 — futur)
  algorithms.py                 <- Utilitaires : flood fill, MST, L-path
io/
  serializer.py                 <- Import/export JSON + validation jsonschema
  autosave.py                   <- Sauvegarde automatique (QTimer 30s)
ui/
  main_window.py                <- FenetrePrincipale + orchestration
  editor_view.py                <- Canvas QGraphicsView/QGraphicsScene — rendu, zoom, pan
  toolbar.py                    <- Palette d'outils + sélection d'étage
  dialogs.py                    <- Dialogues : génération, peuplement, import/export
assets/
  default_sprites/              <- Sprites par défaut (PNG 32×32)
tests/
  test_grid.py
  test_generator.py
  test_serializer.py
```

---

## 📐 SYSTÈME DE GRILLE

- **Dimensions :** 72×72 cellules (5 184 cellules totales)
- **Coordonnées centrées :** (0,0) au centre de la grille
  - X : de -36 (gauche) à +36 (droite)
  - Y : de -36 (bas) à +36 (haut)
- **Cellules carrées** — jamais de déformation
- **Rendu :** QGraphicsView + QGraphicsScene — une QPixmap par étage, invalidation partielle à chaque modification
- **NE PAS** instancier 5 184 widgets Qt pour la grille — canvas unique obligatoire

```
(-36, 36) ←──── (0, 36) ────→ (36, 36)
    │             │                │
    │        STAIRS DOWN           │
    │           (0, 0)             │
    │             │                │
(-36,-36) ←── (0,-36) ────→ (36,-36)
```

---

## 🎨 TYPES DE CELLULES (CellType enum)

| Valeur enum | Emoji | Nom affiché | Notes |
|------------|-------|-------------|-------|
| `EMPTY` | — | Vide | Cellule par défaut |
| `GROUND` | 🟫 | Sol | Praticable, base de dessin manuel |
| `WALL` | 🧱 | Mur | Généré automatiquement en bordure |
| `ENEMY` | 👾 | Ennemi | Entité standard |
| `BOSS` | 👹 | Boss | Salle isolée ou éloignée du spawn |
| `TREASURE` | 💎 | Trésor | Salle de transition ou coin |
| `TRAP` | 🔥 | Piège | Couloirs étroits |
| `CAMP` | ⛺ | Camp | Salle sécurisée |
| `STAIRS_DOWN` | 🪜 | Escalier bas | **Forcé à (0,0)** — généré automatiquement |
| `STAIRS_UP` | 🪜 | Escalier haut | Placé manuellement, salle isolée |
| `SPAWN` | 📍 | Spawn | Point d'apparition |
| `ERASER` | 🗑️ | Gomme | Outil UI uniquement, pas une cellule |

---

## 💾 FORMAT JSON D'EXPORT

> **Ce schéma est figé — ne pas modifier sans valider avec l'utilisateur.**

```json
{
  "version": 1,
  "floors": [
    {
      "id": 1,
      "name": "Étage 1",
      "grid": [
        [
          { "type": "ground", "custom_image": null },
          { "type": "wall",   "custom_image": null }
        ]
      ]
    }
  ]
}
```

- `grid` est une liste de **72 lignes × 72 colonnes** (index [0][0] = coin haut-gauche)
- `type` = valeur string de l'enum CellType en minuscules
- `custom_image` = chemin relatif vers sprite personnalisé, ou `null`
- Validation à l'import via `jsonschema` — fichier invalide = refus + message d'erreur, **jamais** de corruption silencieuse

---

## ⚙️ ALGORITHME DE GÉNÉRATION PROCÉDURALE

### Workflow général

```
1. Détection des salles (flood fill sur cellules GROUND)
2. Vérification : chaque salle >= 6×6 cases
3. Calcul des centres géométriques de chaque salle
4. MST de Kruskal (networkx.minimum_spanning_tree) sur les centres
5. Ajout connexions supplémentaires aléatoires (30% de chance par paire)
6. Tracé des couloirs en L entre chaque paire de salles connectées
7. Création salles de transition (5×5 à 9×9) si couloir > 9 cases
8. Génération des murs extérieurs (bordure de 1 case autour de tout GROUND + couloirs)
9. Placement STAIRS_DOWN forcé à (0,0)
```

### Règles salles de transition

- Tentatives : 5 positions (milieu, 1/3, 2/3, 1/4, 3/4) × 5 tailles (5×5 à 9×9) = 25 max
- ❌ Pas de superposition avec salle manuelle
- ❌ Distance minimum 3 cases avec toute salle manuelle
- ✅ Si aucune position valide → couloir simple sans salle de transition

### Règle "Salle Montée" (STAIRS_UP)

- La salle contenant STAIRS_UP est **isolée** : une seule connexion vers la salle la plus proche
- Les autres salles ont entre 1 et 4 connexions

### Connexion en L

```
De A(ax, ay) à B(bx, by) :
  Segment 1 : (ax, ay) → (bx, ay)  [horizontal]
  Segment 2 : (bx, ay) → (bx, by)  [vertical]
```

---

## 🔧 DÉCISIONS TECHNIQUES ARRÊTÉES

> Ces choix sont **validés et définitifs**. Ne pas remettre en question.

1. **QGraphicsView + QGraphicsScene** pour le canvas (pas de QOpenGLWidget sauf problème de performance avéré)
2. **networkx.minimum_spanning_tree** pour le MST (Kruskal)
3. **Flood fill récursif** (ou itératif si stack overflow sur grande salle) pour la détection de salles contiguës
4. **JSON + jsonschema** pour la persistance jusqu'à une éventuelle migration SQLite (non planifiée)
5. **QTimer 30s** pour la sauvegarde automatique vers `~/.tower_dungeon/autosave.json`
6. **Une QPixmap par étage** mis en cache, invalidation partielle à chaque modification de cellule
7. **Coordonnées internes** : index tableau [row][col] → conversion vers (x,y) centrés dans l'affichage uniquement
8. **Upload d'images** : stockage du chemin relatif dans `custom_image`, chargement à la volée

---

## 🗺️ PLAN DE DÉVELOPPEMENT — CYCLE EN V

### ✅ Phases de définition (descendante)

| Phase | Nom | Statut |
|-------|-----|--------|
| 1 | Analyse des besoins — cahier des charges | ✅ Terminé (ce document) |
| 2 | Architecture globale — modules, schéma JSON | ✅ Terminé (ce document) |
| 3 | Conception détaillée — signatures, algos | ✅ Terminé (ce document) |

### 🔲 Phases d'implémentation (fond du V)

| Phase | Nom | Priorité | Fichiers concernés |
|-------|-----|----------|--------------------|
| **4a** | Modèle de données + serializer | 🔴 Priorité 1 | `core/grid.py`, `io/serializer.py` |
| **4b** | Canvas de base (rendu + clic) | 🔴 Priorité 2 | `ui/editor_view.py` |
| **4c** | Outils de dessin + drag | 🟠 | `ui/editor_view.py`, `ui/toolbar.py` |
| **4d** | Zoom/pan + coordonnées temps réel | 🟠 | `ui/editor_view.py` |
| **4e** | Algorithme de génération (sans UI) | 🟠 | `core/generator.py`, `core/algorithms.py` |
| **4f** | Bouton "Générer couloirs et murs" | 🟡 | `ui/main_window.py`, `ui/dialogs.py` |
| **4g** | Navigation multi-étages | 🟡 | `ui/toolbar.py`, `core/grid.py` |
| **4h** | Import/export + sauvegarde auto | 🟡 | `io/serializer.py`, `io/autosave.py` |
| **5** | Upload sprites personnalisés | 🔵 Futur | `ui/dialogs.py`, `core/grid.py` |
| **6** | Système de peuplement d'entités | 🔵 Futur | `core/populator.py`, `ui/dialogs.py` |
| **7** | Packaging .exe PyInstaller | 🔵 Futur | — |

### 🔲 Phases de validation (remontante)

| Phase | Nom | Symétrie |
|-------|-----|----------|
| **V5** | Tests unitaires core/ | ↔ Phase 3 |
| **V6** | Tests d'intégration pipeline | ↔ Phase 2 |
| **V7** | Validation utilisateur game designer | ↔ Phase 1 |

---

## 📋 AVANCEMENT PAR MODULE

| Module | Statut | Notes |
|--------|--------|-------|
| `core/grid.py` | 🔲 À faire | Phase 4a |
| `core/generator.py` | 🔲 À faire | Phase 4e |
| `core/algorithms.py` | 🔲 À faire | Phase 4e |
| `core/populator.py` | 🔲 Futur | Phase 6 |
| `io/serializer.py` | 🔲 À faire | Phase 4a |
| `io/autosave.py` | 🔲 À faire | Phase 4h |
| `ui/editor_view.py` | 🔲 À faire | Phase 4b/4c/4d |
| `ui/toolbar.py` | 🔲 À faire | Phase 4c/4g |
| `ui/main_window.py` | 🔲 À faire | Phase 4f |
| `ui/dialogs.py` | 🔲 À faire | Phase 4f/4h |
| `app.py` | 🔲 À faire | Phase 4b |
| `tests/` | 🔲 À faire | Phase V5 |

---

## 🚦 AVANCEMENT DES COMMITS

| Tag | Description | Commit |
|-----|-------------|--------|
| — | Aucun commit pour l'instant | — |

---

## 🔒 CONTRAINTES PERMANENTES

1. **Ne jamais** instancier 5 184 widgets Qt pour la grille — canvas QGraphicsView obligatoire
2. **STAIRS_DOWN forcé à (0,0)** — généré par le générateur, pas par l'utilisateur
3. **Salles manuelles minimum 6×6** — refus avec message d'erreur si inférieur
4. **Salle STAIRS_UP isolée** — une seule connexion sortante dans le MST
5. **Import JSON invalide** = refus + message d'erreur — jamais de corruption silencieuse
6. **Sauvegarde auto** = toujours dans `~/.tower_dungeon/autosave.json` — jamais écraser le fichier principal
7. **Custom_image** = chemin relatif uniquement — jamais de chemin absolu dans le JSON
8. **Un seul utilisateur** — pas d'auth, pas de réseau
9. **Coordonnées (0,0) au centre** — conversion index ↔ coordonnées dans `grid.py` uniquement
10. **Commit Git pour chaque livrable** — format `type(scope): description`
11. **ast.parse() avant livraison** de tout fichier Python
12. **jsonschema** à chaque import — validation obligatoire
13. **Flood fill itératif** (pile explicite) pour éviter les RecursionError sur grandes salles
14. **25 tentatives maximum** pour les salles de transition — si échec, couloir simple sans salle
15. **Distance min 3 cases** entre salle de transition et salle manuelle
16. **30% de chance** d'ajouter une connexion supplémentaire (boucle) dans le graphe post-MST

---

## 🐛 BUGS CONNUS / PIÈGES À ÉVITER

*(sera rempli au fil du développement)*

- Flood fill récursif → RecursionError sur Python pour des salles > ~500 cases — utiliser une pile explicite
- QGraphicsScene : ne pas oublier `scene.setSceneRect()` sinon le scroll est erratique
- networkx MST : passer un graphe **pondéré** (distance euclidienne entre centres) sinon Kruskal est non-déterministe
- Coordonnées grille vs coordonnées scène : ne pas mélanger les espaces de coordonnées — encapsuler la conversion dans `grid.py`

---

## 📁 FICHIERS À UPLOADER EN DÉBUT DE SESSION

| Fichier | Phase | Peut être absent |
|---------|-------|-----------------|
| `app.py` | Toutes (dès 4b) | Oui (Phase 4a) |
| `core/grid.py` | Toutes (dès 4a) | Non |
| `core/generator.py` | 4e, 4f, V5 | Oui |
| `core/algorithms.py` | 4e, V5 | Oui |
| `io/serializer.py` | 4a, 4h, V5 | Oui |
| `ui/editor_view.py` | 4b, 4c, 4d | Oui |
| `ui/toolbar.py` | 4c, 4g | Oui |
| `ui/main_window.py` | 4f, 4g | Oui |

**Pour Phase 4a (modèle + serializer) :** aucun fichier existant à uploader — partir de zéro  
**Pour Phase 4b (canvas) :** `core/grid.py` + `io/serializer.py`  
**Pour Phase 4e (générateur) :** `core/grid.py` + `core/algorithms.py`  
**Pour bugfix génération :** `core/generator.py` + `core/algorithms.py` + `core/grid.py`  
**Pour bugfix UI :** `ui/editor_view.py` + `ui/main_window.py`

---

## 💡 CONTEXTE PROJET — ORIGINE

Ce projet est le portage Python/PyQt6 d'un éditeur initialement conçu en React + TypeScript + Canvas HTML5.
Le prompt original complet (architecture React, règles de génération procédurale, cas d'usage) est disponible dans `docs/PROMPT_ORIGINAL_REACT.md`.

Les différences majeures React → PyQt6 :
- Canvas HTML5 `requestAnimationFrame` → **QGraphicsView** avec invalidation sur modification
- LocalStorage → **fichier JSON** + autosave QTimer
- Interface tactile mobile → **desktop**, souris + clavier
- TypeScript types → **dataclasses Python** + type hints
- npm/bundler → **pip** + stdlib

---

*Dernière mise à jour : début de projet — Phase 4a non commencée*
