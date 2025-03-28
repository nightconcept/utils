#!/usr/bin/env python3

import os
import re
import argparse
from collections import defaultdict
import logging
from typing import Tuple, Dict, List, Optional, Set

# Configure logging
# logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
# Quieter default logging
logging.basicConfig(level=logging.WARNING, format='%(levelname)s: %(message)s')

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

# --- Analysis Functions ---

def analyze_season_organization(show_path: str):
    """
    Identify video files in the root of a show folder that could be organized into seasons.
    Returns True if potential organization is needed, False otherwise.
    """
    print(f"\n--- Checking Season Organization ---")
    files_to_organize: Dict[int, List[str]] = defaultdict(list)
    found_loose_files = False

    try:
        # Only check files directly in the show path, not subdirs like 'Season X'
        for item in os.listdir(show_path):
            item_path = os.path.join(show_path, item)
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
            print("  No loose video files needing season organization found.")
            return False # No organization needed

        print("  Potential Season Organization Needed:")
        for season_num, files in sorted(files_to_organize.items()):
            target_folder = f"Season {season_num}"
            print(f"  Would create folder: '{target_folder}'")
            for file in sorted(files):
                print(f"    - Move file: '{file}'")

        return True # Organization needed

    except FileNotFoundError:
        logging.error(f"Show directory not found during organization check: {show_path}")
    except Exception as e:
        logging.error(f"Error checking season organization for '{show_path}': {e}")
    return False # Assume no organization needed on error


def analyze_existing_seasons(show_path: str) -> Tuple[bool, bool]:
    """
    Analyze existing 'Season X' folders within a show folder for inconsistency and holes.
    Returns a tuple: (all_seasons_consistent, all_seasons_complete)
    """
    print(f"\n--- Analyzing Existing Season Folders ---")
    season_folders_found = False
    all_consistent = True
    all_complete = True
    season_results = {} # Store results per season

    try:
        items = sorted(os.listdir(show_path)) # Sort for consistent order
        for item in items:
            item_path = os.path.join(show_path, item)
            if os.path.isdir(item_path):
                match = SEASON_FOLDER_REGEX.match(item)
                if match:
                    season_folders_found = True
                    season_num = int(match.group(1))
                    print(f"\n  Analyzing Folder: '{item}' (Season {season_num})")
                    consistent, complete = analyze_single_season_folder(item_path, season_num)
                    season_results[season_num] = (consistent, complete)
                    if not consistent:
                        all_consistent = False
                    if not complete:
                        all_complete = False

        if not season_folders_found:
            print("  No 'Season X' folders found to analyze.")
            # If no season folders, it's trivially consistent and complete
            return True, True

    except FileNotFoundError:
        logging.error(f"Show directory not found during season analysis: {show_path}")
        return False, False # Error state
    except Exception as e:
        logging.error(f"Error analyzing existing seasons for '{show_path}': {e}")
        return False, False # Error state

    return all_consistent, all_complete


def analyze_single_season_folder(season_path: str, season_num: int) -> Tuple[bool, bool]:
    """
    Analyze a specific season folder for naming inconsistency and episode holes.
    Returns a tuple: (is_consistent, is_complete)
    """
    episodes: Dict[int, str] = {}
    release_tags: Set[str] = set()
    filenames: List[str] = []
    is_consistent = True
    is_complete = True

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
            print("    No valid episode files found in this season folder.")
            # Considered complete if empty, but inconsistent might be debatable (let's say consistent)
            return True, True

        # 1. Naming Inconsistency Check
        if len(release_tags) > 1:
            print(f"    ❌ Naming Inconsistency: Found {len(release_tags)} potential release patterns.")
            is_consistent = False
            # Optional debugging:
            # print(f"      Tags found: {', '.join(sorted(list(release_tags)))}")
            # for fname in sorted(filenames):
            #     print(f"        - {fname}")
        else:
            print(f"    ✅ Naming Consistency: Appears consistent.")

        # 2. Season Hole Check
        min_ep = min(episodes.keys())
        max_ep = max(episodes.keys())

        if len(episodes) == 1:
             print(f"    ✅ Season Completeness: Only one episode (E{max_ep}) found.")
             is_complete = True # Single episode is considered complete unless it's not E01? Let's stick to no gaps.
        else:
            expected_episodes = set(range(1, max_ep + 1)) # Assume seasons start at 1
            found_episodes = set(episodes.keys())
            missing_episodes = sorted(list(expected_episodes - found_episodes))

            hole_messages = []
            if min_ep > 1:
                 hole_messages.append(f"Starts at episode {min_ep}, not 1.")
                 is_complete = False

            if missing_episodes:
                hole_messages.append(f"Missing episode(s): {missing_episodes}")
                is_complete = False

            if not hole_messages:
                 print(f"    ✅ Season Completeness: No episodes missing between 1-{max_ep}.")
                 is_complete = True
            else:
                 print(f"    ❌ Season Hole: {'; '.join(hole_messages)}")


    except FileNotFoundError:
        logging.error(f"Season directory not found during analysis: {season_path}")
        return False, False # Error state
    except Exception as e:
        logging.error(f"Error analyzing season folder '{season_path}': {e}")
        return False, False # Error state

    return is_consistent, is_complete


# --- Main Execution ---

def analyze_show(show_path: str) -> Tuple[bool, bool]:
    """Runs all analyses for a single show folder."""
    show_name = os.path.basename(show_path)
    print(f"\n{'='*10} Analyzing Show: {show_name} {'='*10}")

    needs_org = analyze_season_organization(show_path)
    all_consistent, all_complete = analyze_existing_seasons(show_path)

    print(f"\n--- Show Summary: {show_name} ---")
    print(f"  Needs Season Organization: {'Yes' if needs_org else 'No'}")
    print(f"  Overall Naming Consistency: {'✅ Consistent' if all_consistent else '❌ Inconsistent'}")
    print(f"  Overall Season Completeness: {'✅ Complete' if all_complete else '❌ Incomplete'}")

    return all_consistent, all_complete


def main():
    parser = argparse.ArgumentParser(
        description="Analyze TV show library for organization, naming consistency, and missing episodes.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "--path",
        required=True, # Make path required
        help="Path to the TV show library directory (containing show folders)."
    )
    parser.add_argument(
        "--show",
        default=None,
        help="Optional: Name of a specific TV show folder within the library path to analyze."
    )
    args = parser.parse_args()

    library_path = os.path.abspath(args.path)

    if not os.path.isdir(library_path):
        logging.error(f"Error: Library path is not a valid directory: {library_path}")
        return

    shows_to_analyze = []
    if args.show:
        # Analyze only the specified show
        specific_show_path = os.path.join(library_path, args.show)
        if os.path.isdir(specific_show_path):
            shows_to_analyze.append(specific_show_path)
        else:
            logging.error(f"Error: Specified show folder not found: {specific_show_path}")
            return
    else:
        # Analyze all subdirectories in the library path
        try:
            for item in os.listdir(library_path):
                item_path = os.path.join(library_path, item)
                if os.path.isdir(item_path):
                    # Basic check: avoid hidden folders like .git, .DS_Store etc.
                    if not item.startswith('.'):
                         shows_to_analyze.append(item_path)
        except Exception as e:
            logging.error(f"Error reading library directory '{library_path}': {e}")
            return

    if not shows_to_analyze:
        print(f"No show folders found to analyze in '{library_path}'" + (f" matching '{args.show}'" if args.show else ""))
        return

    print(f"Starting analysis for {len(shows_to_analyze)} show(s) in: {library_path}\n")

    total_shows = 0
    consistent_shows = 0
    complete_shows = 0

    for show_path in sorted(shows_to_analyze):
        try:
            is_consistent, is_complete = analyze_show(show_path)
            total_shows += 1
            if is_consistent:
                consistent_shows += 1
            if is_complete:
                complete_shows += 1
        except Exception as e:
            show_name = os.path.basename(show_path)
            logging.error(f"Failed to analyze show '{show_name}': {e}")

    # --- Final Summary Report ---
    print("\n" + "=" * 40)
    print("          Analysis Summary Report")
    print("=" * 40)
    if total_shows > 0:
        print(f"Total Shows Analyzed: {total_shows}")
        print(f"Shows with Consistent Naming: {consistent_shows} ({consistent_shows/total_shows:.1%})")
        print(f"Shows with Complete Seasons:   {complete_shows} ({complete_shows/total_shows:.1%})")
    else:
        print("No shows were successfully analyzed.")
    print("=" * 40)


if __name__ == "__main__":
    main()
