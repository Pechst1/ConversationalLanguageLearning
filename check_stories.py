
import asyncio
import os
import sys

# Add current directory to path
sys.path.append(os.getcwd())

from app.db.session import SessionLocal
from app.db.models.story import Story
from sqlalchemy import select

async def main():
    db = SessionLocal()
    try:
        print("Checking stories in DB...")
        stmt = select(Story)
        stories = db.execute(stmt).scalars().all()
        
        print(f"Total stories found: {len(stories)}")
        for s in stories:
            print(f"- Story: {s.title} (ID: {s.id})")
            print(f"  Active: {s.is_active}")
            print(f"  Source: {s.source_book}")
            print(f"  Levels: {s.target_levels}")
            
            # Check visibility logic match
            if s.is_active:
                print("  [VISIBLE] Should be visible in API")
            else:
                print("  [HIDDEN] is_active is False")
                
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
