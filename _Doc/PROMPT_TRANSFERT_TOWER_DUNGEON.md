# PROMPT DE TRANSFERT — Tower Dungeon Level Editor (v2)

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

## 📦 INSTALLATION SUR UN NOUVEAU PC

### Prérequis
- **Python 3.12+**
- **pip** à jour : `python -m pip install --upgrade pip`

### Dépendances
```bash
pip install PyQt6 networkx jsonschema
```

| Package | Usage |
|---------|-------|
| `PyQt6` 6.4+ | Interface graphique |
| `networkx` 3.0+ | MST de Kruskal (génération procédurale) |
| `jsonschema` 4.0+ | Validation schéma JSON à l'import |

### Lancer l'application
```bash
python app.py
```

### Lancer les tests
```bash
python -m unittest discover -s tests -v
```

---

## 🎯 VISION DU PROJET

Éditeur de level design **desktop local** (PyQt6) pour un jeu mobile **Tower Dungeon**.

- L'utilisateur dessine manuellement des salles sur une grille 72×72
- Un générateur procédural crée automatiquement les couloirs, murs et salles de transition
- Export/import JSON pour intégration dans le moteur de jeu **Godot**
- Interface desktop, un seul utilisateur, tout local

---

## 🏗️ ARCHITECTURE DES MODULES

```
app.py                          ← Point d'entrée
core/
  __init__.py
  grid.py                       ← Modèle : Cell, Floor, GridModel, CellType
  generator.py                  ← Génération procédurale (à faire — Phase 4e)
  algorithms.py                 ← Flood fill, MST, L-path (à faire — Phase 4e)
  populator.py                  ← Peuplement entités (futur — Phase 6)
serialization/
  __init__.py
  serializer.py                 ← Import/export JSON + validation jsonschema
  autosave.py                   ← Sauvegarde auto QTimer (à faire — Phase 4h)
ui/
  __init__.py
  main_window.py                ← Fenêtre principale + orchestration
  editor_view.py                ← Canvas QGraphicsView — rendu, zoom, pan, dessin
  toolbar.py                    ← (fusionné dans main_window pour l'instant)
  dialogs.py                    ← Dialogues génération/import/export (à faire)
tests/
  __init__.py
  test_grid.py                  ← 36 tests unitaires ✅
  test_serializer.py            ← 19 tests unitaires ✅
```

> ⚠️ Le dossier s'appelait `io/` dans les premières versions — il a été renommé en `serialization/` pour éviter le conflit avec le module stdlib Python `io`.

---

## 📐 SYSTÈME DE GRILLE

- **Dimensions :** 72×72 cellules
- **Coordonnées centrées :** (0,0) au centre
  - x ∈ [-36, 35], y ∈ [-36, 35]
  - x croît vers la droite, y croît vers le haut
- **Formule de conversion :**
  - `row = HALF - 1 - y` → y=35 → row=0, y=-36 → row=71
  - `col = HALF + x`     → x=-36 → col=0, x=35 → col=71
  - Centre (0,0) → index (row=35, col=36)
- **Rendu :** QGraphicsView + QGraphicsScene, une QPixmap par étage
- **NE PAS** instancier 5 184 widgets Qt — canvas unique obligatoire

### Signification de (0,0) pour Godot
La case (0,0) est **l'escalier d'entrée du niveau** (`STAIRS_DOWN`).
Elle est générée automatiquement par le générateur procédural — l'utilisateur ne la pose pas manuellement.
Le moteur Godot utilise cette case comme référence de positionnement.

---

## 🎨 TYPES DE CELLULES (CellType enum)

| Valeur enum | Rendu éditeur | Nom | Notes |
|------------|---------------|-----|-------|
| `EMPTY` | Couleur sombre | Vide | Défaut |
| `GROUND` | Couleur marron | Sol | Dessin manuel, base des salles |
| `WALL` | Couleur grise | Mur | Généré automatiquement |
| `ENEMY` | **Icône** | Ennemi | — |
| `BOSS` | **Icône** | Boss | Salle isolée |
| `TREASURE` | **Icône** | Trésor | Salle transition ou coin |
| `TRAP` | **Icône** | Piège | Couloirs étroits |
| `CAMP` | **Icône** | Camp | Salle sécurisée |
| `STAIRS_DOWN` | **Icône + marqueur (0,0)** | Escalier bas | **Forcé à (0,0)** |
| `STAIRS_UP` | **Icône** | Escalier haut | Salle isolée |
| `SPAWN` | **Icône** | Spawn | Point d'apparition |

> **Règle de rendu :** GROUND et WALL = couleur pleine. Tous les autres types = icône Unicode centrée sur la cellule.
> La case (0,0) affiche un **marqueur visuel spécifique** (croix ou highlight) pour indiquer l'origine du repère.

---

## 💾 FORMAT JSON D'EXPORT (figé — version 1)

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

- `grid` : 72 lignes × 72 colonnes, index [0][0] = coin haut-gauche
- `type` : valeur string de l'enum en minuscules
- `custom_image` : chemin relatif ou `null`
- Validation jsonschema obligatoire à l'import

---

## ⚙️ ALGORITHME DE GÉNÉRATION PROCÉDURALE (Phase 4e — non commencée)

```
1. Flood fill itératif → détection salles contiguës (GROUND)
2. Vérification taille min 6×6
3. MST Kruskal (networkx) sur centres géométriques
4. +30% connexions aléatoires supplémentaires
5. Tracé couloirs en L
6. Salles de transition 5×5 à 9×9 (25 tentatives max)
7. Murs extérieurs autour de tout
8. STAIRS_DOWN forcé à (0,0)
```

**Règle salle STAIRS_UP :** isolée, une seule connexion vers la salle la plus proche.
**Couloir en L :** `(ax,ay)→(bx,ay)→(bx,by)`
**Transition :** ❌ superposition salle manuelle, ❌ distance < 3 cases

---

## 🔧 DÉCISIONS TECHNIQUES ARRÊTÉES

> Validées et définitives — ne pas remettre en question.

1. **QGraphicsView + QGraphicsScene** pour le canvas
2. **networkx.minimum_spanning_tree** pour le MST
3. **Flood fill itératif** (pile explicite, pas récursif)
4. **JSON + jsonschema** pour la persistance
5. **QTimer 30s** → autosave `~/.tower_dungeon/autosave.json`
6. **Une QPixmap par étage**, invalidation partielle par cellule
7. **Coordonnées internes** : index tableau → conversion dans `grid.py` uniquement
8. **Rendu cellules :** GROUND/WALL = couleur pleine, autres = icône Unicode
9. **Marqueur (0,0)** : highlight visuel spécifique sur la case centre uniquement (pas une croix pleine sur toute la grille)
10. **Dossier `serialization/`** (pas `io/` — conflit stdlib Python)

---

## 🗺️ PLAN DE DÉVELOPPEMENT — CYCLE EN V

### ✅ Phases terminées

| Phase | Contenu | Statut |
|-------|---------|--------|
| **4a** | Modèle de données + serializer + 55 tests | ✅ Validé |
| **4b** | Canvas PyQt6, fenêtre, palette outils, zoom/pan, multi-étages | ✅ Validé |

### 🔧 En cours / à venir

| Phase | Contenu | Fichiers |
|-------|---------|----------|
| **4b-fix** | Améliorations visuelles canvas : icônes sur cellules entités, marqueur (0,0) | `ui/editor_view.py` |
| **4c** | Outils avancés : taille de pinceau, raccourcis clavier | `ui/editor_view.py`, `ui/main_window.py` |
| **4d** | Navigation multi-étages améliorée (déjà partiel dans 4b) | `ui/toolbar.py` |
| **4e** | Algorithmes + générateur procédural | `core/algorithms.py`, `core/generator.py` |
| **4f** | Bouton "Générer couloirs et murs" + logs | `ui/main_window.py`, `ui/dialogs.py` |
| **4g** | Import / Export JSON + dialog fichier | `ui/dialogs.py`, `serialization/serializer.py` |
| **4h** | Autosave QTimer | `serialization/autosave.py` |
| **5** | Upload sprites personnalisés | `ui/dialogs.py`, `core/grid.py` |
| **6** | Peuplement d'entités (sliders + placement intelligent) | `core/populator.py` |
| **7** | Tests d'intégration pipeline complet | `tests/` |
| **8** | Packaging .exe PyInstaller | — |

---

## 📋 AVANCEMENT PAR MODULE

| Module | Statut | Notes |
|--------|--------|-------|
| `core/grid.py` | ✅ Complet | 55 tests passent |
| `serialization/serializer.py` | ✅ Complet | Import/export + jsonschema |
| `app.py` | ✅ Complet | Point d'entrée fonctionnel |
| `ui/main_window.py` | ✅ Fonctionnel | Palette outils, étages, status bar |
| `ui/editor_view.py` | 🔧 En amélioration | Icônes entités + marqueur (0,0) à faire |
| `core/algorithms.py` | 🔲 À faire | Phase 4e |
| `core/generator.py` | 🔲 À faire | Phase 4e |
| `serialization/autosave.py` | 🔲 À faire | Phase 4h |
| `ui/dialogs.py` | 🔲 À faire | Phase 4f/4g |
| `core/populator.py` | 🔲 Futur | Phase 6 |

---

## 🚦 HISTORIQUE DES COMMITS

| Tag | Description | Commit |
|-----|-------------|--------|
| 4a | Modèle de données + serializer + tests | `feat(core): Phase 4a — grid model, serializer, unit tests` |
| 4b | Canvas PyQt6 fonctionnel | `feat(ui): Phase 4b — editor view, main window, zoom/pan` |

---

## 🐛 BUGS CORRIGÉS — NE PAS REPRODUIRE

- `coords_to_index` : formule initiale `row = HALF - y` fausse → corrigée en `row = HALF - 1 - y`
- `io/` renommé en `serialization/` — conflit avec module stdlib Python `io`
- Tests `test_serializer.py` : fixture `tmp_path` pytest incompatible avec unittest → remplacée par `setUp/tearDown + tempfile`
- `__init__.py` manquants dans `core/`, `serialization/`, `tests/` → à toujours créer lors d'un nouveau package

---

## 🔒 CONTRAINTES PERMANENTES

1. **Ne jamais** instancier 5 184 widgets Qt — canvas QGraphicsView obligatoire
2. **STAIRS_DOWN forcé à (0,0)** — généré par le générateur, jamais par l'utilisateur
3. **Salles manuelles minimum 6×6** — refus avec message d'erreur sinon
4. **Salle STAIRS_UP isolée** — une seule connexion sortante dans le MST
5. **Import JSON invalide** = refus + message d'erreur — jamais de corruption silencieuse
6. **Autosave** → `~/.tower_dungeon/autosave.json` — jamais écraser le fichier principal
7. **custom_image** = chemin relatif uniquement
8. **Un seul utilisateur** — pas d'auth, pas de réseau
9. **Coordonnées (0,0) = escalier d'entrée Godot** — ne jamais changer cette convention
10. **Commit Git pour chaque livrable**
11. **ast.parse() avant toute livraison** de fichier Python
12. **Rendu :** GROUND/WALL = couleur pleine, entités = icône Unicode sur fond coloré
13. **Marqueur (0,0)** = highlight sur la case uniquement, pas une croix traversant toute la grille
14. **Flood fill itératif** — jamais récursif (RecursionError sur grandes surfaces)
15. **25 tentatives max** pour les salles de transition

---

## 📁 FICHIERS À UPLOADER EN DÉBUT DE SESSION

| Fichier | Phase | Obligatoire |
|---------|-------|-------------|
| `core/grid.py` | Toutes | Oui |
| `serialization/serializer.py` | Toutes | Oui |
| `app.py` | 4b+ | Oui |
| `ui/main_window.py` | 4b+ | Oui |
| `ui/editor_view.py` | 4b-fix, 4c, 4d | Oui |
| `core/algorithms.py` | 4e | Non (pas encore créé) |
| `core/generator.py` | 4e, 4f | Non (pas encore créé) |
| `ui/dialogs.py` | 4f, 4g | Non (pas encore créé) |
| `tests/test_grid.py` | QA | Non |
| `tests/test_serializer.py` | QA | Non |

**Pour 4b-fix (améliorations visuelles) :** `ui/editor_view.py` + `core/grid.py`
**Pour 4e (générateur) :** `core/grid.py` uniquement — partir de zéro pour algorithms.py et generator.py
**Pour bugfix canvas :** `ui/editor_view.py` + `ui/main_window.py`

---

*Dernière mise à jour : Phase 4b validée — en cours : 4b-fix (icônes entités + marqueur 0,0)*