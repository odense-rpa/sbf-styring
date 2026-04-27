from zoneinfo import ZoneInfo
from datetime import datetime
from typing import Optional
from kmd_nexus_client import utils
from dubu_client import DubuClientManager
from automation_server_client import Credential


class Dubu(DubuClientManager):
    def __init__(self, brugernavn, adgangskode: str, idp: str):
        super().__init__(brugernavn, adgangskode, idp)

    def hent_dubu_borgere(self) -> list[dict]:
        dubu_borgere: list[dict] = []
        dubu_borgere_ufiltreret = self.sager.soeg_sager_sammenhaengende_borger_forloeb()

        for person in dubu_borgere_ufiltreret["value"]:
            try:
                cpr = person.get("primaerPerson", {}).get("cprnr", None)
                if cpr is None:
                    continue

                if len([x for x in dubu_borgere if x["cpr"] == cpr]) > 0:
                    continue

                sagsbehandler = self.brugere.hent_org_bruger(
                    person.get("primaerBehandler", {}).get("orgBrugerId", -1)
                )

                if sagsbehandler is None:
                    continue

                if not utils.is_valid_cpr(cpr):
                    continue

                if len([x for x in dubu_borgere if x["cpr"] == cpr]) > 0:
                    continue

                sagsbehandler_information = {
                    "initialer": sagsbehandler.get("adresse", {})
                    .get("emailAdresse", "")
                    .split("@")[0],
                    "navn": sagsbehandler.get("fuldeNavn", ""),
                    "email": sagsbehandler.get("adresse", {}).get("emailAdresse", ""),
                    "telefon": sagsbehandler.get("adresse", {}).get("mobiltelefon", ""),
                    "system": "Dubu",
                }

                dubu_borgere.append(
                    {
                        "cpr": cpr,
                        "navn": person["primaerPerson"]["fuldeNavn"],
                        "aktiv": True,
                        "sidst_set": datetime.now(ZoneInfo("Europe/Copenhagen")),
                        "sagsbehandler": [sagsbehandler_information],
                    }
                )
            except Exception:
                continue

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
    global dubu
    if dubu is None:
        raise Exception("Dubu er ikke initialiseret")
    return dubu
