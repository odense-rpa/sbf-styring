import copy
import sys
import asyncio
import logging
import os

from datetime import datetime
from httpx import HTTPStatusError, ReadTimeout
from automation_server_client import AutomationServer, Workqueue, Credential, WorkItemStatus, WorkItemError
from kmd_nexus_client import utils
from momentum_client.manager import MomentumClientManager
from odk_tools.tracking import Tracker
from odk_tools.reporting import Reporter
from datafordeler import Datafordeler
from sbf_database import SBFManager, BarnSynkronisering
from systemer import init_dubu, get_dubu, init_nexus, get_nexus

datafordeler: Datafordeler
momentum: MomentumClientManager
reporter: Reporter
sbf_database: SBFManager
tracker: Tracker

proces_navn = "SBF Styring"

# TODO: Oprydning af kode i main.py
# TODO: Sletning af SBF kandidater der ikke længere er aktive i et af de tre systemer.

async def populate_queue(workqueue: Workqueue):
    dubu = get_dubu()
    nexus = get_nexus()
    
    dubu_borgere = dubu.hent_dubu_borgere()
    nexus_borgere = nexus.hent_nexus_borgere()

    borgere = sorted(dubu_borgere + nexus_borgere, key=lambda x: x.barn_cpr)
    sbf_kandidater = filtrer_sbf_kandidater(borgere)
    synkroniser_borgere_i_database(sbf_kandidater)
    # TODO: Populate queues
    # TODO: Kontroller for rows til sletning


def filtrer_sbf_kandidater(borgere: list[BarnSynkronisering]) -> list[BarnSynkronisering]:
    sbf_kandidater = []    

    for barn in borgere:
        forældre_myndigheder = hent_forældre_myndigheder(str(barn.barn_cpr))
        for forældre_myndighed in forældre_myndigheder:
            if kontroller_forælder_i_momentum(forældre_myndighed):
                forældre_cpr = forældre_myndighed.get("Foraelderoplysning", {}).get("Foraelder", {}).get("foraelderPersonnummer", "")
                if not utils.is_valid_cpr(forældre_cpr):
                    continue
                # TODO: Hent sagsbehandler information fra momentum og set data

                borger = momentum.borgere.hent_borger(forældre_myndighed.get("Foraelderoplysning", {}).get("Foraelder", {}).get("foraelderPersonnummer", ""))

                if borger is None:
                    continue

                ansvarlig_sagsbehandlere_reference = momentum.borgere.hent_ansvarlige_sagsbehandlere(
                    borger
                )

                ansvarlig_sagsbehandler = ansvarlig_sagsbehandlere_reference[0] if len(ansvarlig_sagsbehandlere_reference) > 0 else None
                
                if ansvarlig_sagsbehandler is None:
                    continue

                ansvarlig_sagsbehandler = momentum.borgere.hent_aktør(ansvarlig_sagsbehandler.get("caseworkerId", ""))

                if ansvarlig_sagsbehandler is None:
                    continue

                sagsbehandler_information = {
                    "momentum": {
                        "initialer": ansvarlig_sagsbehandler.get("email", "")
                        .split("@")[0],
                        "navn": ansvarlig_sagsbehandler.get("displayName", ""),
                        "email": ansvarlig_sagsbehandler.get("email", ""),
                        "telefon": ansvarlig_sagsbehandler.get("phone", {}) #Overvej om phone/mobile er inkonsistent
                    }                    
                }

                barn = copy.deepcopy(barn)
                barn.barn_foraelder_cpr = forældre_cpr
                barn.foraelder_sidst_set = datetime.now()
                barn.foraelder_sagsbehandler_information = sagsbehandler_information
                sbf_kandidater.append(barn)
    
    return sbf_kandidater

def synkroniser_borgere_i_database(sbf_kandidater: list[BarnSynkronisering]):
    for barn in sbf_kandidater:
        eksisterende_barn = sbf_database.hent_efter_cpr(barn_cpr=str(barn.barn_cpr), barn_foraelder_cpr=str(barn.barn_foraelder_cpr))
        if eksisterende_barn is None:
            eksisterende_barn = sbf_database.gem(barn)            
        
        eksisterende_barn.barn_cpr = barn.barn_cpr
        eksisterende_barn.barn_foraelder_cpr = barn.barn_foraelder_cpr
        eksisterende_barn.barn_sidst_set = barn.barn_sidst_set        
        eksisterende_barn.barn_sagsbehandler_information = barn.barn_sagsbehandler_information        

        sbf_database.gem(eksisterende_barn)

def hent_forældre_myndigheder(cpr: str) -> list[dict]:    
    try:
        person_data = datafordeler.hent_personoplysninger(cpr)
    except Exception as e:        
        if isinstance(e, ReadTimeout):
            return []
        raise
    return person_data.get("Person", {}).get("Foraelderoplysninger", [])

def kontroller_forælder_i_momentum(forælder_myndighed: dict) -> bool:
    try:
        forælder = momentum.borgere.hent_borger(forælder_myndighed.get("Foraelderoplysning", {}).get("Foraelder", {}).get("foraelderPersonnummer", ""))
    except HTTPStatusError:
        return False
    
    if not forælder or forælder.get("cprStatusCode", "") == "DØD":
        return False
    if forælder.get("targetGroupCode") is None:
        return False
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

    init_dubu(user_credential)

    momentum = MomentumClientManager(
        base_url=momentum_credential.data["base_url"],
        client_id=momentum_credential.username,
        client_secret=momentum_credential.password,
        api_key=momentum_credential.data["api_key"],
        resource=momentum_credential.data["resource"],
    )
    
    init_nexus(nexus_credential, nexus_database_credential)


    reporter = Reporter(
        username=user_credential.username,
        password=user_credential.password
    )

    sbf_database = SBFManager(
        database_url=os.getenv("DB_CONNECTION", "pgsql://postgres:postgres@localhost:5432/sbf")
    )
    
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
    