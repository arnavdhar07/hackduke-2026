---
description: Inject when writing FastAPI route handlers, dependency
  injection, asyncpg queries, or Redis cache logic for ReHarvestAI.
---

## asyncpg query patterns
```python
# Connection pool (from app.database import pool)
async def get_zones_for_field(field_id: str) -> list[dict]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT z.id, z.label, ST_AsGeoJSON(z.polygon)::json as polygon,
                   n.ndvi, n.ndwi, n.ndre, n.captured_at
            FROM zones z
            JOIN LATERAL (
                SELECT ndvi, ndwi, ndre, captured_at
                FROM ndvi_timeseries
                WHERE zone_id = z.id
                ORDER BY captured_at DESC
                LIMIT 1
            ) n ON true
            WHERE z.field_id = $1
            ORDER BY z.created_at
            """,
            uuid.UUID(field_id)
        )
        return [dict(r) for r in rows]
```

## Redis cache pattern
```python
async def get_zones_cached(field_id: str) -> list[dict]:
    cache_key = f"zone_scores:{field_id}"

    # Check cache
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    # DB fallback
    zones = await get_zones_for_field(field_id)

    # Write through with TTL
    await redis.setex(cache_key, 3600, json.dumps(zones, default=str))
    return zones

# Invalidation (call this in output_formatter after writing recommendations)
await redis.delete(f"zone_scores:{field_id}")
```

## FastAPI response model pattern
```python
@router.get("/fields/{field_id}/zones", response_model=list[ZoneResponse])
async def get_zones(field_id: str):
    zones = await get_zones_cached(field_id)
    return [ZoneResponse.model_validate(z) for z in zones]
```

## Stub pattern (use until real DB logic is ready)
```python
@router.get("/fields/{field_id}/zones", response_model=list[ZoneResponse])
async def get_zones(field_id: str):
    # STUB — replace with real implementation
    return [
        ZoneResponse(
            id="zone-001",
            field_id=field_id,
            label="Zone A",
            polygon={"type": "Polygon", "coordinates": [[...]]},
            latest_scores={"ndvi": 72.5, "ndwi": 45.0, "ndre": 61.0,
                          "captured_at": "2025-03-01T00:00:00Z"},
            timeseries=[]
        )
    ]
```

## Gotchas
- asyncpg returns Record objects not dicts — always wrap with dict(row)
- ST_AsGeoJSON returns a JSON string — cast with ::json in the query or
  json.loads() in Python before putting in Pydantic model
- UUID fields from asyncpg come back as uuid.UUID objects — call str() before
  putting in response or use json.dumps(default=str)
- pool.acquire() must be used as async context manager — never call
  pool.acquire() and store the connection without releasing it
- aioredis.get() returns bytes not str — always decode: value.decode("utf-8")
  or use decode_responses=True in the Redis connection init
