import asyncio
import logging
import os

from automation_server_client import AutomationServer, Credential
from odk_tools.tracking import Tracker
from odk_tools.reporting import Reporter
from systemer import (
    init_dubu,
    get_dubu,
    init_nexus,
    get_nexus,
    init_momentum,
    get_momentum,
    init_datafordeler,
    # , init_sbf_database, get_sbf_database
)

from sbf_database import get_sbf_repository

reporter: Reporter
tracker: Tracker
proces_navn = "SBF Styring"


async def synkroniser_sbf():
    dubu = get_dubu()
    nexus = get_nexus()
    momentum = get_momentum()
    # sbf_database = get_sbf_database()

    repository = get_sbf_repository(
        os.getenv("DB_CONNECTION", "pgsql://postgres:postgres@localhost:5432/sbf"), True
    )

    # Hent børn fra systemer

    nexus_børn = nexus.hent_nexus_borgere()
    if len(nexus_børn) == 0:
        raise Exception("Ingen nexus borgere fundet")

    dubu_børn = dubu.hent_dubu_borgere()
    if len(dubu_børn) == 0:
        raise Exception("Ingen dubu borgere fundet")

    # Nustil børn
    børn = repository.hent_alle_børn()
    for barn in børn:
        repository.opdater_barn(barn.cpr, {"aktiv": False})

    # Set aktive børn
    børn = dubu_børn + nexus_børn

    merged = {}
    for item in børn:
        cpr = item["cpr"]
        if cpr not in merged:
            # Keep all fields except sagsbehandler
            merged[cpr] = {k: v for k, v in item.items() if k != "sagsbehandler"}
            merged[cpr]["sagsbehandler"] = []
        merged[cpr]["sagsbehandler"].extend(item["sagsbehandler"])

    børn = list(merged.values())

    for barn in børn:
        db_barn = repository.hent_barn(barn["cpr"])
        if db_barn is None:
            db_barn = repository.opret_barn(barn)
        else:
            repository.opdater_barn(
                barn["cpr"],
                {
                    "aktiv": True,
                    "sidst_set": barn["sidst_set"],
                    "sagsbehandler": barn["sagsbehandler"],
                },
            )

    # Hent sbf kandidater fra momentum baseret på aktive børn
    børn = repository.hent_alle_børn()
    børn = [barn for barn in børn if barn.aktiv]

    voksne = momentum.hent_sbf_kandidater(børn)
    if len(voksne) == 0:
        raise Exception("Ingen momentum forældre fundet")

    # Nulstil alle forældre
    alle_voksne = repository.hent_alle_forældre()
    for voksen in alle_voksne:
        repository.opdater_foraelder(voksen.cpr, {"aktiv": False})

    # Tilknyt og opret aktive forældre.
    for voksen in voksne:
        db_voksen = repository.hent_foraelder(voksen["cpr"])
        if db_voksen is None:
            db_voksen = repository.opret_foraelder({
                "cpr": voksen["cpr"],
                "navn": voksen["navn"],
                "aktiv": True,
                "sidst_set": voksen["sidst_set"],
                "sagsbehandler": voksen["sagsbehandler"],
            })
        else:
            repository.opdater_foraelder(
                voksen["cpr"],
                {
                    "aktiv": True,
                    "navn": voksen["navn"],
                    "sidst_set": voksen["sidst_set"],
                    "sagsbehandler": voksen["sagsbehandler"],
                },
            )
        repository.tilknyt_foraelder_til_barn(voksen["barn"], voksen["cpr"])

    # Slet gamle SBF sæt
    slettet = repository.slet_inaktive()
    logging.info(f"Slettet {slettet} inaktive SBF sæt")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

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
        certifikat_nøglefil=os.path.join(certifikat_sti, "datafordeler.key"),
    )
    # init_sbf_database(
    #    database_url=os.getenv("DB_CONNECTION", "pgsql://postgres:postgres@localhost:5432/sbf")
    # )

    reporter = Reporter(
        username=user_credential.username, password=user_credential.password
    )
    tracker = Tracker(
        username=tracking_credential.username, password=tracking_credential.password
    )

    logger = logging.getLogger(__name__)

    # Process workqueue
    asyncio.run(synkroniser_sbf())
