from typing import Optional
from datafordeler import DatafordelerGraphQL
from httpx import ReadTimeout


class Datafordeler:
    def __init__(self, client_id: str, client_secret: str):
        self.client = DatafordelerGraphQL(
            client_id=client_id, client_secret=client_secret
        )

    def hent_forældre_myndigheder(self, cpr: str) -> list[str]:
        """Hent CPR-numre på aktuelle forældremyndighedsindehavere for et givet CPR-nummer"""
        try:
            person = self.client.hent_person(cpr)
        except Exception as e:
            if isinstance(e, ReadTimeout):
                return []
            raise
        return list(person.foraeldremyndighed)


# Global instance
datafordeler: Optional[Datafordeler] = None


def init_datafordeler(client_id: str, client_secret: str) -> None:
    """Initialize the global datafordeler instance"""
    global datafordeler
    datafordeler = Datafordeler(client_id, client_secret)


def get_datafordeler() -> Datafordeler:
    """Get the global datafordeler instance"""
    if datafordeler is None:
        raise Exception("Datafordeler er ikke initialiseret")
    return datafordeler
