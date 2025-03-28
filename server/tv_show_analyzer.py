#!/usr/bin/env python3

import os
import re
import argparse
from collections import defaultdict
import logging
import datetime
from typing import Tuple, Dict, List, Optional, Set

# Common video file extensions
VIDEO_EXTENSIONS = {'.mkv', '.mp4', '.avi', '.mov', '.wmv', '.flv'}

# Global logger instance (configured in main)
logger = logging.getLogger(__name__)

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

def analyze_season_organization(show_path: str, args: argparse.Namespace) -> bool:
    """
    Identify video files needing season organization and optionally perform it interactively.
    Returns True if potential organization is needed, False otherwise.
    Logs details about needed organization.
    """
    show_name = os.path.basename(show_path)
    if args.verbose:
        print(f"\n--- Checking Season Organization ---")
    logger.info(f"Checking season organization for: {show_name}")
    files_to_organize: Dict[int, List[str]] = defaultdict(list)
    organization_needed = False

    try:
        items_in_root = [item for item in os.listdir(show_path)
                         if os.path.isfile(os.path.join(show_path, item))]

        for item in items_in_root:
            if is_video_file(item):
                season, _ = parse_season_episode(item)
                if season is None:
                    # Try parsing just the season if S##E## fails
                    season = parse_season_only(item)

                if season is not None:
                    files_to_organize[season].append(item)
                    organization_needed = True
                else:
                    # Log files that look like videos but have no season info
                    logger.debug(f"Could not determine season for loose file: {item} in {show_name}")

        if not organization_needed:
            if args.verbose:
                print("  No loose video files needing season organization found.")
            logger.info(f"No season organization needed for: {show_name}")
            return False

        # Log and potentially print details
        log_summary = [f"Potential Season Organization Needed for: {show_name}"]
        if args.verbose or args.interactive: # Show details if verbose or interactive
             print("  Potential Season Organization Needed:")
        for season_num, files in sorted(files_to_organize.items()):
            target_folder_name = f"Season {season_num}"
            file_count = len(files)
            # Print summary instead of individual files
            if args.verbose or args.interactive:
                print(f"    Would create folder: '{target_folder_name}' (for {file_count} files)")
            log_summary.append(f"  Season {season_num}: {file_count} files")
        logger.warning("\n".join(log_summary)) # Log the summary list

        # Interactive Prompt
        if args.interactive:
            confirm = input(f"Perform organization for '{show_name}'? [y/N]: ").strip().lower()
            if confirm == 'y':
                print(f"  Attempting organization for '{show_name}'...")
                logger.info(f"User confirmed organization for: {show_name}")
                perform_organization(show_path, files_to_organize)
            else:
                print(f"  Skipping organization for '{show_name}'.")
                logger.info(f"User skipped organization for: {show_name}")

        return True # Organization was needed, even if not performed

    except FileNotFoundError:
        logger.error(f"Show directory not found during organization check: {show_path}")
    except Exception as e:
        logger.error(f"Error checking season organization for '{show_path}': {e}")
    return False # Assume no organization needed on error


def perform_organization(show_path: str, files_to_organize: Dict[int, List[str]]):
    """Creates folders and moves files as specified."""
    for season_num, files in sorted(files_to_organize.items()):
        target_folder_name = f"Season {season_num}"
        target_folder_path = os.path.join(show_path, target_folder_name)

        # Create folder
        try:
            os.makedirs(target_folder_path, exist_ok=True)
            print(f"    Created/Ensured folder: '{target_folder_name}'")
            logger.info(f"Created/Ensured folder: '{target_folder_path}'")
        except Exception as e:
            print(f"    ERROR creating folder '{target_folder_name}': {e}")
            logger.error(f"Failed to create folder '{target_folder_path}': {e}")
            continue # Skip moving files if folder creation failed

        # Move files
        for file in sorted(files):
            source_path = os.path.join(show_path, file)
            destination_path = os.path.join(target_folder_path, file)
            try:
                os.rename(source_path, destination_path)
                print(f"      Moved: '{file}' -> '{target_folder_name}/'")
                logger.info(f"Moved '{source_path}' to '{destination_path}'")
            except Exception as e:
                print(f"      ERROR moving file '{file}': {e}")
                logger.error(f"Failed to move '{source_path}' to '{destination_path}': {e}")


def analyze_existing_seasons(show_path: str, args: argparse.Namespace) -> Tuple[Dict[int, List[str]], Dict[int, str]]:
    """
    Analyze existing 'Season X' folders for inconsistency and holes.
    Returns two dictionaries:
    - season_inconsistencies: {season_num: list_of_tags}
    - season_holes: {season_num: hole_description_string}
    Logs details of issues found based on log level.
    """
    show_name = os.path.basename(show_path)
    if args.verbose:
        print(f"\n--- Analyzing Existing Season Folders ---")
    logger.info(f"Analyzing existing seasons for: {show_name}")
    season_folders_found = False
    season_inconsistencies: Dict[int, List[str]] = {}
    season_holes: Dict[int, str] = {}

    try:
        items = sorted(os.listdir(show_path)) # Sort for consistent order
        for item in items:
            item_path = os.path.join(show_path, item)
            if os.path.isdir(item_path):
                match = SEASON_FOLDER_REGEX.match(item)
                if match:
                    season_folders_found = True
                    season_num = int(match.group(1))
                    if args.verbose:
                        print(f"\n  Analyzing Folder: '{item}' (Season {season_num})")
                    logger.info(f"Analyzing folder: {item_path}")
                    inconsistent_tags, hole_description = analyze_single_season_folder(item_path, season_num, args)

                    if inconsistent_tags is not None:
                        season_inconsistencies[season_num] = inconsistent_tags
                    if hole_description is not None:
                        season_holes[season_num] = hole_description

        if not season_folders_found:
            if args.verbose:
                print("  No 'Season X' folders found to analyze.")
            logger.info(f"No 'Season X' folders found in {show_name}")
            # Return empty dicts if no seasons found
            return {}, {}

    except FileNotFoundError:
        logger.error(f"Show directory not found during season analysis: {show_path}")
        return {}, {"error": f"Show directory not found: {show_path}"} # Indicate error
    except Exception as e:
        logger.error(f"Error analyzing existing seasons for '{show_path}': {e}")
        return {}, {"error": f"Error analyzing seasons: {e}"} # Indicate error

    # Determine overall status for logging summary
    all_consistent = not bool(season_inconsistencies)
    all_complete = not bool(season_holes)
    logger.info(f"Finished analyzing existing seasons for: {show_name}. Consistent: {all_consistent}, Complete: {all_complete}")

    return season_inconsistencies, season_holes


def analyze_single_season_folder(season_path: str, season_num: int, args: argparse.Namespace) -> Tuple[Optional[List[str]], Optional[str]]:
    """
    Analyze a specific season folder for naming inconsistency and episode holes.
    Returns a tuple: (inconsistent_tags, hole_description).
    - inconsistent_tags: List of tags if inconsistent, None otherwise.
    - hole_description: String describing holes if incomplete, None otherwise.
    Logs details of issues based on log level.
    """
    folder_name = os.path.basename(season_path)
    episodes: Dict[int, str] = {}
    release_tags: Set[str] = set()
    filenames: List[str] = []
    inconsistent_tags: Optional[List[str]] = None
    hole_description: Optional[str] = None

    try:
        for item in os.listdir(season_path):
            item_path = os.path.join(season_path, item)
            if os.path.isfile(item_path) and is_video_file(item):
                s, e = parse_season_episode(item)
                filenames.append(item)
                if s is not None and e is not None:
                    if s != season_num:
                        # Log season mismatch only if verbose or specifically debugging
                        logger.warning(f"Mismatch: File '{item}' in {folder_name} has S{s:02d}E{e:02d}.")
                        continue # Skip if season number in file doesn't match folder

                    if e in episodes:
                        logger.warning(f"Duplicate episode number {e} found in {folder_name}: '{item}' and '{episodes[e]}'")
                    episodes[e] = item
                    tag = get_release_tag(item, s, e)
                    if tag: # Avoid adding empty tags if extraction fails
                        release_tags.add(tag)
                else:
                     logger.debug(f"Could not parse S##E## from: '{item}' in {folder_name}")

        if not episodes:
            if args.verbose:
                print("    No valid episode files found in this season folder.")
            logger.info(f"No valid episode files found in {folder_name}")
            # Considered complete if empty, but inconsistent might be debatable (let's say consistent)
            return True, True

        # 1. Naming Inconsistency Check
        if len(release_tags) > 1:
            msg = f"Naming Inconsistency: Found {len(release_tags)} potential release patterns in {folder_name}."
            if args.verbose: print(f"    ❌ {msg}")
            logger.warning(msg)
            # Log only the distinct tags found, not every filename
            sorted_tags = sorted(list(release_tags))
            logger.warning(f"  Tags found: {', '.join(sorted_tags)}")
            inconsistent_tags = sorted_tags
        else:
            if args.verbose: print(f"    ✅ Naming Consistency: Appears consistent.")
            logger.info(f"Naming appears consistent in {folder_name}")

        # 2. Season Hole Check
        min_ep = min(episodes.keys())
        max_ep = max(episodes.keys())

        # 2. Season Hole Check
        min_ep = min(episodes.keys())
        max_ep = max(episodes.keys())

        if len(episodes) == 1:
             if args.verbose: print(f"    ✅ Season Completeness: Only one episode (E{max_ep}) found.")
             logger.info(f"Only one episode (E{max_ep}) found in {folder_name}")
             # hole_description remains None
        else:
            expected_episodes = set(range(1, max_ep + 1)) # Assume seasons start at 1
            found_episodes = set(episodes.keys())
            missing_episodes = sorted(list(expected_episodes - found_episodes))

            hole_messages = []
            log_hole_messages = []
            if min_ep > 1:
                 hole_messages.append(f"Starts at episode {min_ep}, not 1")
                 log_hole_messages.append(f"Starts at episode {min_ep}, not 1")

            if missing_episodes:
                hole_messages.append(f"Missing episode(s): {missing_episodes}")
                log_hole_messages.append(f"Missing episode(s): {missing_episodes}")

            if not hole_messages:
                 if args.verbose: print(f"    ✅ Season Completeness: No episodes missing between 1-{max_ep}.")
                 logger.info(f"No episodes missing between 1-{max_ep} in {folder_name}")
                 # hole_description remains None
            else:
                 msg = f"Season Hole: {'; '.join(hole_messages)}"
                 log_msg = f"Season Hole in {folder_name}: {'; '.join(log_hole_messages)}"
                 if args.verbose: print(f"    ❌ {msg}")
                 logger.warning(log_msg)
                 hole_description = log_msg # Store the description


    except FileNotFoundError:
        logger.error(f"Season directory not found during analysis: {season_path}")
        return None, "Error: Directory not found" # Indicate error
    except Exception as e:
        logger.error(f"Error analyzing season folder '{season_path}': {e}")
        return None, f"Error: {e}" # Indicate error

    return inconsistent_tags, hole_description


# --- Main Execution ---

# Define a structure to hold detailed results for a show
class ShowAnalysisResult:
    def __init__(self, show_name: str):
        self.show_name = show_name
        self.needs_org: bool = False
        self.season_inconsistencies: Dict[int, List[str]] = {}
        self.season_holes: Dict[int, str] = {}
        self.overall_consistent: bool = True
        self.overall_complete: bool = True

def analyze_show(show_path: str, args: argparse.Namespace) -> ShowAnalysisResult:
    """Runs all analyses for a single show folder and returns detailed results."""
    show_name = os.path.basename(show_path)
    result = ShowAnalysisResult(show_name)

    if args.verbose:
        print(f"\n{'='*10} Analyzing Show: {show_name} {'='*10}")
    logger.info(f"Starting analysis for show: {show_name} ({show_path})")

    result.needs_org = analyze_season_organization(show_path, args)
    result.season_inconsistencies, result.season_holes = analyze_existing_seasons(show_path, args)

    # Determine overall status based on collected details
    result.overall_consistent = not bool(result.season_inconsistencies)
    result.overall_complete = not bool(result.season_holes)

    if args.verbose:
        print(f"\n--- Show Summary: {show_name} ---")
        print(f"  Needs Season Organization: {'Yes' if result.needs_org else 'No'}")
        print(f"  Overall Naming Consistency: {'✅ Consistent' if result.overall_consistent else '❌ Inconsistent'}")
        print(f"  Overall Season Completeness: {'✅ Complete' if result.overall_complete else '❌ Incomplete'}")

    logger.info(f"Finished analysis for show: {show_name}. Needs Org: {result.needs_org}, Consistent: {result.overall_consistent}, Complete: {result.overall_complete}")
    return result


def setup_logging(args: argparse.Namespace):
    """Configures console and file logging."""
    log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    logger.setLevel(logging.DEBUG) # Capture debug+ for potential processing

    # Clear previous handlers if any (useful for re-runs in interactive sessions)
    # logger.handlers.clear() # Re-evaluating if this is needed/safe

    # File Handler (conditional)
    file_handler = None
    if args.log_level < 2:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"tv_analysis_{timestamp}.log"
        try:
            file_handler = logging.FileHandler(log_filename)
            file_handler.setFormatter(log_formatter)
            # Set level based on log_level for file
            if args.log_level == 0:
                file_handler.setLevel(logging.INFO) # Default: info, warning, error
            elif args.log_level == 1:
                # Level 1: Only log critical+ initially, will log summary later
                file_handler.setLevel(logging.CRITICAL + 1)
            logger.addHandler(file_handler)
            print(f"Logging to: {log_filename} (Level: {args.log_level})")
        except Exception as e:
            print(f"Error setting up log file '{log_filename}': {e}")
            file_handler = None # Ensure it's None if setup fails
    else:
        print("File logging disabled.")

    # Console Handler (level depends on verbose flag)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s')) # Simpler format for console
    if args.verbose:
        console_handler.setLevel(logging.INFO)
    else:
        console_handler.setLevel(logging.WARNING) # Only show warnings and errors by default
    logger.addHandler(console_handler)


def main():
    parser = argparse.ArgumentParser(
        description="Analyze TV show library for organization, naming consistency, and missing episodes.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "--path",
        required=True,
        help="Path to the TV show library directory (containing show folders)."
    )
    parser.add_argument(
        "--show",
        default=None,
        help="Optional: Name of a specific TV show folder within the library path to analyze."
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable detailed output during analysis."
    )
    parser.add_argument(
        "-i", "--interactive",
        action="store_true",
        help="Enable interactive mode to confirm season organization actions."
    )
    parser.add_argument(
        "--log-level",
        type=int,
        choices=[0, 1, 2],
        default=0,
        help="Set log file verbosity: 0=Default (summarized issues), 1=Issues List Only, 2=Disabled."
    )
    args = parser.parse_args()

    # Setup logging based on args
    setup_logging(args)

    library_path = os.path.abspath(args.path)
    logger.info(f"Script started with args: path={library_path}, show={args.show}, verbose={args.verbose}, interactive={args.interactive}")

    if not os.path.isdir(library_path):
        logger.error(f"Error: Library path is not a valid directory: {library_path}")
        return

    shows_to_analyze = []
    if args.show:
        # Analyze only the specified show
        specific_show_path = os.path.join(library_path, args.show)
        if os.path.isdir(specific_show_path):
            shows_to_analyze.append(specific_show_path)
            logger.info(f"Targeting specific show: {specific_show_path}")
        else:
            logger.error(f"Error: Specified show folder not found: {specific_show_path}")
            return
    else:
        # Analyze all subdirectories in the library path
        logger.info(f"Scanning library path for show folders: {library_path}")
        try:
            for item in os.listdir(library_path):
                item_path = os.path.join(library_path, item)
                if os.path.isdir(item_path):
                    # Basic check: avoid hidden folders like .git, .DS_Store etc.
                    if not item.startswith('.'):
                         shows_to_analyze.append(item_path)
            logger.info(f"Found {len(shows_to_analyze)} potential show folders.")
        except Exception as e:
            logger.error(f"Error reading library directory '{library_path}': {e}")
            return

    if not shows_to_analyze:
        msg = f"No show folders found to analyze in '{library_path}'" + (f" matching '{args.show}'" if args.show else "")
        logger.warning(msg)
        print(msg)
        return

    print(f"\nStarting analysis for {len(shows_to_analyze)} show(s)...")

    total_shows = 0
    all_results: List[ShowAnalysisResult] = [] # Store detailed results

    for show_path in sorted(shows_to_analyze):
        try:
            # Pass args down to analysis functions
            show_result = analyze_show(show_path, args)
            all_results.append(show_result)
            total_shows += 1
            # Overall consistency/completeness tracked within ShowAnalysisResult
        except Exception as e:
            show_name = os.path.basename(show_path)
            logger.exception(f"Unexpected error analyzing show '{show_name}': {e}") # Use logger.exception to include traceback

    # --- Log Level 1 Output ---
    if args.log_level == 1 and total_shows > 0:
        issues_log = []
        for result in all_results:
            if not result.overall_consistent:
                for season_num, tags in sorted(result.season_inconsistencies.items()):
                     issues_log.append(f"Inconsistent Naming: {result.show_name} Season {season_num} (Tags: {tags})")
            if not result.overall_complete:
                 for season_num, desc in sorted(result.season_holes.items()):
                      issues_log.append(f"Incomplete Season: {result.show_name} Season {season_num} ({desc})")

        if issues_log:
            # Find the file handler to write the summary
            file_handler = next((h for h in logger.handlers if isinstance(h, logging.FileHandler)), None)
            if file_handler:
                original_level = file_handler.level
                try:
                    file_handler.setLevel(logging.INFO) # Ensure INFO level for this summary
                    logger.info("--- Issues Summary (Log Level 1) ---")
                    for issue in sorted(issues_log): # Sort the final list
                        logger.info(issue)
                    logger.info("--- End Issues Summary ---")
                finally:
                    file_handler.setLevel(original_level) # Reset level if needed
            else:
                 # Should not happen if log_level < 2, but handle defensively
                 logger.error("Log Level 1 specified but no file handler found to write summary.")
        else:
             logger.info("--- Issues Summary (Log Level 1): No inconsistencies or incomplete seasons found. ---")


    # --- Final Summary Report (Console) ---
    # Calculate overall stats from collected results
    consistent_shows = sum(1 for r in all_results if r.overall_consistent)
    complete_shows = sum(1 for r in all_results if r.overall_complete)

    summary_lines = [
        "\n" + "=" * 40,
        "          Analysis Summary Report",
        "=" * 40
    ]
    if total_shows > 0:
        summary_lines.append(f"Total Shows Analyzed: {total_shows}")
        summary_lines.append(f"Shows with Consistent Naming: {consistent_shows} ({consistent_shows/total_shows:.1%})")
        summary_lines.append(f"Shows with Complete Seasons:   {complete_shows} ({complete_shows/total_shows:.1%})")
    else:
        summary_lines.append("No shows were successfully analyzed.")
    summary_lines.append("=" * 40)

    summary_report = "\n".join(summary_lines)
    print(summary_report)
    logger.info("Analysis Complete.\n" + summary_report)


if __name__ == "__main__":
    # Clear root logger handlers to avoid duplicate messages if script is re-run
    # logging.getLogger().handlers.clear() # This might be too aggressive? Let's remove for now.
    main()
