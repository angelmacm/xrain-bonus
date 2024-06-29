from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import create_engine, and_, or_, update
from sqlalchemy.orm import sessionmaker
from database.models.rewardstable import RewardsTable
from database.models.nftTraitList import NFTTraitList
from sqlalchemy.sql import func
from sqlalchemy.types import DateTime
from datetime import timedelta, datetime
from sqlalchemy.future import select

class XparrotDB:
    def __init__(self, host, dbName, username, password, verbose):
        
        #                   username          if empty, do not add :, else :password      host   dbName
        sqlLink = f"mysql+aiomysql://{username}{'' if password in ['', None] else f':{password}'}@{host}/{dbName}"
        self.dbEngine = create_async_engine(sqlLink, echo=verbose)
        self.asyncSessionMaker = async_sessionmaker(bind=self.dbEngine, expire_on_commit=False)
        self.verbose = verbose
    
    async def getDailyStatus(self, xrpId: str) -> dict:
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
            
            print(f"[DB]    Query Result: {result}") if self.verbose else None
            
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
                        
                        # Parse the remaining time
                        remainingHour, remainingMin, remainingSec = str(timeDiff).split(":")
                        
                        # Ready the return structure
                        funcResult["result"] = 'NotReady'
                        funcResult['timeRemaining']['hour'] = remainingHour
                        funcResult['timeRemaining']['minute'] = remainingMin
                        funcResult['timeRemaining']['second'] = remainingSec
                        
                        print(f"[DB]    getDailyStatus({xrpId}): {funcResult}") if self.verbose else None
                        
                        return funcResult
                        
                    else:
                        funcResult["result"] = 'Claimable'
                        print(f"[DB]    getDailyStatus({xrpId}): {funcResult['result']}") if self.verbose else None
                        return funcResult
                else:
                    funcResult["result"] = 'Claimable'
                    print(f"[DB]    getDailyStatus({xrpId}): {funcResult['result']}") if self.verbose else None
                    return funcResult
            else:
                funcResult['result'] = "XrpIdNotFound"
                print(f"[DB]    getDailyStatus({xrpId}): {funcResult['result']}") if self.verbose else None
                return funcResult
            
    async def getDailyAmount(self, xrpId: str) -> dict:
        async with self.asyncSessionMaker() as session:
            funcResult = {'result':None,'amount':None,'nftLink':None}
            query = select(
                NFTTraitList.totalXRAIN, NFTTraitList.nftlink
            ).filter(
                NFTTraitList.xrpId == xrpId,
                NFTTraitList.nftlink != ''
            ).order_by(
                func.random()
            ).limit(1)
            queryResult = await session.execute(query)
            queryResult = queryResult.first()
            
            if queryResult:
                xrainValue, nftLink = queryResult
                
                if nftLink == "":
                    funcResult['result'] = 'ImageLinkNotFound'
                    print(f"[DB]    getDailyAmount({xrpId}): {funcResult['result']}") if self.verbose else None
                    return funcResult
                
                funcResult['result'] = 'Success'
                funcResult['nftLink'] = nftLink
                funcResult['amount'] = xrainValue
                print(f"[DB]    getDailyAmount({xrpId}): {funcResult['result']}") if self.verbose else None
                return funcResult            
            else:
                funcResult['result'] = "XrpIdNotFound"
                print(f"[DB]    getDailyAmount({xrpId}): {funcResult['result']}") if self.verbose else None
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
                    
                    print(f"[DB]    getBiWeeklyStatus({xrpId}): BonusReputationFlagTriggered ") if self.verbose else None
                    return False
                
                print(f"[DB]    getBiWeeklyStatus({xrpId}): Bi-Weekly reward is {rewardAmount}") if self.verbose else None
                return rewardAmount
            
            else:
                print(f"[DB]    getBiWeeklyStatus({xrpId}): XrpIdNotFound") if self.verbose else None
                return False
        
    async def biweeklySet(self, xrpId) -> None:
        async with self.asyncSessionMaker() as session:
            async with session.begin():
                try:
                    await session.execute(
                        update(RewardsTable).where(RewardsTable.xrpId == xrpId).values(bonusXrainFlag=1)
                    )
                    if self.verbose:
                        print(f"[DB]    biweeklySet({xrpId}): Success")
                except Exception as e:
                    if self.verbose:
                        print(f"[DB]    biweeklySet({xrpId}): {e}")
                    await session.rollback()
           
    
    async def dailySet(self, xrpId) -> None:
        async with self.asyncSessionMaker() as session:
            async with session.begin():
                try:
                    await session.execute(
                        update(RewardsTable).where(RewardsTable.xrpId == xrpId).values(dailyBonusFlagDate=func.now())
                    )
                    if self.verbose:
                        print(f"dailySet({xrpId}): Success")
                except Exception as e:
                    if self.verbose:
                        print(f"dailySet({xrpId}): {e}")
                    await session.rollback()