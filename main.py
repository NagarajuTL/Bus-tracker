from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from firebase_admin import credentials, firestore, initialize_app
from firebase_admin.auth import create_user

# Initialize FastAPI app
app = FastAPI()
origins = [
    "https://project-1-70d13.web.app",
    "http://127.0.0.1:5500"]

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Firebase Admin SDK with credentials
cred = credentials.Certificate("productkey.json")  # Replace with your key path
initialize_app(cred)
db = firestore.client()

# Pydantic models for request bodies
class UserDetails(BaseModel):
    email: str
    password: str
    name: str
    user_ref: str
    bus_id:int  # Optional field to store additional reference

class LocationData(BaseModel):
    bus_latitude: float
    bus_longitude: float

# Endpoint to create a new user
@app.post("/users/")
async def create_user_endpoint(user_details: UserDetails):
    try:
        # Create a user in Firebase Auth
        user = create_user(email=user_details.email, password=user_details.password)
        
        # Create a new user document in Firestore with initial location data
        db.collection("users").document(user.uid).set({
            "name": user_details.name,
            "email": user_details.email,
            "password":user_details.password,
            "user_ref": user_details.user_ref,
            "bus_id":user_details.bus_id,
            "bus_latitude": 0.0,  # Default initial latitude
            "bus_longitude": 0.0  # Default initial longitude
        })
        return {"message": "User created successfully", "user_id": user.uid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Endpoint to update the user's location

@app.post("/update-location/{user_id}")
async def update_location(user_id: str, location: LocationData):
    user_ref = db.collection('users').document(user_id)  # Change 'drivers' to 'users'
    try:
        user_ref.set({
            'bus_latitude': location.bus_latitude,
            'bus_longitude': location.bus_longitude
        }, merge=True)  # Use merge=True to keep existing data
        return {"message": "Location updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/location/{bus_id}")
async def get_bus_location(bus_id: str):
    try:
        bus_ref = db.collection("buses").document(bus_id)
        bus_doc = bus_ref.get()
        if bus_doc.exists:
            return bus_doc.to_dict()  # Return the location data
        else:
            raise HTTPException(status_code=404, detail="Bus location not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



# Endpoint to retrieve user details (optional for verifying data)
@app.get("/users/{user_id}")
async def get_user_details(user_id: str):
    try:
        user_ref = db.collection("users").document(user_id)
        user_doc = user_ref.get()
        if user_doc.exists:
            return user_doc.to_dict()  # Return user data
        else:
            raise HTTPException(status_code=404, detail="User not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
