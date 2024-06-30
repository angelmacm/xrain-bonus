from xrpl.asyncio.clients import AsyncWebsocketClient
from xrpl.wallet import Wallet
from xrpl.asyncio.account import get_balance
from xrpl.asyncio.transaction import autofill_and_sign, submit_and_wait
from xrpl.models.transactions import Payment, Memo
from xrpl.models.amounts import IssuedCurrencyAmount
from xrpl.utils import xrp_to_drops
from xrpl.models.requests.account_lines import AccountLines
from xrpl.models.requests import RipplePathFind
from asyncio import sleep
from configparser import ConfigParser

class XRPClient:
    def __init__(self, config: ConfigParser | None) -> None:
        # Parse the configuration
        self.config = config
        # Set an initial test mode based on the configuration
        self.setTestMode(self.config.getboolean('test_mode'))
        
        # Save the last coin checked and its issuer to prevent frequent checking of issuer on the same coin
        self.lastCoinChecked = ""
        self.lastCoinIssuer = ""
        
        # Verbosity for debugging purposes
        self.verbose = self.config.getboolean('verbose')

    async def sendCoin(self, address: str, value: float, coinHex: str = "XRP", memos: str | None = None) -> dict:
        # Prepare the result format
        funcResult = {'result': False, 'error': None}
        
        # if memos are given, properly format it.
        if memos:
            memoData = memos.encode('utf-8').hex()
        
        print("[XRPL]   Preparing payment package...") if self.verbose else None # For debugging purposes
        try:
            if coinHex.upper() == "XRP":
                # Use xrp_to_drops if the currency is XRP
                amount_drops = xrp_to_drops(float(value))
                payment = Payment(
                    account=self.wallet.classic_address,
                    destination=address,
                    amount=amount_drops,
                    memos= [Memo(memo_data=memoData)] if memos else None
                )
            else:
                # Get the coin issuer from the trustline that is set on the sender's account
                coinIssuer = await self.getCoinIssuer(coinHex)
                
                # If the issuer is not available on the sender, return
                if coinIssuer is None:
                    funcResult["error"] = "TrustlineNotSetOnSender"
                    funcResult["result"] = False
                    return funcResult
                
                # Prepare the payment transaction format along with the given fields
                payment = Payment(
                    account=self.wallet.classic_address,
                    destination=address,
                    amount={
                        "currency": coinHex,
                        "value": str(value),  # Ensure amount is a string
                        "issuer": coinIssuer
                    },
                    memos= [Memo(memo_data=memoData)] if memos else None
                )
            
            # Retry logic should there be a network problem
            retries = 3
            for attempt in range(retries):
                print(f"[XRPL]   Attempt #{attempt+1} in sending {value} {coinHex} to {address}") if self.verbose else None # For debugging purposes
                try:
                    async with AsyncWebsocketClient(self.xrpLink) as client:
                        # Sign the transaction
                        signed_tx = await autofill_and_sign(transaction=payment, wallet=self.wallet, client=client)
                        
                        # Submit the signed transaction to be validated
                        result = await submit_and_wait(transaction=signed_tx, client=client)
                    
                    if result.is_successful():
                        print("[XRPL]   Success")  if self.verbose else None # For debugging purposes
                        funcResult["result"] = True
                        return funcResult
                    else:
                        raise Exception(result.result)
                except Exception as e:
                    
                    if "noCurrent" in str(e) or "overloaded" in str(e):
                        print(f"[XRPL]   Attempt {attempt + 1} failed: {e}. Retrying...") if self.verbose else None # For debugging purposes
                        await sleep(5)  # Wait before retrying
                    else:
                        raise e
            return False
        
        except Exception as e:
            print(f"[XRPL]   Error processing {value} {coinHex} for {address}: {str(e)}") if self.verbose else None # For debugging purposes
            funcResult['result'] = False
            funcResult['error'] = e
            return funcResult
    
    async def getCoinIssuer(self, currency: str) -> str | None:
        
        # To prevent multiple request of the same coin, return the last value
        if currency == self.lastCoinChecked:
            return self.lastCoinIssuer
        
        try:
            # Prepare the Account Request Transaction
            account_lines = AccountLines(
                account=self.wallet.classic_address,
                ledger_index="validated"
            )
            
            # Request the transaction
            async with AsyncWebsocketClient(self.xrpLink) as client:
                response = await client.request(account_lines)

            # Check if the proper key is found in the response
            if "lines" not in response.result.keys():
                return
            
            # Iterate on all the trustlines until the coin is matched. Return the account the trustline is set to.
            lines = response.result["lines"]
            for line in lines:
                
                if line["currency"] == currency:
                    self.lastCoinIssuer = line["account"]
                    return self.lastCoinIssuer
            return
        except Exception as e:
            print(f"[XRPL]   Error checking trust line for {self.wallet.classic_address}: {str(e)}")
            return 
        
    async def checkBalance(self):
        async with AsyncWebsocketClient(self.xrpLink) as client:
            return await get_balance(self.wallet.address, client)
    
    def setTestMode(self, mode = True) -> None:
        if mode:
            self.xrpLink = self.config["testnet_link"]
        else:
            self.xrpLink = self.config["mainnet_link"]
        
    async def registerSeed(self, seed) -> dict:
        try:
            print("[XRPL]   Registering Wallet...") if self.verbose else None # For debugging purposes
            self.wallet = Wallet.from_seed(seed)
            print("[XRPL]   Registering Success!") if self.verbose else None # For debugging purposes
            return {"result":True, "error": "success"}
        except Exception as e:
            print(f"[XRPL]   Error in wallet registration") if self.verbose else None # For debugging purposes
            return {"result":False, "error":e}
    
    def getTestMode(self) -> bool:
        return self.xrpLink == self.config["testnet_link"]