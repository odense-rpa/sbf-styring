import sys
import asyncio
import logging

from automation_server_client import AutomationServer, Workqueue, Credential, WorkItemStatus, WorkItemError
from kmd_nexus_client import NexusClientManager
from nexus_database_client import NexusDatabaseClient
from kmd_nexus_client.tree_helpers import (
    filter_by_path 
)
from dubu_client import DubuClientManager
from odk_tools.tracking import Tracker
from odk_tools.reporting import Reporter

nexus: NexusClientManager
nexus_database_client: NexusDatabaseClient
dubu: DubuClientManager
tracker: Tracker
reporter: Reporter
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

async def populate_queue(workqueue: Workqueue):
    dubu_borgere = hent_dubu_borgere()
    nexus_borgere = hent_nexus_borgere()


def hent_nexus_borgere() -> list[str]:
    nexus_borgere = []
    nexus_borgere_ufiltreret = nexus_database_client.hent_borgere_til_sammenhængende_borgerforløb()    

    for borger in nexus_borgere_ufiltreret:
        try:
            nexus_borger = nexus.borgere.hent_borger(borger["cpr"])
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
                    nexus_borgere.append(borger["cpr"])

    return sorted(nexus_borgere)

def hent_dubu_borgere() -> list[str]:    
    dubu_borgere_ufiltreret = dubu.sager.soeg_sager_sammenhaengende_borger_forloeb()    
    dubu_borgere = [person.get("primaerPerson", {}).get("cprnr", None) for person in dubu_borgere_ufiltreret["value"] 
                    if person.get("primaerPerson") is not None and person.get("primaerPerson", {}).get("cprnr") is not None]

    return sorted(dubu_borgere)


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

    nexus_credential = Credential.get_credential("KMD Nexus - produktion")
    nexus_database_credential = Credential.get_credential("KMD Nexus - database")
    tracking_credential = Credential.get_credential("Odense SQL Server")
    roboa_credential = Credential.get_credential("RoboA")
    
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

    #TODO: Momentum Credentials
    
    dubu = DubuClientManager(
        username=roboa_credential.username,
        password=roboa_credential.password,
        idp=roboa_credential.data["idp"]
    )
    
    tracker = Tracker(
        username=tracking_credential.username, 
        password=tracking_credential.password
    )

    reporter = Reporter(
        username=roboa_credential.username,
        password=roboa_credential.password
    )
    
    logger = logging.getLogger(__name__)

    # Queue management
    if "--queue" in sys.argv:
        workqueue.clear_workqueue(WorkItemStatus.NEW)
        asyncio.run(populate_queue(workqueue))
        exit(0)

    # Process workqueue
    asyncio.run(process_workqueue(workqueue))
    