from datetime import datetime
import sys
import asyncio
import logging
import os

from automation_server_client import AutomationServer, Workqueue, Credential, WorkItemStatus, WorkItemError
from kmd_nexus_client import NexusClientManager
from nexus_database_client import NexusDatabaseClient
from kmd_nexus_client.tree_helpers import (
    filter_by_path 
)
from dubu_client import DubuClientManager
from momentum_client.manager import MomentumClientManager
from odk_tools.tracking import Tracker
from odk_tools.reporting import Reporter
from datafordeler import Datafordeler
from sbf_database import SBFManager, BarnSynkronisering

datafordeler: Datafordeler
dubu: DubuClientManager
momentum: MomentumClientManager
nexus: NexusClientManager
nexus_database_client: NexusDatabaseClient
reporter: Reporter
sbf_database: SBFManager
tracker: Tracker


proces_navn = "SBF Styring"

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

# TODO: Duplicate børn cpr mellem begge systemer, what do?

async def populate_queue(workqueue: Workqueue):
    dubu_borgere = hent_dubu_borgere()
    nexus_borgere = hent_nexus_borgere()
    #sbf_kandidater = filtrer_sbf_kandidater(dubu_borgere, nexus_borgere)

def hent_dubu_borgere() -> list[BarnSynkronisering]:
    dubu_borgere: list[BarnSynkronisering] = []
    dubu_borgere_ufiltreret = dubu.sager.soeg_sager_sammenhaengende_borger_forloeb()

    for person in dubu_borgere_ufiltreret["value"]:
        if person.get("primaerPerson") is not None and person.get("primaerPerson", {}).get("cprnr") is not None:
            sagsbehandler = dubu.brugere.hent_org_bruger(person.get("primaerBehandler", {}).get("orgBrugerId", -1))

            if sagsbehandler is None:                
                continue            

            barn = BarnSynkronisering(
                barn_cpr=person["primaerPerson"]["cprnr"],
                barn_foraelder_cpr="",
                barn_sidst_set=datetime.now(),
                barn_sagsbehandler_initialer=sagsbehandler.get("adresse", {}).get("emailAdresse", "").split("@")[0],
                barn_sagsbehandler_information= f"{sagsbehandler.get('fuldeNavn', '')}, {sagsbehandler.get('adresse', {}).get('emailAdresse', '')}, {sagsbehandler.get('adresse', {}).get('mobiltelefon', '')}",
                nexus_sidst_synkroniseret=datetime.now()
                # nexus_slettet=False,
                # momentum_sidst_synkroniseret=datetime(1, 1, 1, 0, 0, 0),
                # momentum_slettet=False,
                # momentum_nuvaerende_kontaktpersoner=None,
                # dubu_sidst_synkroniseret=datetime(1, 1, 1, 0, 0, 0),
                # dubu_slettet=False,
                # status=SynkroniseringsStatus.SYNC
                                                      
            )
            dubu_borgere.append(barn)
    
    return sorted(dubu_borgere, key=lambda x: x.barn_cpr)

def hent_nexus_borgere() -> list[BarnSynkronisering]:
    nexus_borgere = []
    nexus_borgere_ufiltreret = nexus_database_client.hent_borgere_til_sammenhængende_borgerforløb()    

    for barn in nexus_borgere_ufiltreret:
        try:
            nexus_borger = nexus.borgere.hent_borger(barn["cpr"])
        except ValueError:
            # Suppress invalid cpr-numbers
            continue

        if not nexus_borger:
            continue

        pathway = nexus.borgere.hent_visning(borger=nexus_borger)

        if pathway is None:
            continue

        indsats_referencer = nexus.borgere.hent_referencer(visning=pathway)            

        for forløb in nexus_forløb:
            filtrerede_indsats_referencer = filter_by_path(
                indsats_referencer,
                path_pattern=f"/Børn og Unge Grundforløb/{forløb}/Indsatser/basketGrantReference",
                active_pathways_only=True,
            )

            if len(filtrerede_indsats_referencer) > 0:
                aktive_indsatser = nexus.indsatser.filtrer_indsats_referencer(
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
                    sagsbehandler = nexus.hent_fra_reference(sagsbehandler[0])
                    sagsbehandler = nexus_database_client.hent_medarbejder_med_activity_id(sagsbehandler.get("activityIdentifier", {}).get("activityId", ""))
                    sagsbehandler = nexus.organisationer.hent_medarbejder_ved_initialer(sagsbehandler[0].get("primary_identifier", ""))

                    if sagsbehandler is None:
                        break

                    barn = BarnSynkronisering(
                        barn_cpr=barn["cpr"],
                        barn_foraelder_cpr="",
                        barn_sidst_set=datetime.now(),
                        barn_sagsbehandler_initialer=f"{sagsbehandler['initials']}",
                        barn_sagsbehandler_information= f"{sagsbehandler.get('fullName', '')}, {sagsbehandler['initials']}@odense.dk, {sagsbehandler.get('mobile', '')}",
                        #nexus_sidst_synkroniseret=datetime.now()
                        #nexus_slettet=False,
                        # momentum_sidst_synkroniseret=datetime(1, 1, 1, 0, 0, 0),
                        # momentum_slettet=False,
                        # momentum_nuvaerende_kontaktpersoner=None,
                        dubu_sidst_synkroniseret=datetime.now(),
                        # dubu_slettet=False,
                        # status=SynkroniseringsStatus.SYNC                                                            
                    )
                    nexus_borgere.append(barn)

    return sorted(nexus_borgere)



def filtrer_sbf_kandidater(dubu_borgere: list[BarnSynkronisering], nexus_borgere: list[BarnSynkronisering]) -> list[dict]:
    sbf_kandidater = []

    # for cpr in dubu_borgere:
    #     er_der_sbf = kontroller_forældre(cpr)

    #     if er_der_sbf:
    #         sbf_kandidater.append({
    #             "cpr": cpr,
    #             "kilde": "DUBU"
    #             # TODO: Tilføj forældreinfo
    #             # TODO: Tilføj sagsbehandlerinfo Momentum
    #         })

    # for cpr in nexus_borgere:
    #     er_der_sbf = kontroller_forældre(cpr)

    #     if er_der_sbf:
    #         sbf_kandidater.append({
    #             "cpr": cpr,
    #             "kilde": "NEXUS"
    #             # TODO: Tilføj forældreinfo
    #             # TODO: Tilføj sagsbehandlerinfo Momentum
    #         })

    return sbf_kandidater

def kontroller_forældre(cpr: str) -> bool:
    # Implement the logic to check if the parent is valid
    # Kald Datafordeler for forældremyndigheder
    # For hver forælder, hvis i live, kald Momentum

    return True

async def process_workqueue(workqueue: Workqueue):
    logger = logging.getLogger(__name__)
    logger.info("Hello from process workqueue!")

    for item in workqueue:
        with item:
            data = item.data  # Item data deserialized from json as dict
 
            try:
                # Process the item here
                pass
            except WorkItemError as e:
                # A WorkItemError represents a soft error that indicates the item should be passed to manual processing or a business logic fault
                logger.error(f"Error processing item: {data}. Error: {e}")
                item.fail(str(e))


    logging.basicConfig(
        level=logging.INFO        
    )
    
if __name__ == "__main__":
    ats = AutomationServer.from_environment()
    workqueue = ats.workqueue()

    certifikat_sti = os.getenv("CERTIFIKATER", "/certifikater")

    nexus_credential = Credential.get_credential("KMD Nexus - produktion")
    nexus_database_credential = Credential.get_credential("KMD Nexus - database")
    momentum_credential = Credential.get_credential("Momentum - produktion")
    user_credential = Credential.get_credential("RoboA")
    tracking_credential = Credential.get_credential("Odense SQL Server")

    datafordeler = Datafordeler(
        certifikat_sti=os.path.join(certifikat_sti, "datafordeler.crt"),
        certifikat_nøglefil=os.path.join(certifikat_sti, "datafordeler.key")
    )

    dubu = DubuClientManager(
        username=f"{user_credential.username}@odense.dk",
        password=user_credential.password,
        idp=user_credential.data["idp"]
    )

    momentum = MomentumClientManager(
        base_url=momentum_credential.data["base_url"],
        client_id=momentum_credential.username,
        client_secret=momentum_credential.password,
        api_key=momentum_credential.data["api_key"],
        resource=momentum_credential.data["resource"],
    )
    
    nexus = NexusClientManager(
        client_id=nexus_credential.username,
        client_secret=nexus_credential.password,
        instance=nexus_credential.data["instance"],
    )

    nexus_database_client = NexusDatabaseClient(
        host = nexus_database_credential.data["hostname"],
        port = nexus_database_credential.data["port"],
        user = nexus_database_credential.username,
        password = nexus_database_credential.password,
        database = nexus_database_credential.data["database_name"],
    )

    reporter = Reporter(
        username=user_credential.username,
        password=user_credential.password
    )

    #sbf_manager = SBFManager(
    #    database_url=os.getenv("DB_CONNECTION", "")
    #)
    
    tracker = Tracker(
        username=tracking_credential.username, 
        password=tracking_credential.password
    )
    
    logger = logging.getLogger(__name__)

    # Queue management
    if "--queue" in sys.argv:
        workqueue.clear_workqueue(WorkItemStatus.NEW)
        asyncio.run(populate_queue(workqueue))
        exit(0)

    # Process workqueue
    asyncio.run(process_workqueue(workqueue))
    