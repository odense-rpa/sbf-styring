import copy

from datetime import datetime
from httpx import HTTPStatusError
from kmd_nexus_client import utils
from typing import Optional
from automation_server_client import Credential
from momentum_client.manager import MomentumClientManager
from sbf_database import BarnSynkronisering
from .datafordeler import get_datafordeler

class Momentum(MomentumClientManager):
    def __init__(self, base_url, client_id, client_secret, api_key, resource):
        super().__init__(base_url, client_id, client_secret, api_key, resource)

    def filtrer_sbf_kandidater(self, borgere: list[BarnSynkronisering]) -> list[BarnSynkronisering]:
        sbf_kandidater = []    

        for barn in borgere:
            try:
                datafordeler = get_datafordeler()
                forældre_myndigheder = datafordeler.hent_forældre_myndigheder(str(barn.barn_cpr))
                for forældre_myndighed in forældre_myndigheder:
                    if self.kontroller_forælder_i_momentum(forældre_myndighed):
                        forældre_cpr = forældre_myndighed.get("Foraelderoplysning", {}).get("Foraelder", {}).get("foraelderPersonnummer", "")
                        if not utils.is_valid_cpr(forældre_cpr):
                            continue
                        
                        borger = self.borgere.hent_borger(forældre_myndighed.get("Foraelderoplysning", {}).get("Foraelder", {}).get("foraelderPersonnummer", ""))

                        if borger is None:
                            continue

                        ansvarlig_sagsbehandlere_reference = self.borgere.hent_ansvarlige_sagsbehandlere(
                            borger
                        )

                        ansvarlig_sagsbehandler = ansvarlig_sagsbehandlere_reference[0] if ansvarlig_sagsbehandlere_reference and len(ansvarlig_sagsbehandlere_reference) > 0 else None
                        
                        if ansvarlig_sagsbehandler is None:
                            continue

                        ansvarlig_sagsbehandler = self.borgere.hent_aktør(ansvarlig_sagsbehandler.get("caseworkerId", ""))

                        if ansvarlig_sagsbehandler is None:
                            continue

                        sagsbehandler_information = {
                            "momentum": {
                                "initialer": ansvarlig_sagsbehandler.get("email", "")
                                .split("@")[0],
                                "navn": ansvarlig_sagsbehandler.get("displayName", ""),
                                "email": ansvarlig_sagsbehandler.get("email", ""),
                                "telefon": ansvarlig_sagsbehandler.get("phone", {})
                            }                    
                        }

                        barn = copy.deepcopy(barn)
                        barn.barn_foraelder_cpr = forældre_cpr
                        barn.foraelder_sidst_set = datetime.now()
                        barn.foraelder_sagsbehandler_information = sagsbehandler_information
                        sbf_kandidater.append(barn)
            except Exception:
                continue
        
        return sbf_kandidater
    
    def kontroller_forælder_i_momentum(self, forælder_myndighed: dict) -> bool:
        try:
            forælder = self.borgere.hent_borger(forælder_myndighed.get("Foraelderoplysning", {}).get("Foraelder", {}).get("foraelderPersonnummer", ""))
        except HTTPStatusError:
            return False
        
        if not forælder or forælder.get("cprStatusCode", "") == "DØD":
            return False
        if forælder.get("targetGroupCode") is None:
            return False
        return True

momentum: Optional[Momentum] = None

def init_momentum(credentials: Credential) -> None:
    global momentum
    momentum = Momentum(
        base_url=credentials.data["base_url"],
        client_id=credentials.username,
        client_secret=credentials.password,
        api_key=credentials.data["api_key"],
        resource=credentials.data["resource"]
    )

def get_momentum() -> Momentum:
    if momentum is None:
        raise Exception("Momentum er ikke initialiseret")
    return momentum