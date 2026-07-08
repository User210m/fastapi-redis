import json
import os
from typing import Optional

import redis
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

# These values come from Kubernetes ConfigMap and Secret.
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")

redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    password=REDIS_PASSWORD,
    decode_responses=True,
)


class Item(BaseModel):
    name: str
    description: str


class ItemUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


@app.get("/")
def home():
    return {"message": "FastAPI connected to Redis"}


@app.post("/items")
def create_item(item: Item):
    try:
        item_id = redis_client.incr("item_id")

        item_data = {
            "id": item_id,
            "name": item.name,
            "description": item.description,
        }

        redis_client.set(
            f"item:{item_id}",
            json.dumps(item_data),
        )

        return {
            "message": "Item created",
            "item": item_data,
        }

    except redis.exceptions.RedisError as error:
        raise HTTPException(
            status_code=500,
            detail=f"Redis error: {error}",
        )


@app.get("/items")
def get_items():
    try:
        items = []

        for key in redis_client.keys("item:*"):
            stored_item = redis_client.get(key)

            if stored_item:
                items.append(json.loads(stored_item))

        items.sort(key=lambda item: item["id"])

        return {"items": items}

    except redis.exceptions.RedisError as error:
        raise HTTPException(
            status_code=500,
            detail=f"Redis error: {error}",
        )


@app.patch("/items/{item_id}")
def update_item(item_id: int, item: ItemUpdate):
    try:
        key = f"item:{item_id}"
        stored_item = redis_client.get(key)

        if stored_item is None:
            raise HTTPException(
                status_code=404,
                detail="Item not found",
            )

        update_data = item.model_dump(exclude_unset=True)

        if not update_data:
            raise HTTPException(
                status_code=400,
                detail="Provide a name or description to update",
            )

        existing_item = json.loads(stored_item)
        existing_item.update(update_data)

        redis_client.set(
            key,
            json.dumps(existing_item),
        )

        return {
            "message": "Item updated",
            "item": existing_item,
        }

    except redis.exceptions.RedisError as error:
        raise HTTPException(
            status_code=500,
            detail=f"Redis error: {error}",
        )