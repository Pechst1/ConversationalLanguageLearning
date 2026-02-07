"""Import grammar concepts from the Excel tracker."""
import re
import openpyxl
from app.db.session import SessionLocal
from app.services.grammar import GrammarService
from app.db.models.grammar import GrammarConcept
from sqlalchemy import delete


def extract_category(name: str) -> str | None:
    """Extract category from concept name if present."""
    categories = {
        'Artikel': 'Artikel',
        'Nomen': 'Nomen',
        'Adjektiv': 'Adjektive',
        'Adverb': 'Adverbien',
        'Verb': 'Verben',
        'Pronomen': 'Pronomen',
        'Präposition': 'Präpositionen',
        'Konjunktion': 'Konjunktionen',
        'Passé': 'Verben',
        'Imparfait': 'Verben',
        'Futur': 'Verben',
        'Conditionnel': 'Verben',
        'Subjonctif': 'Verben',
        'Partizip': 'Verben',
        'Infinitiv': 'Verben',
        'Passiv': 'Verben',
        'Imperativ': 'Verben',
        'Gérondif': 'Verben',
        'Si-Sätz': 'Satzbau',
        'Relativ': 'Satzbau',
        'Negation': 'Satzbau',
        'Frage': 'Satzbau',
        'Indirekt': 'Satzbau',
        'Vergleich': 'Satzbau',
        'Zahlen': 'Zahlen',
        'Datum': 'Zahlen',
        'Uhrzeit': 'Zahlen',
        'Konnekt': 'Konnektoren',
        'Opposition': 'Konnektoren',
        'Ursache': 'Konnektoren',
        'Folge': 'Konnektoren',
    }
    
    for keyword, category in categories.items():
        if keyword.lower() in name.lower():
            return category
    return 'Allgemein'


def parse_excel():
    """Parse the Excel file and extract all concepts."""
    # Use data_only=True to get computed values instead of formulas
    wb = openpyxl.load_workbook('Französisch_Grammatik_Tracker-2.xlsx', data_only=True)
    ws = wb['Grammatik Tracker']
    
    concepts = []
    seen_names = set()
    
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row[0] or not row[1]:  # Skip empty rows
            continue
        
        concept_id = row[0]
        raw_name = str(row[1])
        level = row[2] if len(row) > 2 and row[2] else None
        
        # Clean the name (remove level prefix if duplicated in name)
        name = raw_name
        if ' – ' in raw_name and raw_name.split(' – ')[0] in ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']:
            parts = raw_name.split(' – ', 1)
            name = parts[1] if len(parts) > 1 else raw_name
            if not level:
                level = parts[0]
        
        # Skip duplicates
        if name in seen_names:
            continue
        seen_names.add(name)
        
        # Extract category from name
        category = extract_category(name)
        
        concepts.append({
            'name': name,
            'level': level or 'B1',
            'category': category,
            'description': None,
            'difficulty_order': int(concept_id) if isinstance(concept_id, (int, float)) else 0,
        })
    
    return concepts


def seed_grammar(clear_existing: bool = False):
    """Import all concepts from Excel."""
    print("Parsing Excel file (with data_only=True)...")
    concepts = parse_excel()
    print(f"Found {len(concepts)} unique concepts")
    
    # Group by level for summary
    by_level = {}
    for c in concepts:
        level = c['level']
        by_level[level] = by_level.get(level, 0) + 1
    
    print("\nBy level:")
    for level in sorted(by_level.keys()):
        print(f"  {level}: {by_level[level]}")
    
    # Insert into database
    db = SessionLocal()
    
    if clear_existing:
        print("\nClearing existing concepts...")
        db.execute(delete(GrammarConcept))
        db.commit()
    
    print("\nImporting to database...")
    service = GrammarService(db)
    count = service.bulk_create_concepts(concepts)
    print(f"Successfully imported {count} new concepts")
    
    # Verify
    from sqlalchemy import func
    total = db.query(func.count(GrammarConcept.id)).scalar()
    
    # Count by level
    result = db.query(GrammarConcept.level, func.count(GrammarConcept.id)).group_by(GrammarConcept.level).all()
    print(f"\nTotal concepts in database: {total}")
    for level, cnt in sorted(result):
        print(f"  {level}: {cnt}")
    
    db.close()


if __name__ == "__main__":
    import sys
    clear = '--clear' in sys.argv
    seed_grammar(clear_existing=clear)
