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

Les fichiers de données nécessaires sont déjà inclus dans le répertoire `data/processed`. Si vous souhaitez les régénérer, vous pouvez exécuter les scripts suivants dans l'ordre :

```bash
python3 -m src.items_extract --max-item 50000
python3 -m src.pano_extract --max-pano 1500
python3 -m src.preprocess
```

### 2. Lancer l'optimiseur

Pour trouver l'ensemble d'équipements optimal, exécutez le script `optimizer.py` avec les paramètres souhaités.

**Exemple :**

```bash
python3 src/optimizer.py --max-level 100 --pa 10 --pm 5 --weights characteristic_10:1.0 characteristic_11:0.5
```

Cette commande recherche l'équipement optimal pour un personnage jusqu'au niveau 100 avec 10 PA et 5 PM, en priorisant la Force (`characteristic_10`) et la Vitalité (`characteristic_11`) avec pondérations respectives.

**Arguments :**

* `--min-level` : Niveau minimum du personnage (par défaut : 1)
* `--max-level` : Niveau maximum du personnage (par défaut : 200)
* `--pa` : PA (Points d'Action) souhaités (par défaut : 12)
* `--pm` : PM (Points de Mouvement) souhaités (par défaut : 6)
* `--no-dofus` : Exclut les Dofus et les Trophées de l'optimisation
* `--weights` : Liste des caractéristiques et de leurs poids à optimiser. Par exemple, `characteristic_10:1.0` pour la Force avec un poids de 1.0.

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

Améliorations prévues : ajouter les bonus même quand inutile pour l'objectif (obligatoire d'avoir 2 si on a 3), ajouter les familiers/montures

