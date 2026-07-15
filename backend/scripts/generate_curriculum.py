import sys
import os
import argparse
import logging
from typing import List

# Add backend directory to sys.path so we can import app modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db.session import SessionLocal
from app.services.content_generator import (
    generate_speaking_exercises,
    generate_writing_prompts,
    generate_vocabulary_words
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description="TalkFiesta Content Generation Pipeline")
    parser.add_argument("--module", type=str, required=True, choices=["speaking", "writing", "vocab", "all"],
                        help="Module to generate content for.")
    parser.add_argument("--cefr", type=str, required=True, choices=["A1", "A2", "B1", "B2", "C1", "C2"],
                        help="Target CEFR level for the generated content.")
    parser.add_argument("--cycle", type=int, required=True,
                        help="Which curriculum cycle this content belongs to.")
    parser.add_argument("--start-day", type=int, default=1,
                        help="The starting day number for the curriculum.")
    parser.add_argument("--days", type=int, default=1,
                        help="How many days of content to generate (will generate 1 item per day per module).")

    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.module in ["speaking", "all"]:
            generate_speaking_exercises(db, args.cefr, args.cycle, args.start_day, args.days)
            
        if args.module in ["writing", "all"]:
            generate_writing_prompts(db, args.cefr, args.cycle, args.start_day, args.days)
            
        if args.module in ["vocab", "all"]:
            generate_vocabulary_words(db, args.cefr, args.cycle, args.start_day, args.days)
            
        logger.info("Content Generation Pipeline completed successfully.")
        
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    main()
