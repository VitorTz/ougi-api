from pydantic import BaseModel


class DeviceInfo(BaseModel):

    device: str
    ip_address: str