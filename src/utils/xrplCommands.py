from xrpl.asyncio.clients import AsyncWebsocketClient
from xrpl.wallet import Wallet
from xrpl.asyncio.account import get_balance
from xrpl.asyncio.transaction import submit_and_wait, autofill
from xrpl.models.transactions import Payment, Memo
from xrpl.utils import xrp_to_drops
from xrpl.models.requests.account_lines import AccountLines
from asyncio import sleep
from asyncio.exceptions import TimeoutError, CancelledError
from configparser import ConfigParser

from requests import Session
from utils.logging import loggingInstance


class XRPClient:
    def __init__(self, config: ConfigParser | None) -> None:
        # Parse the configuration
        self.config = config
        # Set an initial test mode based on the configuration
        self.setTestMode(self.config.getboolean("test_mode"))

        # Save the last coin checked and its issuer to prevent frequent checking of issuer on the same coin
        self.lastCoinChecked = ""
        self.lastCoinIssuer = ""

        # Verbosity for debugging purposes
        self.verbose = self.config.getboolean("verbose")

    async def sendCoin(
        self, address: str, value: float, coinHex: str = "XRP", memos: str | None = None
    ) -> dict:
        # Prepare the result format
        funcResult = {"result": False, "error": None}

        # if memos are given, properly format it.
        if memos:
            memoData = memos.encode("utf-8").hex()

        loggingInstance.debug("Preparing payment package...")
        try:
            if coinHex.upper() == "XRP":
                # Use xrp_to_drops if the currency is XRP
                amount_drops = xrp_to_drops(float(value))
                payment = Payment(
                    account=self.wallet.classic_address,
                    destination=address,
                    amount=amount_drops,
                    memos=[Memo(memo_data=memoData)] if memos else None,
                )
            else:

                loggingInstance.debug("Checking for trustline...")
                # Get the coin issuer from the trustline that is set on the sender's account
                coinIssuer = self.config.get("coin_issuer")

                # If the issuer is not available on the sender, return
                if coinIssuer is None:
                    funcResult["error"] = "TrustlineNotSetOnSender"
                    funcResult["result"] = False
                    return funcResult

                loggingInstance.debug("Trustline found!...")

                # Prepare the payment transaction format along with the given fields
                payment = Payment(
                    account=self.wallet.classic_address,
                    destination=address,
                    amount={
                        "currency": coinHex,
                        "value": str(value),  # Ensure amount is a string
                        "issuer": coinIssuer,
                    },
                    memos=[Memo(memo_data=memoData)] if memos else None,
                )

            # Retry logic should there be a network problem
            retries = 3
            for attempt in range(retries):
                loggingInstance.debug(
                    f"Attempt #{attempt+1} in sending {value} {coinHex} to {address}"
                )
                try:
                    async with AsyncWebsocketClient(self.xrpLink) as client:
                        loggingInstance.debug(
                            f"Submitting payment transaction: {payment.to_dict()}"
                        )

                        autofilledTx = await autofill(
                            transaction=payment, client=client
                        )

                        loggingInstance.debug(
                            f"Autofilled transaction: {autofilledTx.to_dict()}"
                        )

                        # Ensure no unsupported fields are present
                        if "full" in autofilledTx.to_dict().keys():
                            loggingInstance.error(
                                "Found unsupported field 'full' in autofilled transaction"
                            )
                            autofilledTx.to_dict().pop("full")

                        # Autofill, submit, and wait for the transaction to be validated
                        result = await submit_and_wait(
                            transaction=autofilledTx,
                            client=client,
                            wallet=self.wallet,
                            autofill=False,
                        )

                        loggingInstance.debug(f"Transaction result: {result.result}")

                    if result.is_successful():
                        loggingInstance.info("Transaction successful")
                        funcResult["result"] = True
                        return funcResult
                    else:
                        raise Exception(result.result)
                except (TimeoutError, CancelledError, ConnectionError, OSError) as e:
                    loggingInstance.warning(
                        f"Connection error on attempt {attempt + 1}: {e}. Retrying..."
                    )
                    if attempt < retries - 1:
                        await sleep(5)  # Wait before retrying
                    else:
                        loggingInstance.error(
                            f"Failed to send transaction after {retries} attempts"
                        )
                        funcResult["result"] = False
                        funcResult["error"] = (
                            f"Connection timeout after {retries} retries"
                        )
                        return funcResult
                except Exception as e:
                    loggingInstance.error(f"Exception in transaction submission: {e}")

                    if "noCurrent" in str(e) or "overloaded" in str(e):
                        loggingInstance.warning(
                            f"Attempt {attempt + 1} failed: {e}. Retrying..."
                        )
                        if attempt < retries - 1:
                            await sleep(5)  # Wait before retrying
                        else:
                            funcResult["result"] = False
                            funcResult["error"] = str(e)
                            return funcResult
                    else:
                        raise e

            # If we've exhausted all retries without success
            funcResult["result"] = False
            funcResult["error"] = "Failed after all retry attempts"
            return funcResult

        except Exception as e:
            loggingInstance.exception(
                f"Error processing {value} {coinHex} for {address}: {str(e) or 'No error message'}"
            )
            funcResult["result"] = False
            funcResult["error"] = e
            return funcResult

    async def checkBalance(self):
        async with AsyncWebsocketClient(self.xrpLink) as client:
            return await get_balance(self.wallet.address, client)

    def setTestMode(self, mode=True) -> None:
        if mode:
            self.xrpLink = self.config["testnet_link"]
        else:
            self.xrpLink = self.config["mainnet_link"]

    async def registerSeed(self, seed) -> dict:
        try:
            loggingInstance.debug("Registering Wallet...")
            self.wallet = Wallet.from_seed(seed)
            loggingInstance.info("Wallet registered successfully")
            return {"result": True, "error": "success"}
        except Exception as e:
            loggingInstance.exception("Error in wallet registration")
            return {"result": False, "error": e}

    def getTestMode(self) -> bool:
        return self.xrpLink == self.config["testnet_link"]

    async def getAccountBalance(self, xrpId, token):
        session = Session()
        request = session.get(f"https://api.xrpscan.com/api/v1/account/{xrpId}/assets")
        if request.ok:
            for asset in request.json():
                if asset["currency"] == token:
                    return float(asset["value"])

        return False
