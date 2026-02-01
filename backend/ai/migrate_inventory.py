#!/usr/bin/env python3
"""
Migrate inventory from JSON format to EchoMTG CSV format
Combines card data with location/position information
"""

import csv
import json
import sys
from pathlib import Path


def load_inventory_data(json_path):
    """Load inventory data from JSON file"""
    with open(json_path, 'r') as f:
        data = json.load(f)
    return data

def load_echomtg_csv(csv_path):
    """Load EchoMTG export CSV"""
    cards = {}
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Use card name, set, and collector number as unique key
            key = f"{row['Name']}|{row['Set']}|{row['Collector Number']}"
            cards[key] = row
    return cards

def match_card_to_location(card_name, card_set, collector_num, inventory_data):
    """Find matching card in inventory data by name, set, and collector number"""
    for item in inventory_data:
        if (item['name'].lower() == card_name.lower() and 
            item['set'].lower() == card_set.lower() and
            item['collector_number'] == collector_num):
            return item
    return None

def create_location_note(location, pos):
    """Create location note string"""
    return f"Location: {location}, Position: {pos}"

def map_condition_to_echomtg(condition):
    """Map condition to EchoMTG format"""
    condition_map = {
        'near mint': 'NM',
        'nm': 'NM',
        'lightly played': 'LP', 
        'lp': 'LP',
        'moderately played': 'MP',
        'mp': 'MP',
        'heavily played': 'HP',
        'hp': 'HP',
        'damaged': 'D',
        'd': 'D'
    }
    return condition_map.get(condition.lower(), 'NM')

def map_language_to_echomtg(lang):
    """Map language to EchoMTG format"""
    if not lang:
        return 'EN'
    lang_map = {
        'en': 'EN',
        'english': 'EN'
    }
    return lang_map.get(lang.lower(), 'EN')

def main():
    # File paths
    json_path = Path("/Users/sloscal1/Code/text_search/inventory_mtg (7).json")
    output_path = Path("/Users/sloscal1/Code/text_search/inventory_with_locations_7.csv")
    
    # Load data
    print("Loading inventory data...")
    inventory_data = load_inventory_data(json_path)
    print(f"Loaded {len(inventory_data)} items from inventory")
    
    # Prepare output rows
    output_rows = []
    
    # Add header row
    fieldnames = [
        'Reg Qty', 'Foil Qty', 'Name', 'Set', 'Rarity', 'Acquired', 
        'Language', 'Date Acquired', 'Set Code', 'Collector Number', 
        'Condition', 'Marked as Trade', 'note', 'echo_inventory_id', 'tcgid', 'echoid'
    ]
    
    processed_count = 0
    
    for item in inventory_data:
        # Create location note
        location_note = create_location_note(item['location'], item['pos'])
        
        # Convert inventory item to EchoMTG format
        row = {
            'Reg Qty': 1 if item['finishes'] == 'nonfoil' else 0,
            'Foil Qty': 1 if item['finishes'] == 'foil' else 0,
            'Name': item['name'],
            'Set': item['set'].upper(),  # Use set code as set name for now
            'Rarity': '',  # Not available in inventory data
            'Acquired': '',  # Not available in inventory data
            'Language': map_language_to_echomtg(item['lang']),
            'Date Acquired': '',  # Not available in inventory data
            'Set Code': item['set'].upper(),
            'Collector Number': item['collector_number'],
            'Condition': map_condition_to_echomtg(item['condition']),
            'Marked as Trade': '0',
            'note': location_note,
            'echo_inventory_id': '',  # Will be assigned by EchoMTG
            'tcgid': '',  # Not available in inventory data
            'echoid': ''  # Will be assigned by EchoMTG
        }
        
        output_rows.append(row)
        processed_count += 1
    
    # Write output CSV
    print(f"Writing output to {output_path}")
    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)
    
    print(f"\nMigration complete!")
    print(f"Converted {processed_count} cards to EchoMTG format")
    print(f"Total cards: {len(output_rows)}")
    print(f"Output saved to: {output_path}")
    
    # Show sample of converted data
    print(f"\nSample of converted data:")
    for i, row in enumerate(output_rows[:3]):
        print(f"{i+1}. {row['Name']} ({row['Set Code']}) - {row['note']}")

if __name__ == "__main__":
    main()