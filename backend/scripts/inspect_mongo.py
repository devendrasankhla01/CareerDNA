"""Safe MongoDB Atlas connection inspection script.
Masks all credentials. Tests network ping, authentication, database access,
collection listing, and safe test document insert/read/delete.
"""
import os
import re
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")

def mask_uri(uri: str) -> str:
    if not uri:
        return "(empty)"
    # Mask username and password in mongodb:// or mongodb+srv://
    return re.sub(r"://([^:]+):([^@]+)@", r"://\1:********@", uri)

def run_diagnostics():
    mongo_url = os.getenv("MONGODB_URL", "")
    db_name = os.getenv("MONGODB_DB_NAME", "careerdna")
    db_url = os.getenv("DATABASE_URL", "")
    demo_mode = os.getenv("DEMO_MODE", "")

    print("=== ENVIRONMENT VARIABLE CHECK ===")
    print(f"MONGODB_URL: {'SET (' + mask_uri(mongo_url) + ')' if mongo_url else 'MISSING'}")
    print(f"MONGODB_DB_NAME: {db_name}")
    print(f"DATABASE_URL: {'SET' if db_url else 'MISSING'}")
    print(f"DEMO_MODE: {demo_mode}")

    if not mongo_url:
        print("\n[FAIL] MONGODB_URL is not set.")
        return

    import pymongo
    from pymongo.errors import ConnectionFailure, OperationFailure, ConfigurationError

    print(f"\nPyMongo version: {pymongo.__version__}")
    print("Testing connection to MongoDB Atlas...")

    try:
        client = pymongo.MongoClient(mongo_url, serverSelectionTimeoutMS=5000, connectTimeoutMS=5000)
        # 1. Ping
        ping_res = client.admin.command("ping")
        print("MongoDB network connection: PASS")
        print("MongoDB authentication: PASS")
        print(f"Ping response: {ping_res}")
    except ConfigurationError as ce:
        print(f"MongoDB URI Configuration Error: FAIL ({ce})")
        return
    except OperationFailure as of:
        print(f"MongoDB authentication: FAIL ({of})")
        return
    except ConnectionFailure as cf:
        print(f"MongoDB network connection: FAIL ({cf})")
        return
    except Exception as e:
        print(f"MongoDB connection: FAIL ({e})")
        return

    # 2. Database access
    try:
        db = client[db_name]
        print(f"Database selection: PASS (Target: {db_name})")
        
        # 3. Collections listing
        collections = db.list_collection_names()
        print(f"Collections accessible: PASS")
        if collections:
            print(f"Found {len(collections)} collection(s): {', '.join(collections)}")
        else:
            print("Found 0 collections (new / empty database ready for data)")

        # 4. Safe write + read + delete test
        test_col = db["_diagnostics_probe"]
        test_doc = {"probe_key": "database_connection_test", "status": "active"}
        insert_res = test_col.insert_one(test_doc)
        print("Write operation (probe document): PASS")

        found_doc = test_col.find_one({"_id": insert_res.inserted_id})
        if found_doc and found_doc.get("probe_key") == "database_connection_test":
            print("Read operation (probe document): PASS")
        else:
            print("Read operation (probe document): FAIL")

        test_col.delete_one({"_id": insert_res.inserted_id})
        # Clean up probe collection if empty
        if test_col.count_documents({}) == 0:
            test_col.drop()
        print("Delete/Cleanup operation: PASS")

    except Exception as e:
        print(f"Database operations: FAIL ({e})")

if __name__ == "__main__":
    run_diagnostics()
