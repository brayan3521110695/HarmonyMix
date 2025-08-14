# mongo.py
import os
from pymongo import MongoClient, ASCENDING, DESCENDING

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
MONGO_DB  = os.getenv("MONGO_DB", "harmonymix")

client = MongoClient(MONGO_URL)
mdb = client[MONGO_DB]

def ensure_indexes():
    mdb.tracks.create_index([("userId", ASCENDING), ("uploadedAt", DESCENDING)])
    mdb.tracks.create_index([("sha256", ASCENDING)], unique=True)
    mdb.trackFeatures.create_index([("trackId", ASCENDING)], unique=True)
    mdb.trackFeatures.create_index([("bpm", ASCENDING), ("musicalKey", ASCENDING)])
    mdb.feedback.create_index([("userId", ASCENDING), ("target.type", ASCENDING), ("target.id", ASCENDING)])
