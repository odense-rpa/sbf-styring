import asyncio
import logging
import os

from automation_server_client import AutomationServer, Credential
from odk_tools.tracking import Tracker
from odk_tools.reporting import Reporter
from systemer import (
    init_dubu, get_dubu, init_nexus, get_nexus, init_momentum, get_momentum, 
    init_datafordeler, init_sbf_database, get_sbf_database
)

reporter: Reporter
tracker: Tracker
proces_navn = "SBF Styring"


async def synkroniser_sbf():
    dubu = get_dubu()
    nexus = get_nexus()
    momentum = get_momentum()
    sbf_database = get_sbf_database()
    
    # Synkroniser sbf
    dubu_borgere = dubu.hent_dubu_borgere()
    nexus_borgere = nexus.hent_nexus_borgere()
    borgere = sorted(dubu_borgere + nexus_borgere, key=lambda x: x.barn_cpr)
    sbf_kandidater = momentum.filtrer_sbf_kandidater(borgere)
    sbf_database.synkroniser_borgere_i_database(sbf_kandidater)

    # Sæt status til SKAL_SLETTES for rækker hvor barn- eller foraelder_sidst_set er ældre end 14 dage
    sbf_database.kontroller_sbf_til_inaktivering()    

    # Sæt status på rows der er slettet i alle tre systemer, til Status.SLETTET
    sbf_database.opdater_slettet_status()

    # Slet rækker som har haft status slettet i 60 dage.
    sbf_database.fjern_forældede(60)
    
    # Hent alle rækker med status SYNC eller SKAL_SLETTES og opret workitem i SBF-fagsystemers work queues
    sbf_database.opret_kø_items()

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO        
    )

    ats = AutomationServer.from_environment()
    workqueue = ats.workqueue()

    nexus_credential = Credential.get_credential("KMD Nexus - produktion")
    nexus_database_credential = Credential.get_credential("KMD Nexus - database")
    momentum_credential = Credential.get_credential("Momentum - produktion")
    user_credential = Credential.get_credential("RoboA")
    tracking_credential = Credential.get_credential("Odense SQL Server")

    certifikat_sti = os.getenv("CERTIFIKATER", "/certifikater")

    init_dubu(user_credential)
    init_nexus(nexus_credential, nexus_database_credential)
    init_momentum(momentum_credential)
    init_datafordeler(
        certifikat_sti=os.path.join(certifikat_sti, "datafordeler.crt"),
        certifikat_nøglefil=os.path.join(certifikat_sti, "datafordeler.key")
    )
    init_sbf_database(
        database_url=os.getenv("DB_CONNECTION", "pgsql://postgres:postgres@localhost:5432/sbf")
    )

    reporter = Reporter(
        username=user_credential.username,
        password=user_credential.password
    )
    tracker = Tracker(
        username=tracking_credential.username, 
        password=tracking_credential.password
    )
    
    logger = logging.getLogger(__name__)

    # Process workqueue
    asyncio.run(synkroniser_sbf())
    