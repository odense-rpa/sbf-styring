from typing import Optional
from datafordeler import Datafordeler as DatafordelerClient
from httpx import ReadTimeout


class Datafordeler:
    def __init__(self, certifikat_sti: str, certifikat_nøglefil: str):
        self.client = DatafordelerClient(
            certifikat_sti=certifikat_sti, certifikat_nøglefil=certifikat_nøglefil
        )

    def hent_forældre_myndigheder(self, cpr: str) -> list[dict]:
        """Hent forældremyndighedsoplysninger for et givet CPR-nummer"""
        try:
            person_data = self.client.hent_personoplysninger(cpr)
        except Exception as e:
            if isinstance(e, ReadTimeout):
                return []
            raise
        return person_data.get("Person", {}).get("Foraeldermyndighedsoplysninger", [])


# Global instance
datafordeler: Optional[Datafordeler] = None


def init_datafordeler(certifikat_sti: str, certifikat_nøglefil: str) -> None:
    """Initialize the global datafordeler instance"""
    global datafordeler
    datafordeler = Datafordeler(certifikat_sti, certifikat_nøglefil)


def get_datafordeler() -> Datafordeler:
    """Get the global datafordeler instance"""
    if datafordeler is None:
        raise Exception("Datafordeler er ikke initialiseret")
    return datafordeler
