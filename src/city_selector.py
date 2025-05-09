"""
City Selector Module

This module provides functions for loading city data and selecting geographically
dispersed cities using a greedy algorithm.

Documentation for this algorithm can be found here :
https://arxiv.org/pdf/2103.16607
"""

import pandas as pd
import logging
import numpy as np
from sklearn.metrics.pairwise import haversine_distances

def load_city_data(csv_file : str, population_min : int =0):
    """
    Load city data from a CSV file and filter by minimum population.
    
    Args:
        csv_file : Path to the CSV file containing city data
        population_min : Minimum population threshold
        
    Returns:
        DataFrame containing filtered city data
    """
    logging.info(f"Loading city data from {csv_file}")
    cities_df = pd.read_csv(csv_file)
    
    # Filter by population if specified
    if population_min > 0:
        logging.info(f"Filtering cities with population >= {population_min}")
        cities_df = cities_df[cities_df['population'] >= population_min]
    
    logging.info(f"Loaded {len(cities_df)} cities")
    return cities_df

def post_process_city_selection(selected_cities, all_cities, min_distance_km=500):
    """
    Post-process selected cities to ensure minimum distance between any pair.
    
    Args:
        selected_cities: DataFrame of initially selected cities
        all_cities: DataFrame of all cities meeting population threshold
        min_distance_km: Minimum distance between cities in kilometers
        
    Returns:
        DataFrame of post-processed selected cities
    """
    from math import radians, sin, cos, sqrt, atan2
    
    def haversine_distance(lat1, lon1, lat2, lon2):
        # Earth radius in kilometers
        R = 6371.0
        
        # Convert degrees to radians
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        
        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        distance = R * c
        
        return distance
    
    # Create a copy of selected cities to modify
    improved_cities = selected_cities.copy()
    
    # Create a set of indices of cities already in the selection
    selected_indices = set(improved_cities.index)
    
    # Track if any improvements were made
    improvements_made = True
    iteration = 0
    
    logging.info(f"Starting post-processing to ensure minimum distance of {min_distance_km} km between cities")
    
    while improvements_made:
        iteration += 1
        improvements_made = False
        
        # Find the closest pair of cities
        min_dist = float('inf')
        closest_pair = None
        
        # Calculate distances between all pairs
        for i, city1 in improved_cities.iterrows():
            for j, city2 in improved_cities.iterrows():
                if i >= j:  # Skip self-comparisons and duplicates
                    continue
                
                dist = haversine_distance(
                    city1['lat'], city1['lng'],
                    city2['lat'], city2['lng']
                )
                
                # Check if this is the closest pair found so far
                if dist < min_dist:
                    min_dist = dist
                    closest_pair = (i, j)
        
        # If closest pair is too close, replace one of them
        if min_dist < min_distance_km and closest_pair is not None:
            logging.info(f"Iteration {iteration}: Found cities {improved_cities.loc[closest_pair[0]]['city']} and {improved_cities.loc[closest_pair[1]]['city']} only {min_dist:.1f} km apart")
            
            # Choose which city to replace (e.g., the less populous one)
            city1_pop = improved_cities.loc[closest_pair[0]]['population']
            city2_pop = improved_cities.loc[closest_pair[1]]['population']
            
            replace_idx = closest_pair[0] if city1_pop < city2_pop else closest_pair[1]
            
            city_to_replace = improved_cities.loc[replace_idx]
            logging.info(f"  Replacing {city_to_replace['city']} (pop: {city_to_replace['population']})")
            
            # Find the best replacement
            best_replacement = None
            max_min_distance = 0
            
            # Consider all cities not in the current selection
            for idx, candidate in all_cities.iterrows():
                if idx in selected_indices:
                    continue
                
                # Calculate minimum distance to all other selected cities
                min_distance = float('inf')
                for _, selected_city in improved_cities.iterrows():
                    if _ == replace_idx:  # Skip the city we're replacing
                        continue
                    
                    dist = haversine_distance(
                        candidate['lat'], candidate['lng'],
                        selected_city['lat'], selected_city['lng']
                    )
                    min_distance = min(min_distance, dist)
                
                # If this candidate has a better minimum distance, update
                if min_distance > max_min_distance:
                    max_min_distance = min_distance
                    best_replacement = candidate.copy()
                    best_replacement_idx = idx
            
            # If we found a better replacement, use it
            if best_replacement is not None and max_min_distance > min_dist:
                logging.info(f"  Replaced with {best_replacement['city']} (min distance: {max_min_distance:.1f} km)")
                improved_cities.loc[replace_idx] = best_replacement
                selected_indices.remove(replace_idx)
                selected_indices.add(best_replacement_idx)
                improvements_made = True
            else:
                logging.warning(f"  Could not find a better replacement, keeping original city")
        else:
            logging.warning(f"Iteration {iteration}: All cities are at least {min_distance_km} km apart (closest: {min_dist:.1f} km)")
            break
    
    logging.info(f"Post-processing complete after {iteration} iterations")
    return improved_cities

def select_dispersed_cities(cities_df, n_cities : int =200, min_distance_km : int =500):
    """
    Select geographically dispersed cities using a greedy algorithm.
    
    Args:
        cities_df : DataFrame containing city data
        n_cities : Number of cities to select
        min_distance_km : Minimum distance between cities in kilometers
        
    Returns:
        DataFrame containing selected cities
    """
    logging.info(f"Selecting {n_cities} geographically dispersed cities")
    
    # Ensure we have latitude and longitude columns
    if 'lat' not in cities_df.columns or 'lng' not in cities_df.columns:
        raise ValueError("City data must contain 'lat' and 'lng' columns")
    
    # Filter out cities with missing coordinates
    valid_cities = cities_df.dropna(subset=['lat', 'lng']).copy()
    logging.info(f"Found {len(valid_cities)} cities with valid coordinates")
    
    if len(valid_cities) < n_cities:
        logging.warning(f"Warning: Only {len(valid_cities)} cities available, less than requested {n_cities}")
        n_cities = len(valid_cities)
    
    # Convert coordinates to radians for haversine distance calculation
    coords_rad = np.radians(valid_cities[['lat', 'lng']].values)
    
    # Start with the most populous city
    valid_cities = valid_cities.sort_values('population', ascending=False)
    selected_indices = [0]  # Start with the most populous city
    
    # Greedy algorithm to select dispersed cities
    for i in range(1, n_cities):
        selected_coords = coords_rad[selected_indices]
        min_distances = []
        
        # Calculate minimum distance from each unselected city to any selected city
        for j in range(len(valid_cities)):
            if j in selected_indices:
                min_distances.append(-1)  # Already selected
                continue
                
            # Calculate haversine distances to all selected cities
            city_coord = coords_rad[j].reshape(1, -1)
            distances = haversine_distances(city_coord, selected_coords).flatten()
            
            # Convert from radians to kilometers (Earth radius ≈ 6371 km)
            distances_km = 6371.0 * distances
            
            # Find minimum distance to any selected city
            min_distances.append(np.min(distances_km))
        
        # Select the city with the maximum minimum distance
        next_city_idx = np.argmax(min_distances)
        selected_indices.append(next_city_idx)
    
    # Get the selected cities
    selected_cities = valid_cities.iloc[selected_indices].reset_index(drop=True)
    
    # Always apply post-processing
    selected_cities = post_process_city_selection(
        selected_cities, valid_cities, min_distance_km
    )
    
    return selected_cities 