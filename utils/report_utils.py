# report_utils.py

from typing import Dict, List, Any
import pandas as pd
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def summarize_activities(activities: List[Dict[str, Any]]) -> str:
    """Generate a summary of recent activities."""
    logger = logging.getLogger(__name__)
    
    if not activities:
        return "No activities found for the specified period."
    
    try:
        logger.info(f"Processing {len(activities)} activities")
        for idx, activity in enumerate(activities):
            if 'error' in activity:
                logger.error(f"Activity {idx} has error: {activity['error']}")
                continue
            logger.info(f"Activity {idx} type: {activity.get('activityType')}, name: {activity.get('activityName')}")
        
        # Basic statistics
        total_stats = {
            'total_activities': len(activities),
            'total_distance': sum(a.get('summary', {}).get('distance', 0) for a in activities) / 1000,  # km
            'total_duration': sum(a.get('summary', {}).get('duration', 0) for a in activities) / 3600,  # hours
            'total_calories': sum(a.get('summary', {}).get('calories', 0) for a in activities)
        }
        
        summary = f"""# Recent Activities Summary

## Overall Statistics
- Total Activities: {total_stats['total_activities']}
- Total Distance: {total_stats['total_distance']:.2f} km
- Total Duration: {total_stats['total_duration']:.2f} hours
- Total Calories: {total_stats['total_calories']} kcal

## Individual Activities
"""
        
        for activity in activities:
            summary += _format_activity(activity)
        
        return summary
    except Exception as e:
        logger.error(f"Error in summarize_activities: {str(e)}", exc_info=True)
        raise

def _format_activity(activity: Dict[str, Any]) -> str:
    """Format a single activity for the report."""
    try:
        if 'error' in activity:
            return f"### Error in activity\n- Error: {activity['error'].get('message', 'Unknown error')}\n"
        
        summary = activity.get('summary', {})
        base = f"""### {activity.get('activityName', 'Unknown')} ({activity.get('startTime', 'Unknown')})
- Type: {activity.get('activityType', 'Unknown')}
- Distance: {summary.get('distance', 0) / 1000:.2f} km
- Duration: {summary.get('duration', 0) / 3600:.2f} hours
- Avg HR: {summary.get('averageHR', 'N/A')} bpm
- Max HR: {summary.get('maxHR', 'N/A')} bpm
- Calories: {summary.get('calories', 0)}
"""
        
        if activity.get('activityType') == 'multisport' and 'childActivities' in activity:
            base += "\n#### Child Activities\n"
            for child in activity['childActivities']:
                try:
                    base += _format_child_activity(child)
                except Exception as e:
                    logger.error(f"Error formatting child activity: {str(e)}")
                    base += "Error formatting child activity\n"
        
        if 'hr_zones' in activity:
            try:
                base += "\n#### Heart Rate Zones\n"
                base += _format_hr_zones(activity['hr_zones'])
            except Exception as e:
                logger.error(f"Error formatting HR zones: {str(e)}")
                base += "Error formatting HR zones\n"
        
        return base
    except Exception as e:
        logger.error(f"Error formatting activity: {str(e)}", exc_info=True)
        return "### Error formatting activity\n"

def _format_child_activity(child: Dict[str, Any]) -> str:
    """Format a child activity for multisport activities."""
    try:
        summary = child.get('summary', {})
        return f"""##### {child.get('activityType', 'Unknown').capitalize()}
- Distance: {summary.get('distance', 0) / 1000:.2f} km
- Duration: {summary.get('duration', 0) / 3600:.2f} hours
- Avg HR: {summary.get('averageHR', 'N/A')} bpm
- Max HR: {summary.get('maxHR', 'N/A')} bpm
- Calories: {summary.get('calories', 0)}

"""
    except Exception as e:
        logger.error(f"Error formatting child activity: {str(e)}", exc_info=True)
        return "##### Error formatting child activity\n"

def _format_hr_zones(zones: List[Dict[str, Any]]) -> str:
    """Format heart rate zones data."""
    try:
        if not zones:
            return "No heart rate zone data available\n"
            
        result = "| Zone | Time (minutes) |\n|------|----------------|\n"
        for zone in zones:
            try:
                zone_number = zone.get('zoneNumber', 'N/A')
                minutes = zone.get('secsInZone', 0) / 60
                result += f"| {zone_number} | {minutes:.1f} |\n"
            except Exception as e:
                logger.error(f"Error formatting HR zone: {str(e)}")
                result += f"| Error | N/A |\n"
        return result
    except Exception as e:
        logger.error(f"Error formatting HR zones: {str(e)}", exc_info=True)
        return "Error formatting heart rate zones\n"

def summarize_training_volume(activities: List[Dict[str, Any]]) -> str:
    """Generate weekly training volume summary."""
    try:
        # Extract data safely with defaults
        processed_activities = []
        for activity in activities:
            try:
                summary = activity.get('summary', {})
                processed_activities.append({
                    'startTime': activity.get('startTime'),
                    'duration': summary.get('duration', 0),
                    'distance': summary.get('distance', 0)
                })
            except Exception as e:
                logger.error(f"Error processing activity for volume summary: {str(e)}")
                continue

        if not processed_activities:
            return "No valid activities found for volume summary\n"

        df = pd.DataFrame(processed_activities)
        df['startTime'] = pd.to_datetime(df['startTime'])
        df['week'] = df['startTime'].dt.to_period('W')

        weekly_summary = df.groupby('week').agg({
            'duration': 'sum',
            'distance': 'sum',
            'startTime': 'count'
        }).rename(columns={'startTime': 'activities'})
        
        weekly_summary['duration'] = weekly_summary['duration'] / 3600  # Convert to hours
        weekly_summary['distance'] = weekly_summary['distance'] / 1000  # Convert to km

        result = "## Weekly Training Volume\n\n"
        result += "| Week | Hours | Distance (km) | Activities |\n"
        result += "|------|-------|---------------|------------|\n"
        
        for week, row in weekly_summary.iterrows():
            result += f"| {week} | {row['duration']:.1f} | {row['distance']:.1f} | {row['activities']} |\n"
        
        return result
    except Exception as e:
        logger.error(f"Error generating training volume summary: {str(e)}", exc_info=True)
        return "Error generating training volume summary\n"

def summarize_training_intensity(activities: List[Dict[str, Any]]) -> str:
    """Generate training intensity distribution summary."""
    try:
        intensity_data = []
        
        for activity in activities:
            try:
                if activity.get('activityType') == "multisport" and 'childActivities' in activity:
                    for child in activity['childActivities']:
                        try:
                            intensity_data.extend(_extract_intensity_data(child, activity.get('startTime', 'Unknown')))
                        except Exception as e:
                            logger.error(f"Error processing child activity intensity: {str(e)}")
                else:
                    intensity_data.extend(_extract_intensity_data(activity, activity.get('startTime', 'Unknown')))
            except Exception as e:
                logger.error(f"Error processing activity intensity: {str(e)}")
                continue

        if not intensity_data:
            return "No intensity data available\n"

        df = pd.DataFrame(intensity_data)
        df['week'] = pd.to_datetime(df['date']).dt.to_period('W')
        
        weekly_zones = df.pivot_table(
            index=['week', 'activity_type'],
            columns='zone',
            values='minutes',
            aggfunc='sum',
            fill_value=0
        ).round(1)

        result = "## Training Intensity Distribution\n\n"
        result += "| Week | Activity | Zone 1 | Zone 2 | Zone 3 | Zone 4 | Zone 5 |\n"
        result += "|------|----------|--------|--------|--------|--------|--------|\n"
        
        for (week, activity_type), row in weekly_zones.iterrows():
            result += f"| {week} | {activity_type} | "
            result += " | ".join(f"{row.get(i, 0):.1f}" for i in range(1, 6))
            result += " |\n"
        
        return result
    except Exception as e:
        logger.error(f"Error generating training intensity summary: {str(e)}", exc_info=True)
        return "Error generating training intensity summary\n"

def _extract_intensity_data(activity: Dict[str, Any], date: str) -> List[Dict[str, Any]]:
    """Extract intensity data from an activity."""
    try:
        if 'hr_zones' not in activity:
            logger.warning(f"No HR zones found for activity type: {activity.get('activityType', 'Unknown')}")
            return []
        
        result = []
        for zone in activity['hr_zones']:
            try:
                result.append({
                    'date': date,
                    'activity_type': activity.get('activityType', 'Unknown'),
                    'zone': zone.get('zoneNumber', 0),
                    'minutes': zone.get('secsInZone', 0) / 60
                })
            except Exception as e:
                logger.error(f"Error processing HR zone: {str(e)}")
        return result
    except Exception as e:
        logger.error(f"Error extracting intensity data: {str(e)}", exc_info=True)
        return []

def summarize_recovery(recovery_data: List[Dict[str, Any]]) -> str:
    """Generate recovery metrics summary."""
    try:
        processed_data = []
        for item in recovery_data:
            try:
                sleep_data = item.get('sleep', {})
                duration = sleep_data.get('duration', {})
                quality = sleep_data.get('quality', {})
                stress = item.get('stress', {})
                
                processed_data.append({
                    'date': item.get('date'),
                    'sleep_duration': duration.get('total', None),
                    'deep_sleep': duration.get('deep', None),
                    'rem_sleep': duration.get('rem', None),
                    'sleep_score': quality.get('overall_score', None),
                    'stress_level': stress.get('avg_level', None),
                    'hrv': sleep_data.get('avg_overnight_hrv', None)
                })
            except Exception as e:
                logger.error(f"Error processing recovery data item: {str(e)}")
                continue

        if not processed_data:
            return "No valid recovery data available\n"

        df = pd.DataFrame(processed_data)
        df['date'] = pd.to_datetime(df['date'])
        
        result = "## Recovery Metrics\n\n"
        result += "| Date | Sleep (h) | Deep (h) | REM (h) | Sleep Score | Stress | HRV |\n"
        result += "|------|-----------|----------|---------|-------------|--------|-----|\n"
        
        for _, row in df.sort_values('date', ascending=False).iterrows():
            # Handle NaT in date
            date_str = row['date'].strftime('%Y-%m-%d') if pd.notnull(row['date']) else 'N/A'
            
            # Handle null values in numeric columns
            sleep_duration = f"{row['sleep_duration']:.1f}" if pd.notnull(row['sleep_duration']) else 'N/A'
            deep_sleep = f"{row['deep_sleep']:.1f}" if pd.notnull(row['deep_sleep']) else 'N/A'
            rem_sleep = f"{row['rem_sleep']:.1f}" if pd.notnull(row['rem_sleep']) else 'N/A'
            sleep_score = str(row['sleep_score']) if pd.notnull(row['sleep_score']) else 'N/A'
            stress_level = f"{row['stress_level']:.0f}" if pd.notnull(row['stress_level']) else 'N/A'
            hrv = str(row['hrv']) if pd.notnull(row['hrv']) else 'N/A'
            
            result += (f"| {date_str} | "
                      f"{sleep_duration} | "
                      f"{deep_sleep} | "
                      f"{rem_sleep} | "
                      f"{sleep_score} | "
                      f"{stress_level} | "
                      f"{hrv} |\n")
        
        return result
    except Exception as e:
        logger.error(f"Error generating recovery summary: {str(e)}", exc_info=True)
        return "Error generating recovery summary\n"

def summarize_training_load(load_history: List[Dict[str, Any]]) -> str:
    """Generate training load summary."""
    try:
        processed_data = []
        for item in load_history:
            try:
                processed_data.append({
                    'date': item.get('date'),
                    'acute_load': item.get('acute_load', 0),
                    'chronic_load': item.get('chronic_load', 0),
                    'acwr': item.get('acwr', 0)
                })
            except Exception as e:
                logger.error(f"Error processing training load item: {str(e)}")
                continue

        if not processed_data:
            return "No valid training load data available\n"

        df = pd.DataFrame(processed_data)
        df['date'] = pd.to_datetime(df['date'])
        df['week'] = df['date'].dt.to_period('W')
        
        weekly_load = df.groupby('week').agg({
            'acute_load': 'mean',
            'chronic_load': 'mean',
            'acwr': 'mean'
        }).round(2)
        
        result = "## Training Load\n\n"
        result += "| Week | Acute Load | Chronic Load | ACWR |\n"
        result += "|------|------------|--------------|------|\n"
        
        for week, row in weekly_load.iterrows():
            try:
                result += (f"| {week} | {row['acute_load']:.0f} | "
                          f"{row['chronic_load']:.0f} | {row['acwr']:.2f} |\n")
            except Exception as e:
                logger.error(f"Error formatting training load row: {str(e)}")
                result += f"| {week} | Error | Error | Error |\n"
        
        return result
    except Exception as e:
        logger.error(f"Error generating training load summary: {str(e)}", exc_info=True)
        return "Error generating training load summary\n"

def summarize_vo2max_evolution(vo2max_history: List[Dict[str, Any]]) -> str:
    """Generate VO2max evolution summary."""
    try:
        processed_data = []
        for item in vo2max_history:
            try:
                processed_data.append({
                    'date': item.get('date'),
                    'value': item.get('value', 0)
                })
            except Exception as e:
                logger.error(f"Error processing VO2max item: {str(e)}")
                continue

        if not processed_data:
            return "No valid VO2max data available\n"

        df = pd.DataFrame(processed_data)
        df['date'] = pd.to_datetime(df['date'])
        df['week'] = df['date'].dt.to_period('W')
        weekly_vo2max = df.groupby('week')['value'].mean().round(1)
        
        result = "## VO2max Evolution\n\n"
        result += "| Week | VO2max (ml/kg/min) |\n"
        result += "|------|-------------------|\n"
        
        for week, value in weekly_vo2max.items():
            try:
                result += f"| {week} | {value:.1f} |\n"
            except Exception as e:
                logger.error(f"Error formatting VO2max row: {str(e)}")
                result += f"| {week} | Error |\n"
        
        return result
    except Exception as e:
        logger.error(f"Error generating VO2max evolution summary: {str(e)}", exc_info=True)
        return "Error generating VO2max evolution summary\n"

def summarize_readiness_evolution(readiness_data: List[Dict[str, Any]]) -> str:
    """Generate training readiness evolution summary."""
    try:
        processed_data = []
        for item in readiness_data:
            try:
                processed_data.append({
                    'date': item.get('date'),
                    'score': item.get('score', 'N/A'),
                    'level': item.get('level', 'N/A'),
                    'sleep_score': item.get('sleep_score', 'N/A'),
                    'recovery_time': item.get('recovery_time', 'N/A')
                })
            except Exception as e:
                logger.error(f"Error processing readiness data item: {str(e)}")
                continue

        if not processed_data:
            return "No valid readiness data available\n"

        df = pd.DataFrame(processed_data)
        df['date'] = pd.to_datetime(df['date'])
        
        result = "## Training Readiness\n\n"
        result += "| Date | Score | Level | Sleep Score | Recovery Time |\n"
        result += "|------|-------|-------|-------------|---------------|\n"
        
        for _, row in df.sort_values('date', ascending=False).iterrows():
            try:
                date_str = row['date'].strftime('%Y-%m-%d') if pd.notnull(row['date']) else 'N/A'
                result += (f"| {date_str} | "
                          f"{row['score']} | {row['level']} | "
                          f"{row['sleep_score']} | {row['recovery_time']} |\n")
            except Exception as e:
                logger.error(f"Error formatting readiness row: {str(e)}")
                result += "| Error | Error | Error | Error | Error |\n"
        
        return result
    except Exception as e:
        logger.error(f"Error generating readiness evolution summary: {str(e)}", exc_info=True)
        return "Error generating readiness evolution summary\n"

def summarize_race_predictions_weekly(predictions: List[Dict[str, Any]]) -> str:
    """Generate weekly race predictions summary."""
    try:
        processed_data = []
        for item in predictions:
            try:
                processed_data.append({
                    'date': item.get('date'),
                    '5k': item.get('5k', 'N/A'),
                    '10k': item.get('10k', 'N/A'),
                    'half_marathon': item.get('half_marathon', 'N/A'),
                    'marathon': item.get('marathon', 'N/A')
                })
            except Exception as e:
                logger.error(f"Error processing race prediction item: {str(e)}")
                continue

        if not processed_data:
            return "No valid race prediction data available\n"

        df = pd.DataFrame(processed_data)
        df['date'] = pd.to_datetime(df['date'])
        df['week'] = df['date'].dt.to_period('W')
        
        weekly_predictions = df.groupby('week').last().reset_index()
        
        result = "## Race Predictions\n\n"
        result += "| Week | 5K | 10K | Half Marathon | Marathon |\n"
        result += "|------|-----|-----|---------------|----------|\n"
        
        for _, row in weekly_predictions.iterrows():
            try:
                result += (f"| {row['week']} | {row['5k']} | {row['10k']} | "
                          f"{row['half_marathon']} | {row['marathon']} |\n")
            except Exception as e:
                logger.error(f"Error formatting race prediction row: {str(e)}")
                result += f"| {row['week']} | Error | Error | Error | Error |\n"
        
        return result
    except Exception as e:
        logger.error(f"Error generating race predictions summary: {str(e)}", exc_info=True)
        return "Error generating race predictions summary\n"

def summarize_hill_score_weekly(hill_scores: List[Dict[str, Any]]) -> str:
    """Generate weekly hill score summary."""
    try:
        processed_data = []
        for item in hill_scores:
            try:
                processed_data.append({
                    'date': item.get('date'),
                    'overall_score': item.get('overall_score', 0),
                    'strength_score': item.get('strength_score', 0),
                    'endurance_score': item.get('endurance_score', 0),
                    'classification': item.get('classification', 'N/A')
                })
            except Exception as e:
                logger.error(f"Error processing hill score item: {str(e)}")
                continue

        if not processed_data:
            return "No valid hill score data available\n"

        df = pd.DataFrame(processed_data)
        df['date'] = pd.to_datetime(df['date'])
        df['week'] = df['date'].dt.to_period('W')
        
        weekly_scores = df.groupby('week').agg({
            'overall_score': 'mean',
            'strength_score': 'mean',
            'endurance_score': 'mean',
            'classification': 'last'
        }).round(1)
        
        result = "## Hill Score\n\n"
        result += "| Week | Overall | Strength | Endurance | Classification |\n"
        result += "|------|---------|----------|-----------|----------------|\n"
        
        for week, row in weekly_scores.iterrows():
            try:
                result += (f"| {week} | {row['overall_score']} | "
                          f"{row['strength_score']} | {row['endurance_score']} | "
                          f"{row['classification']} |\n")
            except Exception as e:
                logger.error(f"Error formatting hill score row: {str(e)}")
                result += f"| {week} | Error | Error | Error | Error |\n"
        
        return result
    except Exception as e:
        logger.error(f"Error generating hill score summary: {str(e)}", exc_info=True)
        return "Error generating hill score summary\n"

def summarize_endurance_score_weekly(endurance_scores: List[Dict[str, Any]]) -> str:
    """Generate weekly endurance score summary."""
    try:
        processed_data = []
        for item in endurance_scores:
            try:
                processed_data.append({
                    'date': item.get('date'),
                    'overall_score': item.get('overall_score', 0),
                    'classification': item.get('classification', 'N/A')
                })
            except Exception as e:
                logger.error(f"Error processing endurance score item: {str(e)}")
                continue

        if not processed_data:
            return "No valid endurance score data available\n"

        df = pd.DataFrame(processed_data)
        df['date'] = pd.to_datetime(df['date'])
        df['week'] = df['date'].dt.to_period('W')
        
        weekly_scores = df.groupby('week').agg({
            'overall_score': 'mean',
            'classification': 'last'
        })
        
        result = "## Endurance Score\n\n"
        result += "| Week | Score | Classification |\n"
        result += "|------|-------|----------------|\n"
        
        for week, row in weekly_scores.iterrows():
            try:
                result += f"| {week} | {row['overall_score']:.0f} | {row['classification']} |\n"
            except Exception as e:
                logger.error(f"Error formatting endurance score row: {str(e)}")
                result += f"| {week} | Error | Error |\n"
        
        return result
    except Exception as e:
        logger.error(f"Error generating endurance score summary: {str(e)}", exc_info=True)
        return "Error generating endurance score summary\n"
