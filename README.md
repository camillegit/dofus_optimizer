# Optimiseur d'Équipements Dofus

Ce projet est un outil en ligne de commande permettant de trouver l'ensemble d'équipements optimal pour un personnage Dofus en fonction des statistiques souhaitées.

Pour une explication de la construction du problème d'optimisation vous pouvez consulter l'[article dédié](https://camillegilbert.eu/posts/PanoplieOptimale/).

## Installation

1. Assurez-vous d'avoir Python 3 installé.
2. Installez les dépendances requises avec pip :

```bash
pip install -r requirements.txt
```

## Utilisation

### 1. Préparation des données (optionnel)

Les fichiers de données nécessaires sont déjà inclus dans le répertoire `data/processed`. Si vous souhaitez les régénérer (quelques secondes, via l'API paginée de DofusDB), vous pouvez exécuter les scripts suivants dans l'ordre :

```bash
python3 -m src.items_extract
python3 -m src.pano_extract
python3 -m src.preprocess
```

Les extractions brutes sont écrites dans `data/extracted/` (non versionné) et les fichiers prêts à l'emploi dans `data/processed/`. Les conditions d'équipement (`criterions`) sont extraites dans la colonne `condition`.

### 2. Lancer l'optimiseur

Pour trouver l'ensemble d'équipements optimal, exécutez le script `optimizer.py` avec les paramètres souhaités.

**Exemple :**

```bash
python3 src/optimizer.py --max-level 100 --pa 10 --pm 5 --weights characteristic_10:1.0 characteristic_11:0.5 --base-stats characteristic_10:200 characteristic_13:100 --min-stats characteristic_10:100 characteristic_13:300
```

Cette commande recherche l'équipement optimal pour un personnage jusqu'au niveau 100 avec 10 PA et 5 PM, en priorisant la Force (`characteristic_10`) et la Vitalité (`characteristic_11`) avec pondérations respectives.

**Arguments :**

* `--min-level` : Niveau minimum du personnage (par défaut : 1)
* `--max-level` : Niveau maximum du personnage (par défaut : 200)
* `--pa` : PA (Points d'Action) souhaités (par défaut : 9)
* `--pm` : PM (Points de Mouvement) souhaités (par défaut : 4)
* `--no-dofus` : Exclut les Dofus et les Trophées de l'optimisation
* `--weights` : Liste des caractéristiques et de leurs poids à optimiser. Par exemple, `characteristic_10:1.0` pour la Force avec un poids de 1.0.
* `--base-stats` : Stats de base ajoutées au personnage (ex. `characteristic_10:200 characteristic_13:100`). Ces stats sont prises en compte pour les conditions et les totaux affichés.
* `--min-stats` : Contraintes de stats minimales additionnelles (ex. `characteristic_10:100 characteristic_13:300`). PA/PM sont exclus ici, utilisez `--pa` et `--pm` pour cela.
* `--classe` : Classe du personnage (ex. `iop`, `Écaflip` ou son identifiant), pour les items réservés à une classe. Sans cette option, ces conditions sont considérées comme remplies.
* `--debug-pa-pm` : Affiche le détail des PA/PM (items, bonus de panoplie, base).
* `--solver-log` : Affiche le journal du solveur.

### Bonus de panoplie et conditions d'équipement

* Un seul palier de bonus est actif par panoplie : celui qui correspond au nombre exact de pièces portées (les paliers ne se cumulent pas, les malus de palier sont imposés).
* Les conditions d'équipement des items sont prises en compte : caractéristiques totales (`CS>399`, `CP<12|CM<6`…), caractéristiques de base (`Cs>99`, comparées à `--base-stats`) et nombre de bonus de panoplie actifs (`pk<2` : somme sur les panoplies de « pièces portées − 1 »). Les opérateurs ET (`&`), OU (`|`), les parenthèses et `!` (différent de) sont gérés.
* Les conditions qui ne dépendent pas des caractéristiques (métier, quête, alignement…, et classe si `--classe` n'est pas donné) sont considérées comme remplies ; le rapport liste les items concernés « à vérifier en jeu ».
* Le rapport vérifie indépendamment que les conditions des items retenus sont respectées par les stats finales.

Si aucune combinaison ne respecte les contraintes, le programme l'indique (statut du solveur) et retourne un code d'erreur.

### 3. Tests

```bash
pytest
```

## Caractéristiques disponibles

Le tableau suivant liste toutes les caractéristiques supportées ainsi que leurs identifiants internes. Ces identifiants sont utilisés lors de la définition des poids d'optimisation (ex. `characteristic_10`).

| ID caractéristique | Nom                   |
| ------------------ | --------------------- |
| -1                 | dommages Neutre       |
| 10                 | Force                 |
| 88                 | Dommages Terre        |
| 11                 | Vitalité              |
| 92                 | Dommages Neutre       |
| 15                 | Intelligence          |
| 78                 | Fuite                 |
| 0                  | Arme de chasse        |
| 18                 | % Critique            |
| 14                 | Agilité               |
| 79                 | Tacle                 |
| 23                 | PM                    |
| 49                 | Soins                 |
| 91                 | Dommages Air          |
| 12                 | Sagesse               |
| 13                 | Chance                |
| 48                 | Prospection           |
| 90                 | Dommages Eau          |
| 1                  | PA                    |
| 44                 | Initiative            |
| 19                 | Portée                |
| 89                 | Dommages Feu          |
| 16                 | Dommages              |
| 25                 | Puissance             |
| 86                 | Dommages Critiques    |
| 87                 | Résistances Critiques |
| 33                 | % Résistance Terre    |
| 26                 | Invocations           |
| 29                 |                       |
| 84                 | Dommages Poussée      |
| 37                 | % Résistance Neutre   |
| 82                 | Retrait PA            |
| 83                 | Retrait PM            |
| 34                 | % Résistance Feu      |
| 35                 | % Résistance Eau      |
| 36                 | % Résistance Air      |
| 58                 | Résistances Neutre    |
| 54                 | Résistances Terre     |
| 55                 | Résistances Feu       |
| 56                 | Résistances Eau       |
| 57                 | Résistances Air       |
| 28                 | Esquive PM            |
| 85                 | Résistances Poussée   |
| 40                 | Pods                  |
| 38                 |                       |
| 81                 |                       |
| 27                 | Esquive PA            |
| 69                 | Puissance Pièges      |
| 70                 | Dommages Pièges       |
| 50                 | Dommages Renvoyés     |
| 80                 |                       |
| 140                |                       |
| 124                | % Résistance mêlée    |
| 121                | % Résistance distance |
| 125                |                       |
| 120                |                       |
| 122                | Dommages d'armes      |
| 123                | Dommages aux sorts    |

Améliorations prévues : ajouter les familiers/montures
