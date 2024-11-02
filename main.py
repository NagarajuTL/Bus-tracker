from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from firebase_admin import credentials, firestore, initialize_app,messaging
from firebase_admin.auth import create_user
from dotenv import load_dotenv
from fastapi.staticfiles import StaticFiles
import math
import os
from twilio.rest import Client
from datetime import datetime, timedelta
# Initialize FastAPI app
app = FastAPI()


# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
load_dotenv()
firebase_key_path = os.getenv("FIREBASE_KEY_PATH")
account_sid=os.getenv("TWILIO_SID")
account_token=os.getenv("TWILIO_AUTH")
phonenumber=os.getenv("TWILIO_PHONENUMBER")
# Initialize Firebase Admin SDK with credentials

cred = credentials.Certificate(firebase_key_path)
initialize_app(cred)
db = firestore.client()

# Pydantic models for request bodies
class UserDetails(BaseModel):
    email: str
    password: str
    name: str
    user_ref: str
    bus_id:int  
    phone_number:str

class Location(BaseModel):
    latitude: float
    longitude: float

class UserLocation(BaseModel):
    user_latitude:float
    user_longitude:float

# Endpoint to create a new user
@app.post("/users/")
async def create_user_endpoint(user_details: UserDetails):
    try:
        user = create_user(email=user_details.email, password=user_details.password)
        
        db.collection("users").document(user.uid).set({
            "name": user_details.name,
            "email": user_details.email,
            "password": user_details.password,
            "user_ref": user_details.user_ref,
            "bus_id": user_details.bus_id,
            "bus_latitude": 0.0,  # Default initial latitude
            "bus_longitude": 0.0,  # Default initial longitude
            "last_notified_time": datetime.min.strftime("%Y-%m-%d %H:%M:%S"),
            "phone_number":user_details.phone_number
        })
        return {"message": "User created successfully", "user_id": user.uid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

app.mount("/static", StaticFiles(directory="static"), name="static")
from datetime import datetime, timedelta
from fastapi import HTTPException

@app.post("/update-location/{bus_id}")
async def update_location(bus_id: str, location: Location):
    try:
        users_ref = db.collection("users")
        query = users_ref.where("bus_id", "==", int(bus_id))
        users = query.stream()

        for user in users:
            user_data = user.to_dict()
            phone_number = user_data.get('phone_number')
            last_notified_time_str = user_data.get('last_notified_time')
            user_latitude = user_data.get('user_latitude')
            user_longitude = user_data.get('user_longitude')

            last_notified_time = datetime.min
            if last_notified_time_str:
                last_notified_time = datetime.strptime(last_notified_time_str, "%Y-%m-%d %H:%M:%S")

            # Calculate distance only if user location exists
            distance = None
            if user_latitude is not None and user_longitude is not None:
                distance = haversine(location.latitude, location.longitude, user_latitude, user_longitude)

            # Notify if within distance and notification interval
            if distance is not None and distance < 100 and (datetime.now() - last_notified_time >= timedelta(hours=6)):
                if phone_number:
                    await send_sms(phone_number, "The bus is near your desired location!")
                    # Update last_notified_time
                    print(f"Updating last_notified_time for user {user.id}")
                    users_ref.document(user.id).set({
                        "last_notified_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }, merge=True)

            users_ref.document(user.id).set({
                "bus_latitude": location.latitude,
                "bus_longitude": location.longitude
            }, merge=True)

        return {
            "message": f"Locations updated successfully for all users with bus_id: {bus_id}",
        }
    
    except Exception as e:
        print(f"Error updating location for bus_id {bus_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/users/{user_id}")
async def get_user_details(user_id: str):
    try:
        user_ref = db.collection("users").document(user_id)
        user_doc = user_ref.get()
        if user_doc.exists:
            return user_doc.to_dict() 
        else:
            raise HTTPException(status_code=404, detail="User not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

@app.post("/add_location/{user_id}")
async def add_location(user_id: str, location_data: UserLocation):
    try:
        user_ref = db.collection("users").document(user_id)
        user_ref.update({
            "user_latitude": location_data.user_latitude,
            "user_longitude": location_data.user_longitude
        })
        return {"status": "Location updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # Radius of the Earth in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance = R * c * 1000  # Convert to meters
    return distance

client = Client(account_sid, account_token)
def send_sms(to_phone_number: str, message_body: str):
    message = client.messages.create(
        body=message_body,
        from_=phonenumber,
        to=to_phone_number
    )
    return message.sid  
