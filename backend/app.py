from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'law_scraper')))
from db import init_db

app = FastAPI(
    title="Bavarian Law API",
    description="API for accessing Bavarian state legislation",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class NormResponse(BaseModel):
    number: str
    title: str
    content: str

class LawResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None

@app.get("/")
async def root():
    return {
        "message": "Bavarian Law API",
        "docs": "/docs",
        "version": "1.0.0"
    }

@app.get("/api/laws", response_model=list[LawResponse])
async def get_laws():
    """Get all available laws"""
    conn = init_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, name, description FROM laws ORDER BY name")
            rows = cursor.fetchall()
        
        return [
            LawResponse(id=row[0], name=row[1], description=row[2])
            for row in rows
        ]
    finally:
        conn.close()

@app.get("/api/laws/{law_id}/norms")
async def get_norms_by_law(law_id: int):
    """Get all norms for a specific law"""
    conn = init_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT n.number, n.number_raw, n.title, n.url
                FROM norms n
                WHERE n.law_id = %s
                ORDER BY n.id
            """, (law_id,))
            rows = cursor.fetchall()
        
        if not rows:
            raise HTTPException(status_code=404, detail="Law not found or no norms available")
        
        return [
            {
                "number": row[0],
                "number_raw": row[1],
                "title": row[2],
                "url": row[3]
            }
            for row in rows
        ]
    finally:
        conn.close()

@app.get("/api/norms/{law_id}/{norm_number}")
async def get_norm(law_id: int, norm_number: str):
    """Get a specific norm by law ID and norm number"""
    conn = init_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT n.number, n.title, n.content, n.url, l.name, l.description
                FROM norms n
                JOIN laws l ON n.law_id = l.id
                WHERE n.law_id = %s AND n.number = %s
                LIMIT 1
            """, (law_id, norm_number))
            row = cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="Norm not found")
        
        return {
            "number": row[0],
            "title": row[1],
            "content": row[2],
            "url": row[3],
            "law_name": row[4],
            "law_description": row[5]
        }
    finally:
        conn.close()

@app.get("/api/search")
async def search_norms(q: str, limit: int = 20):
    """Search norms by title or content"""
    if len(q) < 3:
        raise HTTPException(status_code=400, detail="Search query must be at least 3 characters")
    
    conn = init_db()
    try:
        with conn.cursor() as cursor:
            search_term = f"%{q}%"
            cursor.execute("""
                SELECT n.number, n.title, n.content, l.name, n.law_id, l.description
                FROM norms n
                JOIN laws l ON n.law_id = l.id
                WHERE n.title LIKE %s OR n.content LIKE %s
                ORDER BY n.title
                LIMIT %s
            """, (search_term, search_term, limit))
            rows = cursor.fetchall()
        
        return [
            {
                "number": row[0],
                "title": row[1],
                "content": row[2][:200] + "..." if len(row[2]) > 200 else row[2],
                "law_name": row[3],
                "law_id": row[4],
                "law_description": row[5]
            }
            for row in rows
        ]
    finally:
        conn.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)