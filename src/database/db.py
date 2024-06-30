from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import update
from database.models.rewardstable import RewardsTable
from database.models.nftTraitList import NFTTraitList
from sqlalchemy.sql import func
from datetime import timedelta, datetime
from sqlalchemy.future import select

from utils.logging import loggingInstance

class XparrotDB:
    def __init__(self, host, dbName, username, password, verbose):
        
        #                   username          if empty, do not add :, else :password      host   dbName
        sqlLink = f"mysql+aiomysql://{username}{'' if password in ['', None] else f':{password}'}@{host}/{dbName}"
        loggingInstance.info(f"DB Link: {sqlLink}")
        self.dbEngine = create_async_engine(sqlLink, 
                                            echo=verbose,
                                            pool_recycle = 3600,
                                            pool_pre_ping=True)
        
        self.asyncSessionMaker = async_sessionmaker(bind=self.dbEngine,
                                                    expire_on_commit=False)
        self.verbose = verbose
    
    async def getBonusStatus(self, xrpId: str) -> dict:
        # Return structure
        funcResult = {"result":"", 
                      'timeRemaining':
                          {
                              'hour':0,
                              'minute':0,
                              'second':0,
                          }}
        
        async with self.asyncSessionMaker() as session: 
            # Query the required columns
            query = select(
                RewardsTable.dailyBonusFlagDate,
                func.now()
            ).filter(RewardsTable.xrpId == xrpId)
            result = await session.execute(query)
            result = result.first()
            
            loggingInstance.info(f"Query Result: {result}") if self.verbose else None
            
            # Check if there are results
            # No result would only mean that xrpId is not found
            if result:
                lastClaim, currentTime = result
                
                # Check if the user has ever claimed their dailies
                # If not, the dailies are available to redeem
                if lastClaim and not lastClaim == "0000-00-00 00:00:00":
                    lastClaim = datetime.strptime(lastClaim,"%Y-%m-%d %H:%M:%S") if type(lastClaim) == str else lastClaim
                    nextClaim = lastClaim + timedelta(days=2)
                                
                    # Check if the currentTime is past than nextClaim
                    if nextClaim > currentTime:
                        
                        
                        # compute the remaining time
                        timeDiff:timedelta = nextClaim - currentTime
                        
                        remainingHour = timeDiff.seconds // 3600  + (timeDiff.days * 24)
                        remainingMin = (timeDiff.seconds // 60) % 60  
                        remainingSec = timeDiff.seconds % 60
                        
                        # Ready the return structure
                        funcResult["result"] = 'NotReady'
                        funcResult['timeRemaining']['hour'] = remainingHour
                        funcResult['timeRemaining']['minute'] = remainingMin
                        funcResult['timeRemaining']['second'] = remainingSec
                        
                        loggingInstance.info(f"getBonusStatus({xrpId}): {funcResult}") if self.verbose else None
                        
                        return funcResult
                        
                    else:
                        funcResult["result"] = 'Claimable'
                        loggingInstance.info(f"getBonusStatus({xrpId}): {funcResult['result']}") if self.verbose else None
                        return funcResult
                else:
                    funcResult["result"] = 'Claimable'
                    loggingInstance.info(f"getBonusStatus({xrpId}): {funcResult['result']}") if self.verbose else None
                    return funcResult
            else:
                funcResult['result'] = "XrpIdNotFound"
                loggingInstance.error(f"getBonusStatus({xrpId}): {funcResult['result']}") if self.verbose else None
                return funcResult
            
    async def getBonusAmount(self, xrpId: str) -> dict:
        async with self.asyncSessionMaker() as session:
            funcResult = {'result':None,'amount':None,'nftLink':None, 'tokenId':None}
            query = select(
                NFTTraitList.totalXRAIN, NFTTraitList.nftlink, NFTTraitList.tokenId
            ).filter(
                NFTTraitList.xrpId == xrpId,
                NFTTraitList.nftlink != ''
            ).order_by(
                func.random()
            ).limit(1)
            queryResult = await session.execute(query)
            queryResult = queryResult.first()
            
            loggingInstance.info(f"Query Result: {queryResult}") if self.verbose else None
            
            if queryResult:
                xrainValue, nftLink, tokenId = queryResult
                
                if nftLink == "":
                    funcResult['result'] = 'ImageLinkNotFound'
                    loggingInstance.error(f"getBonusAmount({xrpId}): {funcResult['result']}") if self.verbose else None
                    return funcResult
                
                funcResult['result'] = 'Success'
                funcResult['nftLink'] = nftLink
                funcResult['amount'] = xrainValue
                funcResult['tokenId'] = tokenId
                loggingInstance.info(f"getBonusAmount({xrpId}): {funcResult['result']}") if self.verbose else None
                return funcResult            
            else:
                funcResult['result'] = "XrpIdNotFound"
                loggingInstance.info(f"    getBonusAmount({xrpId}): {funcResult['result']}") if self.verbose else None
                return funcResult
    
    async def getBiWeeklyStatus(self, xrpId) -> bool | int:
        
        async with self.asyncSessionMaker() as session:
            query = select(RewardsTable.penaltyReputationRewards,
                                            RewardsTable.bonusXrainFlag, 
                                            RewardsTable.reputationFlag)\
                                        .filter(RewardsTable.xrpId == xrpId)
            queryResult = await session.execute(query)
            queryResult = queryResult.first()
            
            if queryResult:
                rewardAmount, bonusFlag, repFlag = queryResult
                if bonusFlag == 1 or repFlag == 1:
                    
                    loggingInstance.error(f"getBiWeeklyStatus({xrpId}): BonusReputationFlagTriggered ") if self.verbose else None
                    return False
                
                loggingInstance.info(f"getBiWeeklyStatus({xrpId}): Bi-Weekly reward is {rewardAmount}") if self.verbose else None
                return rewardAmount
            
            else:
                loggingInstance.error(f"getBiWeeklyStatus({xrpId}): XrpIdNotFound") if self.verbose else None
                return False
        
    async def biweeklySet(self, xrpId) -> None:
        async with self.asyncSessionMaker() as session:
            async with session.begin():
                try:
                    await session.execute(
                        update(RewardsTable).where(RewardsTable.xrpId == xrpId).values(bonusXrainFlag=1)
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
                        update(
                            RewardsTable
                        ).where(
                            RewardsTable.xrpId == xrpId
                        ).values(
                            dailyBonusFlagDate = func.now()
                        )
                    )
                    if self.verbose:
                        loggingInstance.info(f"bonusSet({xrpId}): Success")
                except Exception as e:
                    if self.verbose:
                        loggingInstance.error(f"bonusSet({xrpId}): {e}")
                    await session.rollback()
                    
    async def getRandomNFT(self, xrpId) -> dict:
        async with self.asyncSessionMaker() as session:
            funcResult = {'nftLink':None, 'tokenId':None}
            query = select(
                        NFTTraitList.nftlink, NFTTraitList.tokenId
                    ).filter(
                        NFTTraitList.xrpId == xrpId,
                        NFTTraitList.nftlink != ''
                    ).order_by(
                        func.random()
                    ).limit(1)
            queryResult = await session.execute(query)
            queryResult = queryResult.first()
            
            loggingInstance.info(f"Query Result: {queryResult}") if self.verbose else None
            
            if queryResult:
                nftLink, tokenId = queryResult
                
                if nftLink == "":
                    loggingInstance.error(f"getRandomNFT({xrpId}): NoNFTFound") if self.verbose else None
                    return 'NoNFTFound'
                
                funcResult['nftLink'] = nftLink
                funcResult['tokenId'] = tokenId
                loggingInstance.info(f"getRandomNFT({xrpId}): {funcResult}") if self.verbose else None
                return funcResult
            
            loggingInstance.error(f"getRandomNFT({xrpId}): NoNFTFound") if self.verbose else None
            return 'NoNFTFound'