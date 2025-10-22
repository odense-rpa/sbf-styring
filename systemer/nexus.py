from typing import Optional
from datetime import datetime
from kmd_nexus_client import NexusClientManager,utils
from kmd_nexus_client.tree_helpers import filter_by_path
from nexus_database_client import NexusDatabaseClient
from automation_server_client import Credential
from sbf_database import BarnSynkronisering

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
    "Udfører - Æresrelaterede konflikter"
]


class Nexus(NexusClientManager):

    def __init__(self, instance, client_id, client_secret,db_host,db_port,db_user,db_password,db_database):
        super().__init__(instance, client_id, client_secret)
        self.database = NexusDatabaseClient(
            host = db_host,
            port = db_port,
            user = db_user,
            password = db_password,
            database = db_database)


    def hent_nexus_borgere(self) -> list[BarnSynkronisering]:
        nexus_borgere = []
        nexus_borgere_ufiltreret = self.database.hent_borgere_til_sammenhængende_borgerforløb()

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
                            inkluder_indsatspakker=False
                        )

                        if len(aktive_indsatser) > 0:
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
                                    break

                            # Resolve sagsbehandler, objekt i pathway har ingen kontakt information, dvs. vi resolver hele medarbejderen.
                            sagsbehandler = self.hent_fra_reference(sagsbehandler[0])
                            sagsbehandler = self.database.hent_medarbejder_med_activity_id(sagsbehandler.get("activityIdentifier", {}).get("activityId", ""))
                            sagsbehandler = self.organisationer.hent_medarbejder_ved_initialer(sagsbehandler[0].get("primary_identifier", ""))

                            if sagsbehandler is None:
                                break

                            sagsbehandler_information = { 
                                "nexus": {
                                    "initialer": sagsbehandler['initials'],
                                    "navn": sagsbehandler.get("fullName", ""),
                                    "email": f"{sagsbehandler['initials']}@odense.dk",
                                    "telefon": f"{sagsbehandler.get('mobile', '')}"
                                },
                                "dubu": {
                                }
                            }

                            barn_model = BarnSynkronisering(
                                barn_cpr=barn["cpr"],
                                barn_foraelder_cpr="",
                                barn_sidst_set=datetime.now(),                            
                                barn_sagsbehandler_information = sagsbehandler_information,                            
                            )
                            
                            nexus_borgere.append(barn_model)
            except Exception:
                continue            

        return nexus_borgere


nexus: Optional[Nexus] = None

def init_nexus(credentials: Credential, db_credentials: Credential) -> None:
    global nexus
    nexus = Nexus(
        instance=credentials.data["instance"],
        client_id=credentials.username,
        client_secret=credentials.password,
        db_host = db_credentials.data["hostname"],
        db_port = db_credentials.data["port"],
        db_user = db_credentials.username,
        db_password = db_credentials.password,
        db_database = db_credentials.data["database_name"],
    )

def get_nexus() -> Nexus:
    if nexus is None:
        raise ValueError("Nexus client is not initialized. Call init_nexus() first.")
    return nexus