#!/usr/bin/env python3

import json
import logging
import sys
from argparse import ArgumentParser

from core.security import SecureReportManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def read_user_profile(user_id: str) -> None:
    try:
        # Get stored data
        data_manager = SecureReportManager(user_id)
        stored_data = data_manager.get_report()
        
        if not stored_data:
            logger.error("No stored data found. Please run /generate first!")
            return
            
        # Parse the stored data
        data, timestamp = stored_data
        parsed_data = json.loads(data)
        
        if 'raw_data' not in parsed_data:
            logger.error("No raw Garmin data found in stored data")
            return
            
        # Extract user profile
        user_profile = parsed_data['raw_data'].get('user_profile', {})
        
        if not user_profile:
            logger.error("No user profile found in Garmin data")
            return
            
        # Display user profile information
        logger.info("\n=== User Profile Information ===")
        logger.info(f"Gender: {user_profile.get('gender', 'Not set')}")
        logger.info(f"Height: {user_profile.get('height', 'Not set')} cm")
        logger.info(f"Weight: {user_profile.get('weight', 'Not set')} kg")
        logger.info(f"Birth Date: {user_profile.get('birth_date', 'Not set')}")
        logger.info(f"Activity Level: {user_profile.get('activity_level', 'Not set')}")
        logger.info("\n=== Performance Metrics ===")
        logger.info(f"Running VO2 Max: {user_profile.get('vo2max_running', 'Not set')}")
        logger.info(f"Cycling VO2 Max: {user_profile.get('vo2max_cycling', 'Not set')}")
        logger.info(f"Lactate Threshold Speed: {user_profile.get('lactate_threshold_speed', 'Not set')} m/s")
        logger.info(f"Lactate Threshold HR: {user_profile.get('lactate_threshold_heart_rate', 'Not set')} bpm")
        logger.info(f"FTP Auto Detected: {user_profile.get('ftp_auto_detected', 'Not set')}")
        logger.info("\n=== Training Schedule ===")
        logger.info(f"Available Training Days: {', '.join(user_profile.get('available_training_days', ['Not set']))}")
        logger.info(f"Preferred Long Training Days: {', '.join(user_profile.get('preferred_long_training_days', ['Not set']))}")
        logger.info(f"Sleep Time: {user_profile.get('sleep_time', 'Not set')}")
        logger.info(f"Wake Time: {user_profile.get('wake_time', 'Not set')}")
        
    except Exception as e:
        logger.error(f"Error reading user profile: {str(e)}")
        sys.exit(1)

def main():
    parser = ArgumentParser(description="Read user profile from stored Garmin data")
    parser.add_argument("user_id", help="Telegram user ID")
    args = parser.parse_args()
    
    read_user_profile(args.user_id)

if __name__ == "__main__":
    main()
