from database.db import XparrotDB
from utils.xrplCommands import XRPClient
from utils.config import botConfig, xrplConfig, dbConfig, coinsConfig
from utils.logging import loggingInstance

from interactions import (
    Intents,
    Client,
    listen,
    InteractionContext,
)  # General discord Interactions import
from interactions import slash_command, slash_str_option  # Slash command imports
from interactions import Embed

# Other imports
from datetime import datetime

intents = Intents.DEFAULT | Intents.MESSAGE_CONTENT
client = Client(intents=intents, token=botConfig["token"])

# Initialize DB connection
dbInstance = XparrotDB(
    host=dbConfig["db_server"],
    dbName=dbConfig["db_name"],
    username=dbConfig["db_username"],
    password=dbConfig["db_password"],
    verbose=dbConfig.getboolean("verbose"),
)

xrplInstance = XRPClient(xrplConfig)

botVerbosity = botConfig.getboolean("verbose")

cooldowns = {}


async def is_on_cooldown(ctx: InteractionContext) -> bool:
    user_id = ctx.author_id
    command_name = ctx._command_name
    if command_name not in cooldowns:
        cooldowns[command_name] = {}

    """Check if the user is on cooldown for a specific command."""
    print(f"Checking {user_id} for cooldown")
    now = datetime.now()
    if user_id in cooldowns[command_name]:
        last_used = cooldowns[command_name][user_id]
        if (now - last_used).total_seconds() < botConfig.getfloat("command_cooldown"):
            await ctx.send(
                f"You are on cooldown for this command. Please wait {botConfig.getfloat("command_cooldown")}s before using it again.",
                ephemeral=True,
            )
            return True

    cooldowns[command_name][user_id] = datetime.now()
    return False


def escapeMarkdown(text: str) -> str:
    escapeChars = ["*", "_", "~", "`"]
    for char in escapeChars:
        text = text.replace(char, f"\\{char}")
    return text


def precision(value, precision=6):
    return round(float(value), precision)


async def sendCoin(value, address, memo, ctx):
    status = True
    sendSuccess = await xrplInstance.sendCoin(
        address=address,
        value=precision(value),
        coinHex=coinsConfig["XRAIN"],
        memos=memo,
    )

    if not sendSuccess["result"]:
        status = False
        if "tecPATH_DRY" in str(sendSuccess["error"]):
            embed = Embed(
                title="XRAIN Claim",
                description=f"Please setup XRAIN trustline to claim rewards by clicking this [link](https://xrpl.services/?issuer=rh3tLHbXwZsp7eciw2Qp8g7bN9RnyGa2pF&currency=585241494E000000000000000000000000000000&limit=21000000)",
                timestamp=datetime.now(),
            )
        else:
            embed = Embed(
                title="XRAIN Claim",
                description=f"{sendSuccess['error'] if sendSuccess['error'] is not None else 'Unknown'} error occurred",
                timestamp=datetime.now(),
            )
        await ctx.send(embed=embed)

    return status


async def checkStatus(result, ctx):
    if result["result"] == "Claimable":
        return True

    if result["result"] == "NotReady":
        remainingHour = result["timeRemaining"]["hour"]
        remainingMinute = result["timeRemaining"]["minute"]
        remainingSecond = result["timeRemaining"]["second"]

        description = (
            "Your Bonus XRAIN rewards have already been claimed, please wait **__"
        )
        description += f"{remainingHour}hr" if int(remainingHour) != 0 else ""
        description += f" {remainingMinute}min" if int(remainingMinute) != 0 else ""
        description += f" {remainingSecond}s" if int(remainingSecond) != 0 else ""
        description += "__** to the next XRAIN claim period."

        embed = Embed(
            title="XRAIN Claim", description=description, timestamp=datetime.now()
        )

        embed.set_footer(text="XRPLRainforest Bonus")

        await ctx.send(embed=embed)

    else:
        embed = Embed(
            title="XRAIN Claim",
            description=f"{result['result']} error occurred",
            timestamp=datetime.now(),
        )

        embed.set_footer(text="XRPLRainforest Bonus")

        await ctx.send(embed=embed)

    return False


@listen()
async def on_ready():
    # Some function to do when the bot is ready
    await xrplInstance.registerSeed(xrplConfig["seed"])
    loggingInstance.info(f"Discord Bot Ready!")


# Dailies Command:
# Parameters:
#       XRP ID: [Required] XRP Address where the users hold their NFTs and the receipient of the reward
@slash_command(
    name="bonus-xrain",
    description="Redeem bonus rewards",
    options=[
        slash_str_option(
            name="xrpid",
            description="XRP Address that will receive the bonus reward",
            required=True,
        )
    ],
)
async def bonusXrain(ctx: InteractionContext):
    await ctx.defer()  # Defer the response to wait for the function to run.

    if is_on_cooldown(ctx):
        return

    (
        loggingInstance.info(f"Bonus Claim requested by {ctx.author.display_name}")
        if botVerbosity
        else None
    )

    xrpId = ctx.args[0]

    result = await dbInstance.getBonusStatus(xrpId)

    claimable = await checkStatus(result, ctx)

    if not claimable:
        return

    claimInfo = await dbInstance.getBonusAmount(xrpId)
    if claimInfo["result"] == "Success":
        claimAmount = claimInfo["amount"]
        claimImage = claimInfo["nftLink"]
        tokenId = claimInfo["tokenId"]
        taxonId = claimInfo["taxonId"]

        try:
            message = await dbInstance.getClaimQuote(taxonId)
        except Exception as e:
            ctx.send(f"{e} error occurred")
            return

        sendSuccess = await sendCoin(
            value=claimAmount,
            address=xrpId,
            memos="XRPLRainforest Bonus Rewards",
            ctx=ctx,
        )

        if not sendSuccess:
            return

        await dbInstance.bonusSet(xrpId)

        authorName = escapeMarkdown(ctx.author.display_name)

        claimEmbed = Embed(
            title="XRAIN Claim",
            description=f"Congratulations {authorName} you have claimed your XRPLRainforest Bonus XRAIN rewards totaling **__{claimAmount}__** XRAIN!! Claim again in **__24 Hours__**!",
        )

        messageEmbed = Embed(
            description=f"**{message['description']}**", timestamp=datetime.now()
        )
        messageEmbed.set_footer(text="XRPLRainforest Bonus")

        imageEmbed = Embed(
            description=f"[View NFT Details](https://xrp.cafe/nft/{tokenId})"
        )

        imageEmbed.set_image(url=claimImage)

        await ctx.send(embeds=[claimEmbed, imageEmbed, messageEmbed])
    else:
        embed = Embed(
            title="XRAIN Claim",
            description=f"{claimInfo['result']} error occurred",
            timestamp=datetime.now(),
        )

        embed.set_footer(text="XRPLRainforest Bonus")

        await ctx.send(embed=embed)


# Biweekly Command:
# Parameters:
#       XRP ID: [Required] XRP Address where the users hold their NFTs and the receipient of the reward
@slash_command(
    name="daily-xrain-rep",
    description="Redeem daily reputation rewards",
    options=[
        slash_str_option(
            name="xrpid",
            description="XRP Address that will receive the bonus reward",
            required=True,
        )
    ],
)
async def biweeklyXrain(ctx: InteractionContext):

    (
        loggingInstance.info(f"Biweekly claim requested by {ctx.author.display_name}")
        if botVerbosity
        else None
    )

    await ctx.defer()  # Defer the response to wait for the function to run.

    if is_on_cooldown(ctx):
        return

    xrpId = ctx.args[0]

    result = await dbInstance.getBiWeeklyStatus(xrpId)

    claimable = await checkStatus(result, ctx)

    if not claimable:
        return

    amount = precision(result["amount"] / 14)

    sendSuccess = await sendCoin(
        address=xrpId,
        value=amount,
        memos="XRPLRainforest Bonus Biweekly Reputation Rewards",
        ctx=ctx,
    )

    if not sendSuccess:
        return

    nftData = await dbInstance.getRandomNFT(xrpId)

    if nftData == "NoNFTFound":
        ctx.send("This xrpID has no XRPLRainforest NFTs")
        return

    await dbInstance.biweeklySet(xrpId)

    tokenId = nftData["tokenId"]
    nftLink = nftData["nftLink"]
    taxonId = nftData["taxonId"]

    try:
        message = await dbInstance.getClaimQuote(taxonId)
    except Exception as e:
        ctx.send(f"{e} error occurred")
        return

    authorName = escapeMarkdown(ctx.author.display_name)

    claimEmbed = Embed(
        title="XRAIN Claim",
        description=f"Congratulations {authorName} you have claimed your XRPLRainforest Bonus Daily XRAIN Reputation Rewards totaling **__{amount}__** XRAINs!!",
    )

    messageEmbed = Embed(
        description=f"**{message['description']}**", timestamp=datetime.now()
    )
    messageEmbed.set_footer(text="XRPLRainforest Bi-weekly Bonus")

    imageEmbed = Embed(
        description=f"[View NFT Details](https://xrp.cafe/nft/{tokenId})"
    )

    if nftLink != "NoNFTFound":
        imageEmbed.add_image(nftLink)

    await ctx.send(embeds=[claimEmbed, imageEmbed, messageEmbed])


@slash_command(
    name="daily-xrain-traits",
    description="Redeem daily traits rewards",
    options=[
        slash_str_option(
            name="xrpid",
            description="XRP Address that will receive the bonus reward",
            required=True,
        )
    ],
)
async def biweeklyXrainTraits(ctx: InteractionContext):

    (
        loggingInstance.info(
            f"/daily-xrain-traits requested by {ctx.author.display_name}"
        )
        if botVerbosity
        else None
    )

    await ctx.defer()  # Defer the response to wait for the function to run.

    if is_on_cooldown(ctx):
        return

    xrpId = ctx.args[0]

    try:
        result = await dbInstance.getPenaltyStatus(xrpId)
        randomNFT = await dbInstance.getRandomNFT(xrpId)
        if randomNFT == "NoNFTFound":
            raise Exception("NoNFTFound")
    except Exception as e:
        ctx.send(f"{e} error occurred")
        return

    claimable = await checkStatus(result, ctx)

    if not claimable:
        return

    amount = precision(result["amount"] / 14)

    sendSuccess = await sendCoin(
        address=xrpId,
        value=amount,
        memos="XRPLRainforest Bonus Biweekly Trait Rewards",
        ctx=ctx,
    )

    if not sendSuccess:
        return

    await dbInstance.setPenaltyStatusClaimed(xrpId)

    nftLink = randomNFT["nftLink"]
    claimMessage = await dbInstance.getClaimQuote(randomNFT["taxonId"])

    authorName = escapeMarkdown(ctx.author.display_name)

    embedClaim = Embed(
        title="XRAIN Claim",
        description=f"Congratulations {authorName} you have claimed your XRPLRainforest Daily Traits rewards totalling {amount} XRAIN!!",
    )

    embedText = Embed(
        description=f"**{claimMessage['description']}**", timestamp=datetime.now()
    )
    embedText.set_footer(text="XRPLRainforest Bi-weekly Traits Bonus")

    imageEmbed = Embed(
        description=f"[View NFT Details](https://xrp.cafe/nft/{randomNFT['tokenId']})"
    )

    if nftLink != "NoNFTFound":
        imageEmbed.add_image(nftLink)

    await ctx.send(embeds=[embedClaim, imageEmbed, embedText])


if __name__ == "__main__":
    client.start()
