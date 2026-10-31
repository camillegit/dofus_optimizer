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
python3 src/optimizer.py --max-level 100 --pa 10 --pm 5 --weights force:1.0 vita:0.5 --base-stats force:200 chance:100 --min-stats force:100 chance:300
```

Cette commande recherche l'équipement optimal pour un personnage jusqu'au niveau 100 avec 10 PA et 5 PM, en priorisant la Force et la Vitalité avec pondérations respectives, avec au moins 100 de Force et 300 de Chance (stats de base comprises).

**Arguments :**

* `--min-level` : Niveau minimum du personnage (par défaut : 1)
* `--max-level` : Niveau maximum du personnage (par défaut : 200)
* `--pa` : PA (Points d'Action) souhaités (par défaut : 9)
* `--pm` : PM (Points de Mouvement) souhaités (par défaut : 4)
* `--no-dofus` : Exclut les Dofus et les Trophées de l'optimisation
* `--no-pet` : Exclut les familiers, montiliers et montures (Dragodinde, Muldo, Volkorne)
* `--weights` : Liste des caractéristiques et de leurs poids à optimiser. Par exemple, `force:1.0` (ou `characteristic_10:1.0`) pour la Force avec un poids de 1.0.
* `--base-stats` : Stats de base ajoutées au personnage (ex. `force:200 chance:100`). Ces stats sont prises en compte pour les conditions et les totaux affichés.
* `--min-stats` : Contraintes de stats minimales additionnelles (ex. `force:100 chance:300`). PA/PM sont exclus ici, utilisez `--pa` et `--pm` pour cela.
* `--classe` : Classe du personnage (ex. `iop`, `Écaflip` ou son identifiant), pour les items réservés à une classe. Sans cette option, ces conditions sont considérées comme remplies.
* `--list-stats` : Affiche la liste des caractéristiques et de leurs alias.
* `--debug-pa-pm` : Affiche le détail des PA/PM (items, bonus de panoplie, base).
* `--solver` : Solveur MILP, `cbc` (par défaut, fourni avec PuLP) ou `highs` (nécessite `pip install highspy`). Sur ce modèle CBC est le plus rapide (< 1 s par scénario).
* `--solver-log` : Affiche le journal du solveur.

### Familiers et montures

Familiers, montiliers et montures (Dragodinde, Muldo, Volkorne) occupent un emplacement unique commun. Leurs caractéristiques sont celles indiquées par DofusDB : familier nourri au maximum, monture au niveau maximal. Les objets réservés aux maîtres du jeu (suffixe « (MJ) ») sont exclus.

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

Les caractéristiques peuvent être désignées par leur alias, leur nom (`Vitalité`), leur identifiant (`11`) ou leur nom de colonne (`characteristic_11`), dans `--weights`, `--base-stats` et `--min-stats`. La liste est aussi affichée par `--list-stats`.

| ID | Alias | Nom |
| --- | --- | --- |
| -1 | `inconnue` | Inconnue |
| 0 | `vie` | Points de vie |
| 1 | `pa` | PA |
| 10 | `force` | Force |
| 11 | `vitalite`, `vita` | Vitalité |
| 12 | `sagesse`, `sage` | Sagesse |
| 13 | `chance` | Chance |
| 14 | `agilite`, `agi` | Agilité |
| 15 | `intelligence`, `intel` | Intelligence |
| 16 | `dommages`, `do` | Dommages |
| 18 | `critique`, `crit` | % Critique |
| 19 | `portee`, `po` | Portée |
| 23 | `pm` | PM |
| 25 | `puissance`, `pui` | Puissance |
| 26 | `invocations`, `invo` | Invocations |
| 27 | `esquive_pa` | Esquive PA |
| 28 | `esquive_pm` | Esquive PM |
| 33 | `res_terre_pct` | % Résistance Terre |
| 34 | `res_feu_pct` | % Résistance Feu |
| 35 | `res_eau_pct` | % Résistance Eau |
| 36 | `res_air_pct` | % Résistance Air |
| 37 | `res_neutre_pct` | % Résistance Neutre |
| 40 | `pods` | Pods |
| 44 | `initiative`, `ini` | Initiative |
| 48 | `prospection`, `prospe` | Prospection |
| 49 | `soins` | Soins |
| 50 | `renvoi` | Dommages renvoyés |
| 54 | `res_terre` | Résistance Terre |
| 55 | `res_feu` | Résistance Feu |
| 56 | `res_eau` | Résistance Eau |
| 57 | `res_air` | Résistance Air |
| 58 | `res_neutre` | Résistance Neutre |
| 69 | `puissance_pieges` | Puissance Pièges |
| 70 | `dommages_pieges` | Dommages Pièges |
| 78 | `fuite` | Fuite |
| 79 | `tacle` | Tacle |
| 82 | `retrait_pa` | Retrait PA |
| 83 | `retrait_pm` | Retrait PM |
| 84 | `dommages_poussee` | Dommages Poussée |
| 85 | `res_poussee` | Résistance Poussée |
| 86 | `dommages_critiques`, `docri` | Dommages Critiques |
| 87 | `res_critiques` | Résistance Critiques |
| 88 | `dommages_terre` | Dommages Terre |
| 89 | `dommages_feu` | Dommages Feu |
| 90 | `dommages_eau` | Dommages Eau |
| 91 | `dommages_air` | Dommages Air |
| 92 | `dommages_neutre` | Dommages Neutre |
| 120 | `dommages_distance_pct` | % Dommages distance |
| 121 | `res_distance_pct` | % Résistance distance |
| 122 | `dommages_armes_pct` | % Dommages d'armes |
| 123 | `dommages_sorts_pct` | % Dommages aux sorts |
| 124 | `res_melee_pct` | % Résistance mêlée |
| 125 | `dommages_melee_pct` | % Dommages mêlée |
| 140 | `taille` | Taille (%) |

