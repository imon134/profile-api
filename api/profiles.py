import json

# simple in-memory database (resets on deploy)
db = {}

def handler(request):
    method = request.get("method")

    # READ BODY
    body = request.get("body") or "{}"
    data = json.loads(body)

    # CREATE PROFILE (POST)
    if method == "POST":
        name = data.get("name")

        if not name:
            return {
                "statusCode": 400,
                "body": json.dumps({"status": "error", "message": "Name required"})
            }

        db[name] = {"name": name}

        return {
            "statusCode": 200,
            "body": json.dumps({"status": "success", "profile": db[name]})
        }

    # GET PROFILE
    if method == "GET":
        name = request.get("query", {}).get("name")

        profile = db.get(name)

        if not profile:
            return {
                "statusCode": 404,
                "body": json.dumps({"status": "error", "message": "Profile not found"})
            }

        return {
            "statusCode": 200,
            "body": json.dumps({"status": "success", "profile": profile})
        }

    return {
        "statusCode": 405,
        "body": json.dumps({"status": "error", "message": "Method not allowed"})
    }