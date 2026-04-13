from datetime import datetime
from httpx import HTTPStatusError
from kmd_nexus_client import utils
from typing import Optional
from automation_server_client import Credential
from momentum_client.manager import MomentumClientManager
from .datafordeler import get_datafordeler

from sbf_database import Barn


class Momentum(MomentumClientManager):
    def __init__(self, base_url, client_id, client_secret, api_key, resource):
        super().__init__(base_url, client_id, client_secret, api_key, resource)

    def hent_sbf_kandidater(self, børn: list[Barn]) -> list[dict]:
        sbf_kandidater = []

        for barn in børn:
            try:
                datafordeler = get_datafordeler()
                forældre_myndigheder = datafordeler.hent_forældre_myndigheder(
                    str(barn.cpr)
                )
                for forældre_myndighed in forældre_myndigheder:
                    forældre_cpr = (
                        forældre_myndighed.get("Foraeldermyndighedsoplysning", {})
                        .get("Foraeldermyndig", {})
                        .get("foraeldermyndighedPersonnummer", "")
                    )
                    if self._kontroller_forælder_i_momentum(forældre_cpr):
                        if not utils.is_valid_cpr(forældre_cpr):
                            continue

                        borger = self.borgere.hent_borger(forældre_cpr)

                        if borger is None:
                            continue

                        ansvarlig_sagsbehandlere_reference = (
                            self.borgere.hent_ansvarlige_sagsbehandlere(borger)
                        )

                        ansvarlig_sagsbehandler = (
                            ansvarlig_sagsbehandlere_reference[0]
                            if ansvarlig_sagsbehandlere_reference
                            and len(ansvarlig_sagsbehandlere_reference) > 0
                            else None
                        )

                        if ansvarlig_sagsbehandler is None:
                            continue

                        ansvarlig_sagsbehandler = self.borgere.hent_aktør(
                            ansvarlig_sagsbehandler.get("caseworkerId", "")
                        )

                        if ansvarlig_sagsbehandler is None:
                            continue

                        sagsbehandler_information = {
                            "initialer": ansvarlig_sagsbehandler.get("email", "").split(
                                "@"
                            )[0],
                            "navn": ansvarlig_sagsbehandler.get("displayName", ""),
                            "email": ansvarlig_sagsbehandler.get("email", ""),
                            "telefon": ansvarlig_sagsbehandler.get("phone", {}),
                        }

                        forælder = {
                            "cpr": forældre_cpr,
                            "navn": borger.get("displayName", ""),
                            "aktiv": True,
                            "sidst_set": datetime.now(),
                            "sagsbehandler": sagsbehandler_information,
                            "barn": barn.cpr,
                        }

                        sbf_kandidater.append(forælder)
            except Exception:
                continue

        return sbf_kandidater

    def _kontroller_forælder_i_momentum(self, forældre_cpr: str) -> bool:
        try:
            forælder = self.borgere.hent_borger(forældre_cpr)
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
        resource=credentials.data["resource"],
    )


def get_momentum() -> Momentum:
    if momentum is None:
        raise Exception("Momentum er ikke initialiseret")
    return momentum
