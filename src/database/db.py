from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import update
from database.models.rewardstable import RewardsTable
from database.models.nftTraitList import NFTTraitList
from database.models.claimQuotes import ClaimQuotes
from sqlalchemy.sql import func
from datetime import timedelta, datetime, timezone
from sqlalchemy.future import select
from pytz import timezone as tz

from utils.logging import loggingInstance


class XparrotDB:
    def __init__(self, host, dbName, username, password, verbose):

        #                   username          if empty, do not add :, else :password      host   dbName
        sqlLink = f"mysql+aiomysql://{username}{'' if password in ['', None] else f':{password}'}@{host}/{dbName}"
        loggingInstance.info(f"DB Link: {sqlLink}")
        self.dbEngine = create_async_engine(
            sqlLink,
            echo=verbose,
            pool_recycle=600,
            pool_pre_ping=True,
            pool_use_lifo=True,
        )

        self.asyncSessionMaker = async_sessionmaker(
            bind=self.dbEngine, expire_on_commit=False
        )
        self.verbose = verbose

    def check_cooldown(self, result, funcResult):
        if result:
            lastClaim = result[0]
            currentTime = result[1]

            if lastClaim and not lastClaim == "0000-00-00 00:00:00":
                lastClaim = (
                    datetime.strptime(lastClaim, "%Y-%m-%d %H:%M:%S")
                    if type(lastClaim) == str
                    else lastClaim
                )
                nextClaim = lastClaim + timedelta(days=1)

                # Check if the currentTime is past than nextClaim
                if nextClaim > currentTime:

                    # compute the remaining time
                    timeDiff: timedelta = nextClaim - currentTime

                    remainingHour = timeDiff.seconds // 3600 + (timeDiff.days * 24)
                    remainingMin = (timeDiff.seconds // 60) % 60
                    remainingSec = timeDiff.seconds % 60

                    # Ready the return structure
                    funcResult["result"] = "NotReady"
                    funcResult["timeRemaining"]["hour"] = remainingHour
                    funcResult["timeRemaining"]["minute"] = remainingMin
                    funcResult["timeRemaining"]["second"] = remainingSec

                else:
                    funcResult["result"] = "Claimable"
            else:
                funcResult["result"] = "Claimable"
        else:
            funcResult["result"] = "XrpIdNotFound"

        return funcResult

    async def getBonusStatus(self, xrpId: str) -> dict:
        # Return structure
        funcResult = {
            "result": "",
            "timeRemaining": {
                "hour": 0,
                "minute": 0,
                "second": 0,
            },
        }

        async with self.asyncSessionMaker() as session:
            # Query the required columns
            query = select(RewardsTable.dailyBonusFlagDate, func.now()).filter(
                RewardsTable.xrpId == xrpId
            )
            result = await session.execute(query)
            result = result.first()

            loggingInstance.info(f"Query Result: {result}") if self.verbose else None

            # Check if there are results
            # No result would only mean that xrpId is not found
            funcResult = self.check_cooldown(result, funcResult)

            loggingInstance.info(f"getBonusStatus({xrpId}): {funcResult['result']}")

            return funcResult

    async def getBonusAmount(self, xrpId: str) -> dict:
        async with self.asyncSessionMaker() as session:
            funcResult = {
                "result": None,
                "amount": None,
                "nftLink": None,
                "tokenId": None,
                "taxonId": None,
            }
            query = (
                select(
                    NFTTraitList.totalXRAIN,
                    NFTTraitList.nftlink,
                    NFTTraitList.tokenId,
                    NFTTraitList.taxonId,
                )
                .filter(NFTTraitList.xrpId == xrpId, NFTTraitList.nftlink != "")
                .order_by(func.random())
                .limit(1)
            )
            queryResult = await session.execute(query)
            queryResult = queryResult.first()

            (
                loggingInstance.info(f"Query Result: {queryResult}")
                if self.verbose
                else None
            )

            if queryResult:
                xrainValue, nftLink, tokenId, taxonId = queryResult

                if nftLink == "":
                    funcResult["result"] = "ImageLinkNotFound"
                    (
                        loggingInstance.error(
                            f"getBonusAmount({xrpId}): {funcResult['result']}"
                        )
                        if self.verbose
                        else None
                    )
                    return funcResult

                funcResult["result"] = "Success"
                funcResult["nftLink"] = nftLink
                funcResult["amount"] = xrainValue
                funcResult["tokenId"] = tokenId
                funcResult["taxonId"] = taxonId
                (
                    loggingInstance.info(
                        f"getBonusAmount({xrpId}): {funcResult['result']}"
                    )
                    if self.verbose
                    else None
                )
                return funcResult
            else:
                funcResult["result"] = "XrpIdNotFound"
                (
                    loggingInstance.info(
                        f"    getBonusAmount({xrpId}): {funcResult['result']}"
                    )
                    if self.verbose
                    else None
                )
                return funcResult

    async def getBiWeeklyStatus(self, xrpId) -> dict:
        funcResult = {
            "result": "",
            "timeRemaining": {
                "hour": 0,
                "minute": 0,
                "second": 0,
            },
        }

        async with self.asyncSessionMaker() as session:
            query = select(
                RewardsTable.dailyRepFlagDate,
                func.utc_timestamp(),
                RewardsTable.penaltyReputationRewards,
            ).filter(RewardsTable.xrpId == xrpId)
            queryResult = await session.execute(query)
            queryResult = queryResult.first()

            funcResult = self.check_cooldown(queryResult, funcResult)

            if queryResult:
                x, y, funcResult["amount"] = queryResult

            loggingInstance.info(f"getBonusStatus({xrpId}): {funcResult['result']}")

            return funcResult

    async def biweeklySet(self, xrpId) -> None:
        async with self.asyncSessionMaker() as session:
            async with session.begin():
                try:
                    await session.execute(
                        update(RewardsTable)
                        .where(RewardsTable.xrpId == xrpId)
                        .values(dailyRepFlagDate=self.getLastRedemption())
                    )
                    if self.verbose:
                        loggingInstance.info(f"biweeklySet({xrpId}): Success")
                except Exception as e:
                    if self.verbose:
                        loggingInstance.error(f"biweeklySet({xrpId}): {e}")
                    await session.rollback()

    async def bonusSet(self, xrpId) -> None:
        async with self.asyncSessionMaker() as session:
            async with session.begin():
                try:
                    await session.execute(
                        update(RewardsTable)
                        .where(RewardsTable.xrpId == xrpId)
                        .values(dailyBonusFlagDate=func.now())
                    )
                    if self.verbose:
                        loggingInstance.info(f"bonusSet({xrpId}): Success")
                except Exception as e:
                    if self.verbose:
                        loggingInstance.error(f"bonusSet({xrpId}): {e}")
                    await session.rollback()

    async def getRandomNFT(self, xrpId) -> dict:
        async with self.asyncSessionMaker() as session:
            funcResult = {"nftLink": None, "tokenId": None, "taxonId": None}
            query = (
                select(NFTTraitList.nftlink, NFTTraitList.tokenId, NFTTraitList.taxonId)
                .filter(NFTTraitList.xrpId == xrpId, NFTTraitList.nftlink != "")
                .order_by(func.random())
                .limit(1)
            )
            queryResult = await session.execute(query)
            queryResult = queryResult.first()

            (
                loggingInstance.info(f"Query Result: {queryResult}")
                if self.verbose
                else None
            )

            if queryResult:
                nftLink, tokenId, taxonId = queryResult

                if nftLink == "":
                    (
                        loggingInstance.error(f"getRandomNFT({xrpId}): NoNFTFound")
                        if self.verbose
                        else None
                    )
                    return "NoNFTFound"

                funcResult["nftLink"] = nftLink
                funcResult["tokenId"] = tokenId
                funcResult["taxonId"] = taxonId
                (
                    loggingInstance.info(f"getRandomNFT({xrpId}): {funcResult}")
                    if self.verbose
                    else None
                )
                return funcResult

            (
                loggingInstance.error(f"getRandomNFT({xrpId}): NoNFTFound")
                if self.verbose
                else None
            )
            return "NoNFTFound"

    async def getClaimQuote(self, taxonId) -> dict:
        async with self.asyncSessionMaker() as session:
            # Query the rows of taxonId
            query = select(ClaimQuotes.taxonId).group_by(ClaimQuotes.taxonId)
            taxonIdList = await session.execute(query)

            # Get, parse, and put them into a list
            taxonIdList = [row[0] for row in taxonIdList.all()]

            # Retain taxonId if it is in the list, else 0
            taxonId = taxonId if taxonId in taxonIdList else 0

            funcResult = {"nftGroupName": None, "description": None}
            query = (
                select(ClaimQuotes.nftGroupName, ClaimQuotes.description)
                .filter(
                    ClaimQuotes.taxonId == taxonId,
                )
                .order_by(func.random())
                .limit(1)
            )
            queryResult = await session.execute(query)
            queryResult = queryResult.first()

            if not queryResult:
                loggingInstance.error(f"getClaimQuote({taxonId}): ClaimQuoteError")
                raise Exception("ClaimQuoteError")

            nftGroupName, description = queryResult

            funcResult["description"] = description
            funcResult["nftGroupName"] = nftGroupName

            loggingInstance.info(f"getClaimQuote({taxonId}): {description}")
            return funcResult

    async def getPenaltyStatus(self, xrpId):
        funcResult = {
            "result": "",
            "timeRemaining": {
                "hour": 0,
                "minute": 0,
                "second": 0,
            },
        }

        async with self.asyncSessionMaker() as session:
            query = select(
                RewardsTable.dailyTraitFlagDate,
                func.utc_timestamp(),
                RewardsTable.penaltyTraits3DRewards,
            ).filter(RewardsTable.xrpId == xrpId)
            queryResult = await session.execute(query)
            queryResult = queryResult.first()

            funcResult = self.check_cooldown(queryResult, funcResult)

            if queryResult:
                x, y, funcResult["amount"] = queryResult

            loggingInstance.info(f"getBonusStatus({xrpId}): {funcResult['result']}")

            return funcResult

    async def setPenaltyStatusClaimed(self, xrpId):
        async with self.asyncSessionMaker() as session:
            async with session.begin():
                try:
                    await session.execute(
                        update(RewardsTable)
                        .where(RewardsTable.xrpId == xrpId)
                        .values(dailyTraitFlagDate=self.getLastRedemption())
                    )
                    if self.verbose:
                        loggingInstance.info(
                            f"setPenaltyStatusClaimed({xrpId}): Success"
                        )
                except Exception as e:
                    if self.verbose:
                        loggingInstance.error(f"setPenaltyStatusClaimed({xrpId}): {e}")
                    await session.rollback()

    def getLastRedemption(self):
        est = tz("US/Eastern")
        current_time = datetime.now(timezone.utc)
        current_est = current_time.astimezone(est)
        lastEst = datetime(
            current_est.year,
            current_est.month,
            current_est.day,
            19,
            0,
            0,
            tzinfo=est,
        )
        if current_est < lastEst:
            lastEst += timedelta(days=-1)

        return lastEst.astimezone(timezone.utc)
