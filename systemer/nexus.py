from typing import Optional, List, Any
from datetime import datetime
from zoneinfo import ZoneInfo
from kmd_nexus_client import NexusClientManager, utils
from kmd_nexus_client.tree_helpers import filter_by_path
from nexus_database_client import NexusDatabaseClient
from automation_server_client import Credential

nexus_forløb = [
    "Sag: Anbringelse",
    "Sag: Bekæmpelse af ungdomskriminalitet",
    "Sag: Forebyggende og støttende indsatser",
    "Sag: Hjælp til barnet eller den unges forældre",
    "Sag: Rusmiddelbehandling",
    "Sag: Screening, afdækning og børnefaglig undersøgelse",
    "Sag: Støtte til børn og unge med funktionsnedsættelse",
    "Sag: Underretning",
    "Sag: Ungestøtte og overgangen til voksenlivet",
    "Sag: Æresrelaterede konflikter",
    "Udfører - Familiebehandling og vejledning",
    "Udfører - Støtte- og kontaktperson",
    "Udfører - Æresrelaterede konflikter",
]


class Nexus(NexusClientManager):
    def __init__(
        self,
        instance,
        client_id,
        client_secret,
        db_host,
        db_port,
        db_user,
        db_password,
        db_database,
    ):
        super().__init__(instance, client_id, client_secret)
        self.database = NexusDatabaseClient(
            host=db_host,
            port=db_port,
            user=db_user,
            password=db_password,
            database=db_database,
        )

    def hent_nexus_borgere(self) -> list[dict]:
        nexus_borgere = []
        nexus_borgere_ufiltreret = (
            self.database.hent_borgere_til_sammenhængende_borgerforløb()
        )

        nexus_borgere_ufiltreret = nexus_borgere_ufiltreret

        for barn in nexus_borgere_ufiltreret:
            try:
                if not utils.is_valid_cpr(barn.get("cpr", "")):
                    continue

                try:
                    nexus_borger = self.borgere.hent_borger(barn["cpr"])
                except ValueError:
                    # Suppress invalid cpr-numbers
                    continue

                if not nexus_borger:
                    continue

                pathway = self.borgere.hent_visning(borger=nexus_borger)

                if pathway is None:
                    continue

                indsats_referencer = self.borgere.hent_referencer(visning=pathway)

                forløb = self._er_i_sbf_kandidat_forløb(indsats_referencer, barn)

                if forløb is None:
                    continue

                sagsbehandler = self._find_sagsbehandler(indsats_referencer, forløb)

                if sagsbehandler is None:
                    continue

                nexus_borgere.append(
                    {
                        "cpr": barn["cpr"],
                        "navn": nexus_borger["fullName"],
                        "aktiv": True,
                        "sidst_set": datetime.now(ZoneInfo("Europe/Copenhagen")),
                        "sagsbehandler": [sagsbehandler],
                    }
                )
            except Exception:
                continue

        return nexus_borgere

    def _find_sagsbehandler(
        self, indsats_referencer: List[dict[str, Any]], forløb
    ) -> dict | None:
        """Finder sagsbehandler for en given borger baseret på indsats referencer"""
        # Check forløb med aktiv indsats for sagsbehandler
        sagsbehandler = filter_by_path(
            indsats_referencer,
            path_pattern=f"/Børn og Unge Grundforløb/{forløb}/professionalReference",
            active_pathways_only=True,
        )

        if len(sagsbehandler) == 0:
            # Check grundforløb for sagsbehandler
            sagsbehandler = filter_by_path(
                indsats_referencer,
                path_pattern="/Børn og Unge Grundforløb/professionalReference",
                active_pathways_only=True,
            )

            if len(sagsbehandler) == 0:
                return None

        # Resolve sagsbehandler, objekt i pathway har ingen kontakt information, dvs. vi resolver hele medarbejderen.
        sagsbehandler = self.hent_fra_reference(sagsbehandler[0])
        sagsbehandler = self.database.hent_medarbejder_med_activity_id(
            sagsbehandler.get("activityIdentifier", {}).get("activityId", "")
        )
        sagsbehandler = self.organisationer.hent_medarbejder_ved_initialer(
            sagsbehandler[0].get("primary_identifier", "")
        )

        if sagsbehandler is None:
            return None

        return {
            "initialer": sagsbehandler["initials"],
            "navn": sagsbehandler.get("fullName", ""),
            "email": f"{sagsbehandler['initials']}@odense.dk",
            "telefon": f"{sagsbehandler.get('mobile', '')}",
        }

    def _er_i_sbf_kandidat_forløb(
        self, indsats_referencer: List[dict[str, Any]], borger: dict
    ) -> str | None:
        """Tjekker om borger er kandidat til SBF baseret på referencer og borger data"""
        for forløb in nexus_forløb:
            filtrerede_indsats_referencer = filter_by_path(
                indsats_referencer,
                path_pattern=f"/Børn og Unge Grundforløb/{forløb}/Indsatser/basketGrantReference",
                active_pathways_only=True,
            )

            if len(filtrerede_indsats_referencer) > 0:
                aktive_indsatser = self.indsatser.filtrer_indsats_referencer(
                    indsats_referencer=filtrerede_indsats_referencer,
                    kun_aktive=True,
                    inkluder_indsatspakker=False,
                )

                if len(aktive_indsatser) > 0:
                    return forløb

        return None


nexus: Optional[Nexus] = None


def init_nexus(credentials: Credential, db_credentials: Credential) -> None:
    global nexus
    nexus = Nexus(
        instance=credentials.data["instance"],
        client_id=credentials.username,
        client_secret=credentials.password,
        db_host=db_credentials.data["hostname"],
        db_port=db_credentials.data["port"],
        db_user=db_credentials.username,
        db_password=db_credentials.password,
        db_database=db_credentials.data["database_name"],
    )


def get_nexus() -> Nexus:
    if nexus is None:
        raise ValueError("Nexus client is not initialized. Call init_nexus() first.")
    return nexus
