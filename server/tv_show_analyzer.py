#!/usr/bin/env python3

import os
import re
import argparse
from collections import defaultdict
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# Common video file extensions
VIDEO_EXTENSIONS = {'.mkv', '.mp4', '.avi', '.mov', '.wmv', '.flv'}

# Regex to find S##E## pattern (case-insensitive)
SEASON_EPISODE_REGEX = re.compile(r'[._\s-]S(\d{1,2})E(\d{1,3})[._\s-]', re.IGNORECASE)
# Regex to find just the season pattern for loose files (e.g., S01, s02)
SEASON_ONLY_REGEX = re.compile(r'[._\s-]S(\d{1,2})[._\s-]', re.IGNORECASE)
# Regex for season folders
SEASON_FOLDER_REGEX = re.compile(r'^Season (\d+)$', re.IGNORECASE)

def is_video_file(filename):
    """Check if a filename has a common video extension."""
    return os.path.splitext(filename)[1].lower() in VIDEO_EXTENSIONS

def parse_season_episode(filename):
    """Extract (season, episode) numbers from filename using S##E## pattern."""
    match = SEASON_EPISODE_REGEX.search(filename)
    if match:
        return int(match.group(1)), int(match.group(2))
    return None, None

def parse_season_only(filename):
    """Extract season number from filename using S## pattern."""
    match = SEASON_ONLY_REGEX.search(filename)
    if match:
        return int(match.group(1))
    return None

def get_release_tag(filename, season, episode):
    """Attempt to extract a consistent part of the filename after S##E##."""
    match = SEASON_EPISODE_REGEX.search(filename)
    if match:
        # Return the portion after the S##E## match
        return filename[match.end():].strip().lower()
    return filename.lower() # Fallback if pattern not found

def analyze_season_organization(target_path):
    """Identify video files in the root that could be organized into seasons."""
    logging.info(f"--- Checking Season Organization in '{target_path}' ---")
    files_to_organize = defaultdict(list)
    found_loose_files = False

    try:
        for item in os.listdir(target_path):
            item_path = os.path.join(target_path, item)
            if os.path.isfile(item_path) and is_video_file(item):
                season, _ = parse_season_episode(item)
                if season is None:
                    # Try parsing just the season if S##E## fails
                    season = parse_season_only(item)

                if season is not None:
                    files_to_organize[season].append(item)
                    found_loose_files = True
                # else:
                #     logging.warning(f"Could not determine season for loose file: {item}")

        if not found_loose_files:
            print("No loose video files needing season organization found.")
            return

        print("Potential Season Organization Needed:")
        for season_num, files in sorted(files_to_organize.items()):
            target_folder = f"Season {season_num}"
            print(f"  Would create folder: '{target_folder}'")
            for file in sorted(files):
                print(f"    - Move file: '{file}'")

    except FileNotFoundError:
        logging.error(f"Directory not found: {target_path}")
    except Exception as e:
        logging.error(f"Error checking season organization: {e}")


def analyze_existing_seasons(target_path):
    """Analyze existing 'Season X' folders for inconsistency and holes."""
    logging.info(f"--- Analyzing Existing Season Folders in '{target_path}' ---")
    found_season_folders = False

    try:
        for item in os.listdir(target_path):
            item_path = os.path.join(target_path, item)
            if os.path.isdir(item_path):
                match = SEASON_FOLDER_REGEX.match(item)
                if match:
                    found_season_folders = True
                    season_num = int(match.group(1))
                    print(f"\nAnalyzing Folder: '{item}' (Season {season_num})")
                    analyze_single_season_folder(item_path, season_num)

        if not found_season_folders:
            print("No 'Season X' folders found to analyze.")

    except FileNotFoundError:
        logging.error(f"Directory not found: {target_path}")
    except Exception as e:
        logging.error(f"Error analyzing existing seasons: {e}")


def analyze_single_season_folder(season_path, season_num):
    """Analyze a specific season folder for naming inconsistency and episode holes."""
    episodes = {}
    release_tags = set()
    filenames = []

    try:
        for item in os.listdir(season_path):
            item_path = os.path.join(season_path, item)
            if os.path.isfile(item_path) and is_video_file(item):
                s, e = parse_season_episode(item)
                filenames.append(item)
                if s is not None and e is not None:
                    if s != season_num:
                        logging.warning(f"  Mismatch: File '{item}' in Season {season_num} folder has S{s:02d}E{e:02d}.")
                        continue # Skip if season number in file doesn't match folder

                    if e in episodes:
                        logging.warning(f"  Duplicate episode number {e} found: '{item}' and '{episodes[e]}'")
                    episodes[e] = item
                    tag = get_release_tag(item, s, e)
                    if tag: # Avoid adding empty tags if extraction fails
                        release_tags.add(tag)
                # else:
                #     logging.warning(f"  Could not parse S##E## from: '{item}' in {season_path}")

        if not episodes:
            print("  No valid episode files found in this season folder.")
            return

        # 1. Naming Inconsistency Check
        # Simple check: if more than one distinct release tag pattern exists
        # More sophisticated checks could compare similarity, ignore common patterns etc.
        if len(release_tags) > 1:
            print(f"  Naming Inconsistency: Found multiple potential release patterns.")
            # Optionally print the different tags found for debugging
            # print(f"    Tags found: {release_tags}")
            # Optionally list all files for manual review
            # for fname in sorted(filenames):
            #      print(f"      - {fname}")
        else:
            print("  Naming Consistency: Appears consistent (based on simple tag check).")


        # 2. Season Hole Check
        if len(episodes) > 1:
            min_ep = min(episodes.keys())
            max_ep = max(episodes.keys())
            expected_episodes = set(range(min_ep if min_ep == 1 else 1, max_ep + 1))
            found_episodes = set(episodes.keys())
            missing_episodes = sorted(list(expected_episodes - found_episodes))

            if min_ep > 1:
                 print(f"  Season Hole: Starts at episode {min_ep}, not 1.")

            if missing_episodes:
                print(f"  Season Hole: Missing episode(s) between {min_ep if min_ep == 1 else 1}-{max_ep}: {missing_episodes}")
            else:
                 print(f"  Season Completeness: No episodes missing between {min_ep if min_ep == 1 else 1}-{max_ep}.")
        elif len(episodes) == 1:
             print(f"  Season Completeness: Only one episode (E{list(episodes.keys())[0]}) found.")
        # else handled above

    except FileNotFoundError:
        logging.error(f"Season directory not found during analysis: {season_path}")
    except Exception as e:
        logging.error(f"Error analyzing season folder '{season_path}': {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Analyze a TV show folder for organization, naming consistency, and missing episodes.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
        )
    parser.add_argument(
        "--path",
        default=".",
        help="Path to the TV show folder to analyze."
        )
    args = parser.parse_args()

    target_path = os.path.abspath(args.path)

    if not os.path.isdir(target_path):
        logging.error(f"Error: Provided path is not a valid directory: {target_path}")
        return

    print(f"Analyzing TV Show Folder: {target_path}\n")

    # Feature 1: Check for files needing season organization
    analyze_season_organization(target_path)
    print("-" * 40) # Separator

    # Feature 2 & 3: Analyze existing season folders
    analyze_existing_seasons(target_path)
    print("-" * 40) # Separator
    print("\nAnalysis Complete.")


if __name__ == "__main__":
    main()
