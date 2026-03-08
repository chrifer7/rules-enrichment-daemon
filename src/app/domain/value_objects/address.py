from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Address:
    name: str
    address_line_1: str
    city: str
    postal_code: str
    country_code: str
