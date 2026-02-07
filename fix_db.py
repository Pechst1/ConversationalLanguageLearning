
from sqlalchemy import text
from app.db.session import SessionLocal

def fix_db():
    db = SessionLocal()
    try:
        # We need to drop these tables because their schema (PK type) changed incompatible way
        # and we want to re-seed them cleanly.
        tables = ["story_progress", "scenes", "chapters", "npcs", "stories", "story_chapters", "user_story_progress"]
        
        for table in tables:
            try:
                print(f"Dropping table {table}...")
                db.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
            except Exception as e:
                print(f"Error dropping {table}: {e}")
                
        db.commit()
        print("Tables dropped.")
    finally:
        db.close()

if __name__ == "__main__":
    fix_db()
