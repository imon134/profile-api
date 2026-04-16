# Profile API

A serverless REST API built with Python (Vercel) that generates user profiles using external data sources and stores them in a lightweight SQLite database.

---

## Base URL
https://profile-kv54vac8j-imon1.vercel.app/
---

## Features

- Create user profiles from a name
- Automatic enrichment using external APIs:
  - Gender prediction (Genderize)
  - Age prediction (Agify)
  - Nationality prediction (Nationalize)
- Prevent duplicate profiles by name
- Retrieve all profiles with filtering
- Retrieve single profile by ID
- Delete profiles
- Fully JSON-based REST API
- CORS enabled

---
## Endpoints

### 1. Create Profile

**POST** `/api/profiles`

Request:

```json
{
  "name": "ella"
}
```
Response (201):
```json
{
  "status": "success",
  "data": {
    "id": "uuid",
    "name": "ella",
    "gender": "female",
    "gender_probability": 0.99,
    "sample_size": 1234,
    "age": 25,
    "age_group": "adult",
    "country_id": "NG",
    "country_probability": 0.85,
    "created_at": "2026-04-16T12:00:00Z"
  }
}
```
If profile exists:
```json
{
  "status": "success",
  "message": "Profile already exists",
  "data": { ... }
}
```
### 2. Get All Profiles

**GET** `/api/profiles`

Optional query parameters:

gender
country_id
age_group

Example: /api/profiles?gender=male&country_id=ng
Response:
```json
{
  "status": "success",
  "count": 2,
  "data": [
    {
      "id": "id-1",
      "name": "john",
      "gender": "male",
      "age": 30,
      "age_group": "adult",
      "country_id": "NG"
    }
  ]
}
```
### 3. Get Single Profile

**GET** `/api/profiles/{id}`

Response:
```json
{
  "status": "success",
  "data": {
    "id": "uuid",
    "name": "ella",
    "gender": "female",
    "gender_probability": 0.99,
    "sample_size": 1234,
    "age": 25,
    "age_group": "adult",
    "country_id": "NG",
    "country_probability": 0.85,
    "created_at": "2026-04-16T12:00:00Z"
  }
}
```
If not found:
```json
{
  "status": "error",
  "message": "Profile not found"
}
```
### 4. Delete Profile

**DELETE** `/api/profiles/{id}`

Response:
`204 No Content`

---
## Error Responses

All errors follow this format:
```json
{
  "status": "error",
  "message": "Error description"
}
```
Common errors:
| Code | Meaning               |
| ---- | --------------------- |
| 400  | Missing or empty name |
| 422  | Invalid input type    |
| 404  | Profile not found     |
| 502  | External API failure  |

---
## External API Rules

### The API depends on:
1. Genderize
2. Agify
3. Nationalize

### Failure conditions:
1. Gender is null or count = 0 → 502
2. Age is null → 502
3. No country data → 502


## CORS
All responses include:
`Access-Control-Allow-Origin: *`

## Tech Stack
1. Python
2. SQLite (in-memory /tmp)
3. http.server (BaseHTTPRequestHandler)
4. httpx (external API calls)
5.Vercel Serverless Functions

---
## Project Structure
profile-api/
├── main.py
├── requirements.txt
├── vercel.json
└── README.md

## Deployment
Deploy to Vercel:
- Push to GitHub
- Import into Vercel
- Set entry file: main.py
- Deploy

Example curl request
```json
curl -X POST "https://your-domain.vercel.app/api/profiles" \
  -H "Content-Type: application/json" \
  -d '{"name":"ella"}'
````

---
## Notes
- Data stored in /tmp (not permanent)
- Database resets on redeploy
- Designed for serverless environments
