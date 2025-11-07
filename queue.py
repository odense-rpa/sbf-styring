from sbf_database import Barn
from automation_server_client import Workqueue

async def populate_queue_børn(børn: list[Barn]) -> None:
    """Hent alle børn med sammenhængende borgerforløb fra Dubu."""

    queue = Workqueue.get_workqueue(19)

    for barn in børn:
        queue.add_item({"cpr": barn.cpr,
                        "navn": barn.navn,
                        "sidst_set": barn.sidst_set,
                        "forældre": [{
                            "cpr": x.cpr,
                            "navn": x.navn,
                            "sidst_set": x.sidst_set,
                            "sagsbehandler": x.sagsbehandler
                        } for x in barn.forældre]
                        }, reference=barn.cpr)