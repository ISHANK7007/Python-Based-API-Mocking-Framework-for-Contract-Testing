from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from contract.contract_entry import ContractEntry

def register_routes(app: FastAPI, contracts: list[ContractEntry], use_trie: bool = False, strict: bool = False):
    """
    Registers routes on the FastAPI app from the list of contracts.
    """
    for contract in contracts:
        method = contract.method.lower()
        path = contract.path

        async def handler(request: Request, contract=contract):
            return JSONResponse(status_code=contract.response_stub.status_code, content=contract.response_stub.body)

        app.add_api_route(path, handler, methods=[method.upper()])
