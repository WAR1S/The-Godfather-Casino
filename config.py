import os
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

def _ids(raw: str) -> list[int]:
    return [int(x) for x in raw.split(",") if x.strip().isdigit()]

class Config:
    TOKEN               = os.getenv("DISCORD_TOKEN", "")
    PREFIX              = os.getenv("BOT_PREFIX", ".")
    DB_PATH             = os.getenv("DB_PATH", "data/bot.db")

    MASTER_MNEMONIC     = os.getenv("MASTER_MNEMONIC", "").strip()
    LTC_HOT_WIF         = os.getenv("LTC_HOT_WIF", "").strip()

    DEPOSIT_LTC_ADDRESS = os.getenv("DEPOSIT_LTC_ADDRESS", "").strip()

    LTCSPACE_API        = os.getenv("LTCSPACE_API", "https://litecoinspace.org/api").rstrip("/")

    LTC_PER_POINT       = float(os.getenv("LTC_PER_POINT", "0.0001"))
    POINTS_PER_USD      = int(os.getenv("POINTS_PER_USD", "1000"))
    MIN_DEPOSIT_USD     = float(os.getenv("MIN_DEPOSIT_USD", "1"))
    MIN_WITHDRAW_USD    = float(os.getenv("MIN_WITHDRAW_USD", "2"))
    WITHDRAW_FEE_USD    = float(os.getenv("WITHDRAW_FEE_USD", "0.5"))

    DEPOSIT_POLL_SECONDS   = int(os.getenv("DEPOSIT_POLL_SECONDS", "45"))
    PRICE_REFRESH_SECONDS  = int(os.getenv("PRICE_REFRESH_SECONDS", "60"))

    OWNER_IDS           = _ids(os.getenv("OWNER_IDS", ""))
    OWNER_ALERT_DM      = int(os.getenv("OWNER_ALERT_DM", "0") or 0)

    LTC_DECIMALS        = 8