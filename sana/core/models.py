from typing import Annotated

from pydantic import BaseModel, Field

from pydantic_extra_types.country import CountryAlpha2
from pydantic_extra_types.timezone_name import TimeZoneName

class Actor(BaseModel):
    id: Annotated[str, Field('anonymous')]
    country: Annotated[CountryAlpha2, Field('US')]
    zip_code: Annotated[str, Field('10001')]
    timezone: Annotated[TimeZoneName, Field('America/New_York')]

class InvokePayload(BaseModel):
    prompt: Annotated[str, Field(...)]
    actor: Annotated[Actor | None, Field(None)]