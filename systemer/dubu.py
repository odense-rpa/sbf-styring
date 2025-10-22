from datetime import datetime
from typing import Optional
from kmd_nexus_client import utils
from dubu_client import DubuClientManager
from sbf_database import BarnSynkronisering
from automation_server_client import Credential


class Dubu(DubuClientManager):
    def __init__(self, brugernavn, adgangskode: str, idp: str):
        super().__init__(brugernavn, adgangskode, idp)

    def hent_dubu_borgere(self) -> list[BarnSynkronisering]:
        dubu_borgere: list[BarnSynkronisering] = []
        dubu_borgere_ufiltreret = self.sager.soeg_sager_sammenhaengende_borger_forloeb()

        for person in dubu_borgere_ufiltreret["value"]:
            if (
                person.get("primaerPerson") is not None
                and person.get("primaerPerson", {}).get("cprnr") is not None
            ):
                sagsbehandler = self.brugere.hent_org_bruger(
                    person.get("primaerBehandler", {}).get("orgBrugerId", -1)
                )

                if sagsbehandler is None:
                    continue

                if not utils.is_valid_cpr(person.get("primaerPerson", {}).get("cprnr")):
                    continue

                sagsbehandler_information = {
                    "dubu": {
                        "initialer": sagsbehandler.get("adresse", {})
                        .get("emailAdresse", "")
                        .split("@")[0],
                        "navn": sagsbehandler.get("fuldeNavn", ""),
                        "email": sagsbehandler.get("adresse", {}).get(
                            "emailAdresse", ""
                        ),
                        "telefon": sagsbehandler.get("adresse", {}).get(
                            "mobiltelefon", ""
                        ),
                    },
                    "nexus": {},
                }

                barn = BarnSynkronisering(
                    barn_cpr=person["primaerPerson"]["cprnr"],
                    barn_foraelder_cpr="",
                    barn_sidst_set=datetime.now(),
                    barn_sagsbehandler_information=sagsbehandler_information,                    
                )

                dubu_borgere.append(barn)

        return dubu_borgere


dubu: Optional[Dubu] = None


def init_dubu(credentials: Credential) -> None:
    global dubu
    dubu = Dubu(
        brugernavn=f"{credentials.username}@odense.dk",
        adgangskode=credentials.password,
        idp=credentials.data["idp"],
    )


def get_dubu() -> Dubu:
    if dubu is None:
        raise Exception("Dubu er ikke initialiseret")
    return dubu
