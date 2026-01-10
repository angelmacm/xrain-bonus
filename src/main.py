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
from interactions import Embed, Button, ButtonStyle

# Other imports
from datetime import datetime
from random import randint

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

MIN_NFT_TO_CLAIM = coinsConfig.getint("min_nft_count")

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


def prepare_message(message, title="One Time Claim", color=None):
    embed = Embed(
        title=title if title else None,
        description=message,
        color=color if color else random_color(),
    )
    return embed


def escapeMarkdown(text: str) -> str:
    escapeChars = ["*", "_", "~", "`"]
    for char in escapeChars:
        text = text.replace(char, f"\\{char}")
    return text


def precision(value, precision=6):
    return round(float(value), precision)


async def sendCoin(value, address, memos, ctx):
    status = True
    sendSuccess = await xrplInstance.sendCoin(
        address=address,
        value=precision(value),
        coinHex=coinsConfig["XRAIN"],
        memos=memos,
    )

    if not sendSuccess["result"]:
        status = False
        if "tecPATH_DRY" in str(sendSuccess["error"]):
            embed = Embed(
                title="XRAIN Claim",
                description=f"Please setup XRAIN trustline to claim rewards by clicking this [link](https://xrpl.services/?issuer=rh3tLHbXwZsp7eciw2Qp8g7bN9RnyGa2pF&currency=585241494E000000000000000000000000000000&limit=21000000)",
                timestamp=datetime.now(),
            )
        elif "Connection timeout" in str(sendSuccess["error"]):
            embed = Embed(
                title="XRAIN Claim",
                description=f"Error connecting to the XRPL Server, please try again",
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


async def checkStatus(result, ctx, rewardName):
    if result["result"] == "Claimable":
        return True

    if result["result"] == "NotReady":
        remainingHour = result["timeRemaining"]["hour"]
        remainingMinute = result["timeRemaining"]["minute"]
        remainingSecond = result["timeRemaining"]["second"]

        description = (
            f"Your {rewardName} rewards have already been claimed, please wait **__"
        )
        description += f"{remainingHour}hr" if int(remainingHour) != 0 else ""
        description += f" {remainingMinute}min" if int(remainingMinute) != 0 else ""
        description += f" {remainingSecond}s" if int(remainingSecond) != 0 else ""
        description += "__** to the next XRAIN claim period."

        embed = Embed(
            title="XRAIN Claim", description=description, timestamp=datetime.now()
        )

    elif result["result"] == "XrpIdNotFound":
        embed = Embed(
            title="XRAIN Claim",
            description=f"XRP Address not found in our database, please open a support ticket for assistance",
            timestamp=datetime.now(),
        )
    elif result["result"] == "flagged":
        embed = Embed(
            title="XRAIN Claim",
            description=f"You are not eligible for {rewardName} rewards. Open support ticket for assistance.",
            timestamp=datetime.now(),
        )

    elif result["result"] == "minNFTCount":
        embed = prepare_message(
            f"Your XRP ID does not hold enough OG NFTs. You must hold a min of {MIN_NFT_TO_CLAIM} OG NFT to the bonus tokens."
        )
        await ctx.send(embed=embed)
        return

    else:
        embed = Embed(
            title="XRAIN Claim",
            description=f"{result['result']} error occurred",
            timestamp=datetime.now(),
        )

    embed.set_footer(text="XRPLRainforest Bonus")
    await ctx.send(embed=embed)

    return False


def random_color():
    randomColorCode = str(hex(randint(0, 16777215)))[2:]

    for _ in range(abs(len(randomColorCode) - 6)):
        randomColorCode += "0"

    return f"#{randomColorCode}"


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

    if await is_on_cooldown(ctx):
        return

    (
        loggingInstance.info(f"Bonus Claim requested by {ctx.author.display_name}")
        if botVerbosity
        else None
    )

    xrpId = ctx.args[0]

    result = await dbInstance.getBonusStatus(xrpId)

    claimable = await checkStatus(result, ctx, rewardName="Bonus XRAIN")

    if not claimable:
        return

    claimInfo = await dbInstance.getBonusAmount(xrpId)
    if claimInfo["result"] == "Success":
        claimImage = claimInfo["nftLink"]
        tokenId = claimInfo["tokenId"]

        claimAmount = xrplInstance.getAccountBalance(xrpId, coinsConfig["XRAIN"])
        minXrainCount = coinsConfig.getfloat("min_xrain_count")

        if claimAmount and claimAmount < minXrainCount:
            embed = prepare_message(
                message=f"Your XRP ID does not hold enough $XRAIN. You must hold a min of {minXrainCount} $XRAIN and {MIN_NFT_TO_CLAIM} OG NFT to claim daily XRAIN reward.",
                title="Daily Claim",
            )
            button = Button(
                style=ButtonStyle.URL,
                label="Buy More",
                url=coinsConfig.get("xrain_buy_link"),
            )
            await ctx.send(embed=embed, components=button)
            return

        claimAmount *= coinsConfig.getfloat("daily_multiplier")

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
            color=random_color(),
        )

        imageEmbed = Embed(
            description=f"[View NFT Details](https://xrp.cafe/nft/{tokenId})"
        )

        imageEmbed.set_image(url=claimImage)

        await ctx.send(embeds=[claimEmbed, imageEmbed])
    else:
        embed = Embed(
            title="XRAIN Claim",
            description=f"{claimInfo['result']} error occurred",
            timestamp=datetime.now(),
        )

        embed.set_footer(text="XRPLRainforest Bonus")

        await ctx.send(embed=embed)


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

    if await is_on_cooldown(ctx):
        return

    xrpId = ctx.args[0]

    try:
        result = await dbInstance.getPenaltyStatus(xrpId)
        randomNFT = await dbInstance.getRandomNFT(xrpId)
        if randomNFT == "NoNFTFound":
            raise Exception("NoNFTFound")
    except Exception as e:
        await ctx.send(f"{e} error occurred")
        return

    claimable = await checkStatus(result, ctx, rewardName="Traits XRAIN")

    if not claimable:
        return

    amount = max(precision(result["amount"] / 30), 0.01)

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
        color=random_color(),
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


@slash_command(
    name="xrain-amm-claim",
    description="Claim your AMM bonus XRAIN tokens",
    options=[
        slash_str_option(
            name="xrpid",
            description="XRP Address that will receive the bonus reward",
            required=True,
        )
    ],
)
async def xrain_amm_claim(ctx: InteractionContext):

    if await is_on_cooldown(ctx=ctx):
        return

    await ctx.defer()  # Defer the response to wait for the function to run.

    (
        loggingInstance.info(
            f"/xrain_amm_claim requested by {ctx.author.display_name}: {ctx.author_id}"
        )
        if botVerbosity
        else None
    )

    xrpId = ctx.args[0]

    coinBalance = await xrplInstance.getAccountBalance(
        xrpId, coinsConfig.get("XRAIN_LP")
    )

    if not coinBalance or coinBalance < coinsConfig.getfloat("min_lp_count"):
        buy_link = (
            "https://xpmarket.com/amm/pool/XRAIN-rh3tLHbXwZsp7eciw2Qp8g7bN9RnyGa2pF/XRP"
        )
        embed = prepare_message(
            f"To claim daily $XRAIN you must hold a minimum of {precision(coinsConfig.getfloat('min_lp_count'))} XRP/XRAIN LP tokens and {coinsConfig.getint("min_nft_count")} XRPL Rainforest NFT in your wallet.\n\nClick this [link]({buy_link}) to add liquidity to XRP/OGcoin AMM pool",
            "Daily Bonus",
        )
        button = Button(
            style=ButtonStyle.URL,
            label="Add Liquidity",
            url=buy_link,
        )
        await ctx.send(embed=embed, components=button)
        return

    result = await dbInstance.get_amm_status(
        xrpId, min_amount=coinsConfig.getint("min_nft_count")
    )

    claimable = await checkStatus(result, ctx, rewardName="XRAIN AMM")

    if not claimable:
        return

    claimAmount = precision(
        float(coinBalance * coinsConfig.getfloat("xrain_multiplier"))
    )
    sendSuccess = await sendCoin(
        address=xrpId,
        value=claimAmount,
        memos="XRPLRainforest Bonus AMM Rewards",
        ctx=ctx,
    )

    if not sendSuccess:
        return

    embeds = []
    color = random_color()

    await dbInstance.update_amm_claimed(xrpId)

    authorName = escapeMarkdown(ctx.author.display_name)

    claimEmbed = prepare_message(
        title="XRAIN AMM Claim",
        message=f"Congratulations **{authorName}** you have claimed **__{claimAmount}__** $XRAIN based on the XRP/XRAIN LP tokens you hold!!",
        color=color,
    )
    embeds.append(claimEmbed)

    nftInfo = await dbInstance.getRandomNFT(xrpId)
    if "nftLink" in nftInfo:
        imageEmbed = Embed(color=color)
        imageEmbed.add_image(nftInfo["nftLink"])
        embeds.append(imageEmbed)

    if "taxonId" in nftInfo:
        try:
            message = await dbInstance.getClaimQuote(nftInfo["taxonId"])
        except Exception as e:
            await ctx.send(f"{e} error occurred")
            return
        messageEmbed = Embed(
            description=f"**{message['description']}**",
            timestamp=datetime.now(),
            color=color,
        )
        embeds.append(messageEmbed)

    embeds[-1].timestamp = datetime.now()
    embeds[-1].set_footer("XRPL Rainforest AMM Claim")

    await ctx.send(embeds=embeds)


if __name__ == "__main__":
    client.start()
