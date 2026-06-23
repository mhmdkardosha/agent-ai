from pydantic import BaseModel

class VehicleAction(BaseModel):
    vehicle_id: str
    action: str
    parameters: dict