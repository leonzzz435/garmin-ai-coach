#!/usr/bin/env python3

import asyncio
import argparse
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List
from dataclasses import asdict
import yaml
import json
import getpass
import sys
import os

sys.path.append(str(Path(__file__).parent.parent))

from services.ai.langgraph.workflows.planning_workflow import run_complete_analysis_and_planning
from services.garmin import ExtractionConfig, TriathlonCoachDataExtractor
from core.security import SecureCredentialManager

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class ConfigParser:
    
    def __init__(self, config_path: Path):
        self.config_path = config_path
        self.config = self._load_config()
        
    def _load_config(self) -> Dict[str, Any]:
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
            
        content = self.config_path.read_text()
        
        if self.config_path.suffix in ['.yaml', '.yml']:
            return yaml.safe_load(content)
        elif self.config_path.suffix == '.json':
            return json.loads(content)
        else:
            raise ValueError(f"Unsupported config format: {self.config_path.suffix}")
    
    def get_athlete_info(self) -> tuple[str, str]:
        athlete = self.config.get('athlete', {})
        name = athlete.get('name', 'Athlete')
        email = athlete.get('email')
        
        if not email:
            raise ValueError("Athlete email is required in config file")
            
        return name, email
    
    def get_contexts(self) -> tuple[str, str]:
        context = self.config.get('context', {})
        analysis_context = context.get('analysis', '').strip()
        planning_context = context.get('planning', '').strip()
        return analysis_context, planning_context
    
    def get_extraction_config(self) -> Dict[str, Any]:
        extraction = self.config.get('extraction', {})
        return {
            'activities_days': extraction.get('activities_days', 7),
            'metrics_days': extraction.get('metrics_days', 14),
            'ai_mode': extraction.get('ai_mode', 'development')
        }
    
    def get_competitions(self) -> List[Dict[str, Any]]:
        competitions = self.config.get('competitions', [])
        processed_competitions = []
        
        for comp in competitions:
            date_str = comp.get('date', '')
            if date_str:
                try:
                    date_obj = datetime.fromisoformat(date_str).date()
                    processed_comp = {
                        'name': comp.get('name', ''),
                        'date': date_obj.isoformat(),
                        'race_type': comp.get('race_type', ''),
                        'priority': comp.get('priority', 'B'),
                        'target_time': comp.get('target_time', '')
                    }
                    processed_competitions.append(processed_comp)
                except ValueError:
                    logger.warning(f"Invalid date format for competition: {comp.get('name', 'Unknown')}")
        
        return processed_competitions
    
    def get_output_directory(self) -> Path:
        output = self.config.get('output', {})
        output_dir = output.get('directory', './data')
        return Path(output_dir)
    
    def get_password(self) -> str:
        credentials = self.config.get('credentials', {})
        password = credentials.get('password', '')
        
        if not password:
            password = getpass.getpass("Enter Garmin Connect password: ")
        
        return password


async def run_analysis_from_config(config_path: Path) -> None:
    
    config_parser = ConfigParser(config_path)
    athlete_name, email = config_parser.get_athlete_info()
    analysis_context, planning_context = config_parser.get_contexts()
    extraction_settings = config_parser.get_extraction_config()
    competitions = config_parser.get_competitions()
    output_dir = config_parser.get_output_directory()
    
    logger.info(f"Starting analysis for {athlete_name}")
    logger.info(f"Output directory: {output_dir}")
    
    password = config_parser.get_password()
    
    # Set AI mode environment variable
    ai_mode = extraction_settings.get('ai_mode', 'development')
    os.environ['AI_MODE'] = ai_mode
    logger.info(f"AI Mode: {ai_mode}")
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        logger.info("Extracting Garmin Connect data...")
        extractor = TriathlonCoachDataExtractor(email, password)
        
        extraction_config = ExtractionConfig(
            activities_range=extraction_settings['activities_days'],
            metrics_range=extraction_settings['metrics_days'],
            include_detailed_activities=True,
            include_metrics=True
        )
        
        garmin_data = extractor.extract_data(extraction_config)
        logger.info("Data extraction completed")
        
        current_date = {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'day_name': datetime.now().strftime('%A')
        }
        
        week_dates = []
        for i in range(14):
            date = datetime.now() + timedelta(days=i)
            week_dates.append({
                'date': date.strftime('%Y-%m-%d'),
                'day_name': date.strftime('%A')
            })
        
        logger.info("Running AI analysis and planning...")
        result = await run_complete_analysis_and_planning(
            user_id="cli_user",
            athlete_name=athlete_name,
            garmin_data=asdict(garmin_data),
            analysis_context=analysis_context,
            planning_context=planning_context,
            competitions=competitions,
            current_date=current_date,
            week_dates=week_dates
        )
        
        logger.info("Saving results...")
        
        files_generated: list[str] = []
        
        analysis_html = result.get('analysis_html')
        if analysis_html:
            (output_dir / 'analysis.html').write_text(analysis_html)
            files_generated.append('analysis.html')
            logger.info(f"Saved: {output_dir}/analysis.html")
        
        planning_html = result.get('planning_html')
        if planning_html:
            (output_dir / 'planning.html').write_text(planning_html)
            files_generated.append('planning.html')
            logger.info(f"Saved: {output_dir}/planning.html")
        
        cost_total = 0.0
        total_tokens = 0
        if isinstance(result.get('cost_summary'), dict):
            cost_total = float(result['cost_summary'].get('total_cost_usd', 0.0) or 0.0)
            total_tokens = int(result['cost_summary'].get('total_tokens', 0) or 0)
        elif isinstance(result.get('execution_metadata'), dict):
            cost_total = float(result['execution_metadata'].get('total_cost_usd', 0.0) or 0.0)
            total_tokens = int(result['execution_metadata'].get('total_tokens', 0) or 0)
        else:
            cost_total = sum(cost.get('total_cost', 0) for cost in result.get('costs', []))
        
        summary = {
            'athlete': athlete_name,
            'analysis_date': datetime.now().isoformat(),
            'competitions': competitions,
            'total_cost_usd': cost_total,
            'total_tokens': total_tokens,
            'execution_id': result.get('execution_id', ''),
            'trace_id': (result.get('execution_metadata') or {}).get('trace_id', ''),
            'root_run_id': (result.get('execution_metadata') or {}).get('root_run_id', ''),
            'files_generated': files_generated
        }
        
        (output_dir / 'summary.json').write_text(json.dumps(summary, indent=2))
        
        logger.info("✅ Analysis completed successfully!")
        logger.info(f"📁 Results saved to: {output_dir}")
        logger.info(f"💰 Total cost: ${cost_total:.2f} ({total_tokens} tokens)")
        
    except Exception as e:
        logger.error(f"❌ Analysis failed: {e}")
        raise


def create_config_template(output_path: Path) -> None:
    template_path = Path(__file__).parent / 'coach_config_template.yaml'
    
    if template_path.exists():
        output_path.write_text(template_path.read_text())
        logger.info(f"✅ Config template created: {output_path}")
        logger.info("Edit this file with your settings and run analysis with --config")
    else:
        logger.error("❌ Template file not found")


def main():
    parser = argparse.ArgumentParser(
        description="Tele Garmin CLI - AI Triathlon Coach",
        epilog="Example: python tele_garmin_cli.py --config my_config.yaml"
    )
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        '--config', 
        type=Path,
        help='Path to configuration file (YAML or JSON)'
    )
    group.add_argument(
        '--init-config',
        type=Path,
        help='Create a configuration template file'
    )
    
    parser.add_argument(
        '--output-dir',
        type=Path,
        help='Override output directory from config'
    )
    
    args = parser.parse_args()
    
    if args.init_config:
        create_config_template(args.init_config)
        return
    
    if args.config:
        try:
            asyncio.run(run_analysis_from_config(args.config))
        except KeyboardInterrupt:
            logger.info("❌ Analysis cancelled by user")
        except Exception as e:
            logger.error(f"❌ Analysis failed: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()