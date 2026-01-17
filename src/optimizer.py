
import pandas as pd
from pulp import LpMaximize, LpProblem, LpVariable, lpSum
import re
import argparse
import glob
from pathlib import Path


def load_data():
    """Loads items and panoplies data from the data/processed directory."""
    
    # Get the directory of the current script
    script_dir = Path(__file__).parent
    
    # Construct the path to the data/processed directory relative to the script
    data_processed_dir = script_dir.parent / 'data' / 'processed'
    
    items_df = pd.read_parquet(data_processed_dir / 'dofus_items_processed.parquet')
    bonuses_df = pd.read_parquet(data_processed_dir / 'dofus_panos_processed.parquet')

    # Replace NaN values with 0
    items_df.fillna(0, inplace=True)
    bonuses_df.fillna(0, inplace=True)
    
    return items_df, bonuses_df


def main():
    parser = argparse.ArgumentParser(description='Dofus Stuff Optimizer')
    parser.add_argument('--min-level', type=int, default=1, help='Minimum character level')
    parser.add_argument('--max-level', type=int, default=200, help='Maximum character level')
    parser.add_argument('--pa', type=int, default=9, help='Desired PA')
    parser.add_argument('--pm', type=int, default=4, help='Desired PM')
    parser.add_argument('--no-dofus', action='store_true', help='Exclude Dofus and Trophies')
    parser.add_argument('--weights', nargs='+', default=[], help='List of characteristics and weights (e.g., characteristic_13:1.0)')
    
    args = parser.parse_args()
    
    print("Loading data...")
    items_df, bonuses_df = load_data()
    print("Data loaded.")

    # Step 1: Filter items by level
    items_df = items_df[(items_df['niveau'] >= args.min_level) & (items_df['niveau'] <= args.max_level)]

    # Filter out banned items
    to_drop = [2155, 8575, 27265, 27266, 27267, 27268, 27278, 27280, 27282, 9031, 2447]
    items_df = items_df[~items_df['id'].isin(to_drop)]

    # Step 2: Define ILP variables
    item_vars = {row['id']: LpVariable(f"item_{row['id']}", cat='Binary') for _, row in items_df.iterrows()}

    bonus_vars = {}
    unique_panos = items_df['pano'].unique()
    
    # Filter panos that are in bonuses_df
    valid_pano_ids = bonuses_df['id'].unique()
    filtered_panos = [pano for pano in unique_panos if pano != -1 and pano in valid_pano_ids]

    for set_id in filtered_panos:
        count = items_df[items_df['pano'] == set_id].shape[0]
        if count >= 2:
            for k in range(2, count + 1):
                bonus_vars[set_id, k] = LpVariable(f"bonus_{set_id}_{k}", cat='Binary')

    # Step 3: Create the ILP problem
    problem = LpProblem("Optimal_Stuff_Combination", LpMaximize)

    # Step 4: Constraints on types
    type_groups = items_df.groupby('type')
    for item_type, group in type_groups:
        limit = 1
        if item_type == 9:
            limit = 2
        elif item_type in [151, 23]:
            limit = 6
        elif item_type in [3, 7, 4, 2, 5, 6, 19, 22, 8]:
            continue

        problem += lpSum(item_vars[item_id] for item_id in group['id']) <= limit, f"Type_{item_type}_Constraint"

    grouped_types = [3, 7, 4, 2, 5, 6, 19, 22, 8]
    item_types = items_df.set_index('id')['type'].to_dict()
    grouped_items = [item_id for item_id, item_type in item_types.items() if item_type in grouped_types]
    problem += lpSum(item_vars[item_id] for item_id in grouped_items) <= 1, "Grouped_Types_Constraint"

    # Step 5: Constraints on bonuses
    for set_id in filtered_panos:
        count = items_df[items_df['pano'] == set_id].shape[0]
        if count >= 2:
            id_values = items_df[items_df['pano'] == set_id]['id'].tolist()
            for k in range(2, count + 1):
                problem += bonus_vars[(set_id, k)] <= lpSum(item_vars[item_id] for item_id in id_values) / k, f"Bonus_{set_id}_{k}_Constraint"
    
    # Step 6: Parse weights
    characteristics_of_interest = [w.split(':')[0] for w in args.weights]
    weights = [float(w.split(':')[1]) for w in args.weights]

    # Step 7: Calculate weighted characteristics for items
    item_characteristics = {
        item_id: sum(row[char] * weight for char, weight in zip(characteristics_of_interest, weights))
        for item_id, row in items_df.set_index('id').iterrows()
    }

    # Step 8: Calculate weighted characteristics for bonuses
    bonus_characteristics = {}
    for set_id in filtered_panos :
        count = items_df[items_df['pano'] == set_id].shape[0]
        if count >= 2:
            for k in range(2, count + 1):
                row = bonuses_df[bonuses_df['id'] == set_id]
                if not row.empty:
                    weighted_sum = 0
                    for characteristic, weight in zip(characteristics_of_interest, weights):
                        column_name = f"bonus_{k}_{characteristic}"
                        if column_name in bonuses_df.columns:
                            value = row[column_name].iloc[0]
                            weighted_sum += value * weight
                
                    key = (set_id, k)
                    bonus_characteristics[key] = weighted_sum
    
    # Step 9: Constraints on minimum PA
    min_PA_input = args.pa # Renaming for clarity based on user's request

    if args.max_level >= 100:
        base_PA = 6
        min_PA = min_PA_input - base_PA
    else:
        base_PA = 5
        min_PA = min_PA_input - base_PA

    # Ensure min_PA is not negative
    min_PA = max(0, min_PA) # PA cannot be negative

    ## PA Bonus of the items
    item_characteristics_PA = {
        item_id: row["characteristic_1"]
        for item_id, row in items_df.set_index('id').iterrows()}

    ## PA Bonus of the set

    bonus_PA = {}
    for set_id in filtered_panos :
        count = items_df[items_df['pano'] == set_id].shape[0]  # Count occurrences
        if count >= 2:
            for k in range(2, count + 1):
                row_PA = bonuses_df[bonuses_df['id'] == set_id]  # Get the row matching set_id
                if not row_PA.empty:
                    weighted_sum_PA = 0

                    column_name = f"bonus_{k}_characteristic_1"
                    if column_name in bonuses_df.columns:  # Check if the column exists
                        value = row_PA[column_name].iloc[0]  # Get the value for the characteristic
                        weighted_sum_PA += value

                        key = (set_id, k)
                        bonus_PA[key] = weighted_sum_PA
            
    problem += (
        lpSum(
            # Sum of individual item contributions
            item_vars[item_id] * item_characteristics_PA.get(item_id, 0)
            for item_id in item_vars
        ) +
        lpSum(
            # Sum of set bonus contributions
            bonus_vars[key] * bonus_PA.get(key, 0)
            for key in bonus_vars
        ) >= min_PA, "Minimum_PA_Constraint")
    
    # Step 10: Constraints on minimum PM
    min_PM_input = args.pm
    base_PM = 2
    min_PM = min_PM_input - base_PM
    min_PM = max(0, min_PM) # PM cannot be negative

    ## PM Bonus of the items
    item_characteristics_PM = {
        item_id: row["characteristic_23"]
        for item_id, row in items_df.set_index('id').iterrows()}

    ## PM Bonus of the set

    bonus_PM = {}
    for set_id in filtered_panos :
        count = items_df[items_df['pano'] == set_id].shape[0]  # Count occurrences
        if count >= 2:
            for k in range(2, count + 1):
                row_PM = bonuses_df[bonuses_df['id'] == set_id]  # Get the row matching set_id
                if not row_PM.empty:
                    weighted_sum_PM = 0

                    column_name = f"bonus_{k}_characteristic_23"
                    if column_name in bonuses_df.columns:  # Check if the column exists
                        value = row_PM[column_name].iloc[0]  # Get the value for the characteristic
                        weighted_sum_PM += value

                        key = (set_id, k)
                        bonus_PM[key] = weighted_sum_PM
        
    problem += (
        lpSum(
            # Sum of individual item contributions
            item_vars[item_id] * item_characteristics_PM.get(item_id, 0)
            for item_id in item_vars
        ) +
        lpSum(
            # Sum of set bonus contributions
            bonus_vars[key] * bonus_PM.get(key, 0)
            for key in bonus_vars
        ) >= min_PM, "Minimum_PM_Constraint")
    
    # Step 11: Define the objective function
    problem += lpSum(
        item_vars[item_id] * item_characteristics[item_id] for item_id in item_vars
    ) + lpSum(
        bonus_vars[key] * bonus_characteristics[key] for key in bonus_vars
    ), "Total_Weighted_Stats"

    # Step 12: Solve the problem
    print("\nSolving the optimization problem...")
    problem.solve()
    print("Problem solved.")

    # Step 13: Print the results
    print("\nÉquipement optimal:")
    
    char_id_to_name = {
        -1: "dommages Neutre", 10: "Force", 88: "Dommages Terre", 11: "Vitalité",
        92: "Dommages Neutre", 15: "Intelligence", 78: "Fuite", 0: "Arme de chasse",
        18: "% Critique", 14: "Agilité", 79: "Tacle", 23: "PM", 49: "Soins",
        91: "Dommages Air", 12: "Sagesse", 13: "Chance", 48: "Prospection",
        90: "Dommages Eau", 1: "PA", 44: "Initiative", 19: "Portée",
        89: "Dommages Feu", 16: "Dommages", 25: "Puissance", 86: "Dommages Critiques",
        87: "Résistances Critiques", 33: "% Résistance Terre", 26: "Invocations",
        84: "Dommages Poussée", 37: "% Résistance Neutre", 82: "Retrait PA",
        83: "Retrait PM", 34: "% Résistance Feu", 35: "% Résistance Eau",
        36: "% Résistance Air", 58: "Résistances Neutre", 54: "Résistances Terre",
        55: "Résistances Feu", 56: "Résistances Eau", 57: "Résistances Air",
        28: "Esquive PM", 85: "Résistances Poussée", 40: "Pods", 27: "Esquive PA",
        69: "Puissance Pièges", 70: "Dommages Pièges", 50: "Dommages Renvoyés",
        124: "% Résistance mêlée", 121: "% Résistance distance",
        122: "Dommages d'armes", 123: "Dommages aux sorts"
    }

    # Define stats to always display, plus the ones from the weights
    stats_to_display = set(['characteristic_1', 'characteristic_23', 'characteristic_19'])
    for char in characteristics_of_interest:
        stats_to_display.add(char)

    total_stats = {stat: 0 for stat in stats_to_display}

    equip_types_map = {
        16: "Chapeau", 17: "Cape", 9: "Anneau", 1: "Amulette", 3: "Baguette",
        11: "Bottes", 10: "Ceinture", 7: "Marteau", 4: "Bâton", 2: "Arc",
        5: "Dague", 6: "Épée", 19: "Hache", 22: "Faux", 8: "Pelle",
        151: "Trophée", 23: "Dofus", 82: "Boucliers"
    }

    selected_items = []
    for item_id, var in item_vars.items():
        if var.value() == 1:
            item_data = items_df[items_df['id'] == item_id].iloc[0]
            selected_items.append(item_data)
            item_type_id = item_data['type']
            item_type_name = equip_types_map.get(item_type_id, "Unknown Type")
            print(f"- Item ID: {item_id}, Nom: {item_data['nom']}, Type: {item_type_name}")
            for char in stats_to_display:
                if char in item_data:
                    total_stats[char] += item_data[char]

    print("\nBonus panoplies:")
    for (set_id, k), var in bonus_vars.items():
        if var.value() == 1:
            pano_data = bonuses_df[bonuses_df['id'] == set_id].iloc[0]
            print(f"- Panoplie: {pano_data['nom']}, Niveau: {k}")
            for char in stats_to_display:
                col_name = f"bonus_{k}_{char}"
                if col_name in pano_data:
                    total_stats[char] += pano_data[col_name]
    
    print("\nStats totales:")
    # Add base stats
    if args.max_level >= 100:
        total_stats['characteristic_1'] += 6
    else:
        total_stats['characteristic_1'] += 5
    total_stats['characteristic_23'] += 2
    
    for char, value in total_stats.items():
        char_id = int(char.split('_')[1])
        char_name = char_id_to_name.get(char_id, char)
        print(f"- {char_name}: {value}")


if __name__ == '__main__':
    main()
