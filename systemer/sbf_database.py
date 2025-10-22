from typing import Optional
from sbf_database import SBFManager as SBFDatabaseManager, BarnSynkronisering, SynkroniseringsStatus


class SBFManager(SBFDatabaseManager):
    def __init__(self, database_url: str):
        super().__init__(database_url)
    
    def synkroniser_borgere_i_database(self, sbf_kandidater: list[BarnSynkronisering]) -> None:
        """Synkroniser en liste af SBF kandidater til databasen"""
        for barn in sbf_kandidater:
            eksisterende_barn = self.hent_efter_cpr(
                barn_cpr=str(barn.barn_cpr), 
                barn_foraelder_cpr=str(barn.barn_foraelder_cpr)
            )
            if eksisterende_barn is None:
                eksisterende_barn = self.gem(barn)            
            
            eksisterende_barn.barn_cpr = barn.barn_cpr
            eksisterende_barn.barn_foraelder_cpr = barn.barn_foraelder_cpr
            eksisterende_barn.barn_sidst_set = barn.barn_sidst_set        
            eksisterende_barn.barn_sagsbehandler_information = barn.barn_sagsbehandler_information        

            self.gem(eksisterende_barn)

    def kontroller_sbf_til_inaktivering(self) -> None:
        """Marker gamle SBF rækker til sletning"""
        sbf_rækker = self.hent_aeldre_end(14)

        for række in sbf_rækker:
            række.status = SynkroniseringsStatus.SKAL_SLETTES
            self.gem(række)


# Global instance
sbf_database: Optional[SBFManager] = None


def init_sbf_database(database_url: str) -> None:
    """Initialize the global SBF database instance"""
    global sbf_database
    sbf_database = SBFManager(database_url)


def get_sbf_database() -> SBFManager:
    """Get the global SBF database instance"""
    if sbf_database is None:
        raise Exception("SBF Database er ikke initialiseret")
    return sbf_database