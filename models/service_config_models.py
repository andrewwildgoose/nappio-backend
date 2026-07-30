from pydantic import BaseModel

class ServiceAreas(BaseModel):
    postcode_prefixes: list[str]