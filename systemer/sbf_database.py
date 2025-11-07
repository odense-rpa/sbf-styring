from typing import Optional
#from sbf_database import SBFManager as SBFDatabaseManager, BarnSynkronisering, SynkroniseringsStatus
from automation_server_client import Workqueue


# class SBFManager(SBFDatabaseManager):
#     def __init__(self, database_url: str):
#         super().__init__(database_url)
    
#     def synkroniser_borgere_i_database(self, sbf_kandidater: list[BarnSynkronisering]) -> None:
#         """Synkroniser en liste af SBF kandidater til databasen"""
#         for barn in sbf_kandidater:
#             eksisterende_barn = self.hent_efter_cpr(
#                 barn_cpr=str(barn.barn_cpr), 
#                 barn_foraelder_cpr=str(barn.barn_foraelder_cpr)                
#             )
#             if eksisterende_barn is None:
#                 eksisterende_barn = self.gem(barn)            

#             eksisterende_barn.barn_sidst_set = barn.barn_sidst_set        
#             eksisterende_barn.barn_sagsbehandler_information = barn.barn_sagsbehandler_information
#             # Sættes i tilfælde af at en slettet borger skal genaktiveres.
#             eksisterende_barn.dubu_slettet = False
#             eksisterende_barn.momentum_slettet = False
#             eksisterende_barn.nexus_slettet = False
#             eksisterende_barn.status = SynkroniseringsStatus.SYNC

#             self.gem(eksisterende_barn)

#     def kontroller_sbf_til_inaktivering(self) -> None:
#         """Marker gamle SBF rækker til sletning"""
#         sbf_rækker: list[BarnSynkronisering] = self.hent_aeldre_end(14)

#         for række in sbf_rækker:
#             try:
#                 række.status = SynkroniseringsStatus.SKAL_SLETTES
#                 self.gem(række)
#             except Exception:
#                 continue
     
#     def opret_kø_items(self) -> None:
#         """Opret work items i SBF-fagsystemers work queues for rækker med status SYNC eller SKAL_SLETTES"""        
#         sbf_rækker: list[BarnSynkronisering] = self.hent_alle_til_køhåndtering()        
#         self.tilføj_kø_items(sbf_rækker, SynkroniseringsStatus.SKAL_SLETTES)
#         self.tilføj_kø_items(sbf_rækker, SynkroniseringsStatus.SYNC)
        
        

#     def tilføj_kø_items(self, rækker: list[BarnSynkronisering], status: SynkroniseringsStatus) -> None:
#         dubu_workqueue = Workqueue.get_workqueue(20)
#         momentum_workqueue = Workqueue.get_workqueue(21)
#         nexus_workqueue = Workqueue.get_workqueue(19)        

#         """Tilføj work items til kø for de angivne SBF rækker"""        
#         sbf_rækker = [række for række in rækker if række.status == status]

#         børn_set = set([række.barn_cpr for række in sbf_rækker])
#         forældre_set = set([række.barn_foraelder_cpr for række in sbf_rækker])
        
#         for barn_cpr in børn_set:
#             forældre = [
#                 række 
#                 for række in sbf_rækker 
#                 if række.barn_cpr == barn_cpr
#             ]

#             kødata = {
#                 "barn_cpr": barn_cpr,
#                 "status": status.value,
#                 "forældre": [{
#                     "foraelder_cpr": x.barn_foraelder_cpr,
#                     "sagsbehandlere": [y for y in x.foraelder_sagsbehandler_information.values() if y]
#                 } for x in forældre]

#             }

#             nexus_workqueue.add_item(data=kødata, reference=barn_cpr)
#             dubu_workqueue.add_item(data=kødata, reference=barn_cpr)

#         for foraelder_cpr in forældre_set:
#             børn = [
#                 række 
#                 for række in sbf_rækker 
#                 if række.barn_foraelder_cpr == foraelder_cpr
#             ]

#             kødata = {
#                 "foraelder_cpr": foraelder_cpr,
#                 "status": status.value,
#                 "børn": [{
#                     "barn_cpr": x.barn_cpr,
#                     "sagsbehandlere": [
#                         {
#                             **y,
#                             "system": key
#                         }
#                         for key, y in x.barn_sagsbehandler_information.items() if y
#                     ]
#                 } for x in børn]
#             }

#             momentum_workqueue.add_item(data=kødata, reference=foraelder_cpr)

# # Global instance
# sbf_database: Optional[SBFManager] = None


# def init_sbf_database(database_url: str) -> None:
#     """Initialize the global SBF database instance"""
#     global sbf_database
#     sbf_database = SBFManager(database_url)


# def get_sbf_database() -> SBFManager:
#     """Get the global SBF database instance"""
#     if sbf_database is None:
#         raise Exception("SBF Database er ikke initialiseret")
#     return sbf_database