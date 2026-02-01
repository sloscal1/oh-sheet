"""Test fixtures for echomtg_sync tests."""

from io import StringIO

import pandas as pd
import pytest


@pytest.fixture
def sample_local_csv_data() -> str:
    """Sample local inventory CSV data with locations."""
    return """Reg Qty,Foil Qty,Name,Set,Rarity,Acquired,Language,Date Acquired,Set Code,Collector Number,Condition,Marked as Trade,note,echo_inventory_id,tcgid,echoid
1.0,0.0,Lightning Bolt,Double Masters,Rare,,EN,,2XM,0117,NM,0.0,b3r4p100,,,
1.0,0.0,Lightning Bolt,Double Masters,Rare,,EN,,2XM,0117,NM,0.0,b3r4p101,,,
0.0,1.0,Lightning Bolt,Double Masters,Rare,,EN,,2XM,0117,NM,0.0,frame5,,,
1.0,0.0,Shock,Strixhaven Mystical Archive,Uncommon,,EN,,STA,0049,NM,0.0,b3r4p200,,,
1.0,0.0,Selesnya Guildgate,Ravnica Remastered,Common,,EN,,RVR,0286,NM,0.0,b3r4p466a,,,
1.0,0.0,Selesnya Guildgate,Ravnica Remastered,Common,,EN,,RVR,0286,NM,0.0,b3r4p466b,,,
1.0,0.0,Selesnya Guildgate,Ravnica Remastered,Common,,EN,,RVR,0286,NM,0.0,b3r4p466c,,,
"""


@pytest.fixture
def sample_echo_csv_data() -> str:
    """Sample EchoMTG export CSV data with echo_inventory_ids."""
    return """Reg Qty,Foil Qty,Name,Set,Rarity,Acquired,Language,Date Acquired,Set Code,Collector Number,Condition,Marked as Trade,note,echo_inventory_id,tcgid,echoid
"1","0","Lightning Bolt","Double Masters","Rare","1.50","EN","01/26/2026","2XM","117","NM","0"," ","58942001","123456","78901"
"1","0","Lightning Bolt","Double Masters","Rare","1.50","EN","01/26/2026","2XM","117","NM","0"," ","58942002","123456","78901"
"1","0","Lightning Bolt","Double Masters","Rare","1.50","EN","01/26/2026","2XM","117","NM","0"," ","58942003","123456","78901"
"0","1","Lightning Bolt","Double Masters","Rare","2.00","EN","01/26/2026","2XM","117","NM","0"," ","58942004","123456","78901"
"1","0","Shock","Strixhaven Mystical Archive","Uncommon","0.25","EN","01/26/2026","STA","49","NM","0"," ","58942005","123457","78902"
"1","0","Selesnya Guildgate","Ravnica Remastered","Common","0.19","EN","01/26/2026","RVR","286","NM","0"," ","58942006","123458","78903"
"1","0","Selesnya Guildgate","Ravnica Remastered","Common","0.19","EN","01/26/2026","RVR","286","NM","0"," ","58942007","123458","78903"
"1","0","Selesnya Guildgate","Ravnica Remastered","Common","0.19","EN","01/26/2026","RVR","286","NM","0"," ","58942008","123458","78903"
"1","0","Counterspell","Modern Horizons 2","Uncommon","0.50","EN","01/26/2026","MH2","267","NM","0"," ","58942009","123459","78904"
"""


@pytest.fixture
def sample_local_df(sample_local_csv_data: str) -> pd.DataFrame:
    """Load sample local CSV as DataFrame."""
    df = pd.read_csv(StringIO(sample_local_csv_data), dtype=str)
    return df.fillna("")


@pytest.fixture
def sample_echo_df(sample_echo_csv_data: str) -> pd.DataFrame:
    """Load sample echo CSV as DataFrame."""
    df = pd.read_csv(StringIO(sample_echo_csv_data), dtype=str)
    return df.fillna("")
