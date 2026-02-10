"""
Example API Endpoints for AI Classifications

Copy these endpoints into your existing API file (e.g., api.py or routes/ai_routes.py)
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
import psycopg2.extras

router = APIRouter(tags=["AI Classifications"])


@router.get("/api/flights/{flight_id}/ai-classification")
def get_flight_classification(flight_id: str, schema: str = Query("live", description="Database schema")):
    """
    Get AI classification for a specific flight.
    
    Returns the most recent AI classification if multiple exist.
    Returns 404 if no classification found.
    """
    try:
        from pg_provider import get_connection
        
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(f"""
                    SELECT 
                        flight_id,
                        classification_text,
                        confidence_score,
                        processing_time_sec,
                        created_at,
                        error_message,
                        gemini_model
                    FROM {schema}.ai_classifications
                    WHERE flight_id = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (flight_id,))
                
                result = cursor.fetchone()
                
                if not result:
                    raise HTTPException(
                        status_code=404, 
                        detail=f"No AI classification found for flight {flight_id}"
                    )
                
                return {
                    "flight_id": result["flight_id"],
                    "classification": result["classification_text"],
                    "confidence_score": result["confidence_score"],
                    "processing_time_sec": result["processing_time_sec"],
                    "created_at": result["created_at"].isoformat() if result["created_at"] else None,
                    "error": result["error_message"],
                    "model": result["gemini_model"]
                }
                
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/api/ai-classifications/recent")
def get_recent_classifications(
    schema: str = Query("live", description="Database schema"),
    limit: int = Query(20, ge=1, le=100, description="Number of results"),
    offset: int = Query(0, ge=0, description="Pagination offset")
):
    """
    Get recent AI classifications with flight metadata.
    
    Returns list of classifications ordered by most recent first.
    """
    try:
        from pg_provider import get_connection
        
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                # Get total count
                cursor.execute(f"""
                    SELECT COUNT(*) 
                    FROM {schema}.ai_classifications
                    WHERE error_message IS NULL
                """)
                total = cursor.fetchone()["count"]
                
                # Get classifications
                cursor.execute(f"""
                    SELECT 
                        c.flight_id,
                        c.classification_text,
                        c.created_at,
                        c.processing_time_sec,
                        m.callsign,
                        m.origin_airport,
                        m.destination_airport,
                        m.aircraft_type
                    FROM {schema}.ai_classifications c
                    LEFT JOIN {schema}.flight_metadata m ON c.flight_id = m.flight_id
                    WHERE c.error_message IS NULL
                    ORDER BY c.created_at DESC
                    LIMIT %s OFFSET %s
                """, (limit, offset))
                
                results = cursor.fetchall()
                
                return {
                    "total": total,
                    "limit": limit,
                    "offset": offset,
                    "classifications": [
                        {
                            "flight_id": r["flight_id"],
                            "classification": r["classification_text"],
                            "callsign": r["callsign"],
                            "origin": r["origin_airport"],
                            "destination": r["destination_airport"],
                            "aircraft_type": r["aircraft_type"],
                            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                            "processing_time": r["processing_time_sec"]
                        }
                        for r in results
                    ]
                }
                
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/api/ai-classifications/stats")
def get_classification_stats(schema: str = Query("live", description="Database schema")):
    """
    Get AI classification statistics and insights.
    
    Returns overall stats and top classification categories.
    """
    try:
        from pg_provider import get_connection
        
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                # Overall stats
                cursor.execute(f"""
                    SELECT 
                        COUNT(*) as total,
                        COUNT(*) FILTER (WHERE error_message IS NULL) as success,
                        COUNT(*) FILTER (WHERE error_message IS NOT NULL) as failed,
                        AVG(processing_time_sec) FILTER (WHERE error_message IS NULL) as avg_time,
                        MIN(created_at) as first_classification,
                        MAX(created_at) as last_classification
                    FROM {schema}.ai_classifications
                """)
                
                stats = cursor.fetchone()
                
                # Top classifications
                cursor.execute(f"""
                    SELECT 
                        classification_text,
                        COUNT(*) as count
                    FROM {schema}.ai_classifications
                    WHERE error_message IS NULL
                    GROUP BY classification_text
                    ORDER BY count DESC
                    LIMIT 10
                """)
                
                top_classifications = cursor.fetchall()
                
                return {
                    "overview": {
                        "total_classifications": stats["total"] or 0,
                        "successful": stats["success"] or 0,
                        "failed": stats["failed"] or 0,
                        "success_rate": round(stats["success"] / stats["total"] * 100, 2) if stats["total"] > 0 else 0,
                        "avg_processing_time_sec": round(stats["avg_time"], 2) if stats["avg_time"] else None,
                        "first_classification": stats["first_classification"].isoformat() if stats["first_classification"] else None,
                        "last_classification": stats["last_classification"].isoformat() if stats["last_classification"] else None
                    },
                    "top_classifications": [
                        {
                            "text": r["classification_text"],
                            "count": r["count"]
                        }
                        for r in top_classifications
                    ]
                }
                
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


# Optional: Add this helper function to pg_provider.py
def get_ai_classification_for_flight(flight_id: str, schema: str = 'live'):
    """
    Helper function to get AI classification from anywhere in your code.
    
    Usage:
        from pg_provider import get_ai_classification_for_flight
        classification = get_ai_classification_for_flight("3d7211ef")
        if classification:
            print(f"AI says: {classification['classification_text']}")
    """
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(f"""
                    SELECT * FROM {schema}.ai_classifications
                    WHERE flight_id = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (flight_id,))
                
                result = cursor.fetchone()
                return dict(result) if result else None
                
    except Exception as e:
        import logging
        logging.error(f"Error fetching AI classification for {flight_id}: {e}")
        return None
