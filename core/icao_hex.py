"""
ICAO 24-bit Hex Address Utilities

Provides:
1. hex_to_country(): Map ICAO 24-bit hex code to country of registration
2. airline_prefix_to_country(): Map 3-letter ICAO airline designator to operator country
3. check_identity_origin_conflict(): Compare hex country vs callsign operator country

Based on ICAO Annex 10, Volume III (ICAO 24-bit Address Allocation).
"""

from __future__ import annotations
from typing import Optional, Tuple, Dict

# ============================================================================
# ICAO 24-BIT HEX ADDRESS ALLOCATION TABLE
# Source: ICAO Doc 9680 / Annex 10 Volume III
# Format: (hex_start, hex_end, country_iso2, country_name)
# ============================================================================

ICAO_HEX_RANGES = [
    # === Africa ===
    (0x004000, 0x0043FF, "ZW", "Zimbabwe"),
    (0x006000, 0x006FFF, "MZ", "Mozambique"),
    (0x008000, 0x00FFFF, "ZA", "South Africa"),
    (0x010000, 0x017FFF, "EG", "Egypt"),
    (0x018000, 0x01FFFF, "LY", "Libya"),
    (0x020000, 0x027FFF, "MA", "Morocco"),
    (0x028000, 0x02FFFF, "TN", "Tunisia"),
    (0x030000, 0x0303FF, "BW", "Botswana"),
    (0x034000, 0x034FFF, "CM", "Cameroon"),
    (0x038000, 0x038FFF, "CG", "Congo (Brazzaville)"),
    (0x03E000, 0x03EFFF, "GA", "Gabon"),
    (0x040000, 0x040FFF, "CI", "Cote d'Ivoire"),
    (0x044000, 0x044FFF, "ET", "Ethiopia"),
    (0x048000, 0x048FFF, "GQ", "Equatorial Guinea"),
    (0x04C000, 0x04CFFF, "GH", "Ghana"),
    (0x050000, 0x050FFF, "GN", "Guinea"),
    (0x054000, 0x054FFF, "KE", "Kenya"),
    (0x058000, 0x058FFF, "NG", "Nigeria"),
    (0x060000, 0x060FFF, "UG", "Uganda"),
    (0x064000, 0x064FFF, "SN", "Senegal"),
    (0x068000, 0x068FFF, "SD", "Sudan"),
    (0x06C000, 0x06CFFF, "TZ", "Tanzania"),
    (0x070000, 0x070FFF, "TD", "Chad"),
    (0x074000, 0x074FFF, "ML", "Mali"),
    (0x078000, 0x078FFF, "NE", "Niger"),
    (0x09C000, 0x09CFFF, "DZ", "Algeria"),
    (0x0A0000, 0x0A0FFF, "AO", "Angola"),
    (0x0A8000, 0x0A8FFF, "ER", "Eritrea"),

    # === Europe ===
    (0x200000, 0x27FFFF, "RU", "Russia"),
    (0x300000, 0x33FFFF, "IT", "Italy"),
    (0x340000, 0x37FFFF, "ES", "Spain"),
    (0x380000, 0x3BFFFF, "FR", "France"),
    (0x3C0000, 0x3FFFFF, "DE", "Germany"),
    (0x400000, 0x43FFFF, "GB", "United Kingdom"),
    (0x440000, 0x447FFF, "AT", "Austria"),
    (0x448000, 0x44FFFF, "BE", "Belgium"),
    (0x450000, 0x457FFF, "BG", "Bulgaria"),
    (0x458000, 0x45FFFF, "DK", "Denmark"),
    (0x460000, 0x467FFF, "FI", "Finland"),
    (0x468000, 0x46FFFF, "GR", "Greece"),
    (0x470000, 0x477FFF, "HU", "Hungary"),
    (0x478000, 0x47FFFF, "NO", "Norway"),
    (0x480000, 0x487FFF, "NL", "Netherlands"),
    (0x488000, 0x48FFFF, "PL", "Poland"),
    (0x490000, 0x497FFF, "PT", "Portugal"),
    (0x498000, 0x49FFFF, "CZ", "Czech Republic"),
    (0x4A0000, 0x4A7FFF, "RO", "Romania"),
    (0x4A8000, 0x4AFFFF, "SE", "Sweden"),
    (0x4B0000, 0x4B7FFF, "CH", "Switzerland"),
    (0x4B8000, 0x4BFFFF, "TR", "Turkey"),
    (0x4C0000, 0x4C7FFF, "RS", "Serbia"),
    (0x4C8000, 0x4C83FF, "CY", "Cyprus"),
    (0x500000, 0x5003FF, "IE", "Ireland"),
    (0x501000, 0x5013FF, "IS", "Iceland"),
    (0x501C00, 0x501FFF, "LU", "Luxembourg"),
    (0x502C00, 0x502FFF, "MT", "Malta"),
    (0x503C00, 0x503FFF, "MC", "Monaco"),
    (0x505000, 0x5053FF, "AL", "Albania"),
    (0x506000, 0x506FFF, "HR", "Croatia"),
    (0x507000, 0x507FFF, "LV", "Latvia"),
    (0x508000, 0x508FFF, "LT", "Lithuania"),
    (0x509000, 0x509FFF, "MD", "Moldova"),
    (0x50A000, 0x50AFFF, "SK", "Slovakia"),
    (0x50B000, 0x50BFFF, "SI", "Slovenia"),
    (0x50C000, 0x50CFFF, "UZ", "Uzbekistan"),
    (0x510000, 0x5103FF, "UA", "Ukraine"),
    (0x514000, 0x5143FF, "BY", "Belarus"),
    (0x518000, 0x5183FF, "EE", "Estonia"),
    (0x51C000, 0x51C3FF, "MK", "North Macedonia"),
    (0x520000, 0x5203FF, "BA", "Bosnia Herzegovina"),
    (0x524000, 0x5243FF, "GE", "Georgia"),
    (0x528000, 0x5283FF, "TJ", "Tajikistan"),
    (0x52C000, 0x52C3FF, "ME", "Montenegro"),
    (0x600000, 0x6003FF, "AM", "Armenia"),
    (0x604000, 0x6043FF, "AZ", "Azerbaijan"),
    (0x608000, 0x6083FF, "KG", "Kyrgyzstan"),
    (0x60C000, 0x60C3FF, "TM", "Turkmenistan"),
    (0x610000, 0x6103FF, "KZ", "Kazakhstan"),

    # === Middle East & Asia ===
    (0x700000, 0x700FFF, "AF", "Afghanistan"),
    (0x704000, 0x704FFF, "QA", "Qatar"),
    (0x710000, 0x717FFF, "SA", "Saudi Arabia"),
    (0x718000, 0x71FFFF, "BD", "Bangladesh"),
    (0x720000, 0x727FFF, "BT", "Bhutan"),
    (0x728000, 0x72FFFF, "IQ", "Iraq"),
    (0x730000, 0x737FFF, "IR", "Iran"),
    (0x738000, 0x73FFFF, "IL", "Israel"),
    (0x740000, 0x747FFF, "JO", "Jordan"),
    (0x748000, 0x74FFFF, "LB", "Lebanon"),
    (0x750000, 0x757FFF, "MY", "Malaysia"),
    (0x758000, 0x75FFFF, "PH", "Philippines"),
    (0x760000, 0x767FFF, "PK", "Pakistan"),
    (0x768000, 0x76FFFF, "SG", "Singapore"),
    (0x770000, 0x777FFF, "LK", "Sri Lanka"),
    (0x778000, 0x77FFFF, "SY", "Syria"),
    (0x780000, 0x7BFFFF, "CN", "China"),
    (0x7C0000, 0x7FFFFF, "AU", "Australia"),
    (0x800000, 0x83FFFF, "IN", "India"),
    (0x840000, 0x87FFFF, "JP", "Japan"),
    (0x880000, 0x887FFF, "TH", "Thailand"),
    (0x888000, 0x88FFFF, "VN", "Vietnam"),
    (0x890000, 0x890FFF, "YE", "Yemen"),
    (0x894000, 0x8943FF, "BH", "Bahrain"),
    (0x895000, 0x8953FF, "BN", "Brunei"),
    (0x896000, 0x896FFF, "AE", "United Arab Emirates"),
    (0x898000, 0x898FFF, "KW", "Kuwait"),
    (0x89A000, 0x89AFFF, "MN", "Mongolia"),
    (0x89C000, 0x89CFFF, "OM", "Oman"),
    (0x89E000, 0x89E3FF, "NP", "Nepal"),
    (0x8A0000, 0x8A7FFF, "KR", "South Korea"),
    (0x8A8000, 0x8AFFFF, "KP", "North Korea"),
    (0x900000, 0x9FFFFF, "US", "United States (Mil)"),

    # === Americas ===
    (0xA00000, 0xAFFFFF, "US", "United States"),
    (0xC00000, 0xC3FFFF, "CA", "Canada"),
    (0xC80000, 0xC87FFF, "NZ", "New Zealand"),
    (0xE00000, 0xE3FFFF, "AR", "Argentina"),
    (0xE40000, 0xE7FFFF, "BR", "Brazil"),
    (0xE80000, 0xE80FFF, "CL", "Chile"),
    (0xE84000, 0xE84FFF, "CO", "Colombia"),
    (0xE88000, 0xE88FFF, "CR", "Costa Rica"),
    (0xE8C000, 0xE8CFFF, "CU", "Cuba"),
    (0xE90000, 0xE90FFF, "EC", "Ecuador"),
    (0xEA0000, 0xEA0FFF, "MX", "Mexico"),
    (0xEAC000, 0xEACFFF, "UY", "Uruguay"),
    (0xEB0000, 0xEB0FFF, "VE", "Venezuela"),

    # === Offshore registration hubs ===
    (0x4A4000, 0x4A43FF, "BM", "Bermuda"),       # British overseas territory
    (0x06A000, 0x06A3FF, "KY", "Cayman Islands"),  # British overseas territory
    (0x4D0000, 0x4D03FF, "IM", "Isle of Man"),     # British Crown dependency
    (0x4CC000, 0x4CC3FF, "VP-B", "Bermuda (VP-B)"),  # Alternate Bermuda block
]

# Build a sorted list for binary search
_SORTED_RANGES = sorted(ICAO_HEX_RANGES, key=lambda r: r[0])

# Offshore registration countries (should be excluded from IOC alerts)
OFFSHORE_REGISTRATION_COUNTRIES = {"BM", "KY", "IM", "VP-B", "AI", "VG", "TC", "MS", "SH"}


def hex_to_country(hex_code: str) -> Optional[Tuple[str, str]]:
    """
    Map an ICAO 24-bit hex address to country of registration.
    
    Args:
        hex_code: The hex address string (e.g., "738065", "4B8A23")
        
    Returns:
        Tuple of (country_iso2, country_name) or None if not found
    """
    if not hex_code:
        return None
    
    # Clean and parse hex
    hex_clean = hex_code.strip().upper()
    try:
        hex_int = int(hex_clean, 16)
    except (ValueError, TypeError):
        return None
    
    # Binary search through sorted ranges
    lo, hi = 0, len(_SORTED_RANGES) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        start, end, iso2, name = _SORTED_RANGES[mid]
        if hex_int < start:
            hi = mid - 1
        elif hex_int > end:
            lo = mid + 1
        else:
            return (iso2, name)
    
    return None


# ============================================================================
# ICAO AIRLINE DESIGNATOR TO COUNTRY MAPPING
# Source: ICAO Doc 8585 (Designators for Aircraft Operating Agencies)
# Format: {"3-letter ICAO code": ("country_iso2", "airline_name")}
# Focused on Middle East, Europe, and key global carriers
# ============================================================================

AIRLINE_COUNTRY_MAP: Dict[str, Tuple[str, str]] = {
    # === Israel ===
    "ELY": ("IL", "El Al Israel Airlines"),
    "ISR": ("IL", "Israir Airlines"),
    "AIZ": ("IL", "Arkia Israeli Airlines"),
    "ICL": ("IL", "CAL Cargo Air Lines"),
    
    # === Lebanon ===
    "MEA": ("LB", "Middle East Airlines"),
    "TMA": ("LB", "Trans Mediterranean Airways"),
    
    # === Jordan ===
    "RJA": ("JO", "Royal Jordanian"),
    "JZR": ("JO", "Jazeera Airways"),
    
    # === Egypt ===
    "MSR": ("EG", "EgyptAir"),
    "MSX": ("EG", "EgyptAir Express"),
    "NIA": ("EG", "Nile Air"),
    "ALW": ("EG", "Air Leisure"),
    
    # === Syria ===
    "SYR": ("SY", "Syrian Air"),
    "RBG": ("SY", "Cham Wings Airlines"),
    
    # === Iran ===
    "IRM": ("IR", "Mahan Air"),
    "IRA": ("IR", "Iran Air"),
    "IRZ": ("IR", "SAHA Airlines"),
    "IRC": ("IR", "Iran Aseman Airlines"),
    "QFZ": ("IR", "Qeshm Fars Air"),
    "IRK": ("IR", "Kish Air"),
    "TBZ": ("IR", "ATA Airlines (Iran)"),
    "CPN": ("IR", "Caspian Airlines"),
    "PYA": ("IR", "Pouya Air"),
    "FRS": ("IR", "Fars Air Qeshm"),
    
    # === Iraq ===
    "IAW": ("IQ", "Iraqi Airways"),
    "KNI": ("IQ", "Fly Baghdad"),
    
    # === Saudi Arabia ===
    "SVA": ("SA", "Saudi Arabian Airlines"),
    "SWQ": ("SA", "Flynas"),
    "FAD": ("SA", "Flyadeal"),
    
    # === UAE ===
    "UAE": ("AE", "Emirates"),
    "ETD": ("AE", "Etihad Airways"),
    "FDB": ("AE", "flydubai"),
    "ABY": ("AE", "Air Arabia"),
    "WIZ": ("AE", "Wizz Air Abu Dhabi"),
    
    # === Qatar ===
    "QTR": ("QA", "Qatar Airways"),
    
    # === Kuwait ===
    "KAC": ("KW", "Kuwait Airways"),
    
    # === Bahrain ===
    "GFA": ("BH", "Gulf Air"),
    
    # === Oman ===
    "OMA": ("OM", "Oman Air"),
    "SER": ("OM", "SalamAir"),
    
    # === Turkey ===
    "THY": ("TR", "Turkish Airlines"),
    "PGT": ("TR", "Pegasus Airlines"),
    "SXS": ("TR", "SunExpress"),
    "KKK": ("TR", "AtlasGlobal"),
    "TJK": ("TR", "TurkishJet"),
    
    # === Cyprus ===
    "CYP": ("CY", "Cyprus Airways"),
    "TUS": ("CY", "Tus Airways"),
    
    # === Russia ===
    "AFL": ("RU", "Aeroflot"),
    "SDM": ("RU", "S7 Airlines"),
    "SVR": ("RU", "Ural Airlines"),
    "VDA": ("RU", "Volga-Dnepr Airlines"),
    
    # === UK ===
    "BAW": ("GB", "British Airways"),
    "EZY": ("GB", "easyJet"),
    "VIR": ("GB", "Virgin Atlantic"),
    "TOM": ("GB", "TUI Airways"),
    
    # === Germany ===
    "DLH": ("DE", "Lufthansa"),
    "EWG": ("DE", "Eurowings"),
    "CFG": ("DE", "Condor"),
    "BOX": ("DE", "Aerologic"),
    
    # === France ===
    "AFR": ("FR", "Air France"),
    "TVF": ("FR", "Transavia France"),
    
    # === Netherlands ===
    "KLM": ("NL", "KLM Royal Dutch Airlines"),
    "TRA": ("NL", "Transavia"),
    
    # === Spain ===
    "IBE": ("ES", "Iberia"),
    "VLG": ("ES", "Vueling"),
    
    # === Italy ===
    "ITY": ("IT", "ITA Airways"),
    "NOS": ("IT", "Neos"),
    
    # === Greece ===
    "AEE": ("GR", "Aegean Airlines"),
    "OAL": ("GR", "Olympic Air"),
    
    # === US ===
    "AAL": ("US", "American Airlines"),
    "DAL": ("US", "Delta Air Lines"),
    "UAL": ("US", "United Airlines"),
    "SWA": ("US", "Southwest Airlines"),
    "JBU": ("US", "JetBlue Airways"),
    "FDX": ("US", "FedEx Express"),
    "UPS": ("US", "UPS Airlines"),
    "GTI": ("US", "Atlas Air"),
    
    # === Other key airlines ===
    "RYR": ("IE", "Ryanair"),
    "WZZ": ("HU", "Wizz Air"),
    "WMT": ("MT", "Wizz Air Malta"),
    "SAS": ("SE", "Scandinavian Airlines"),
    "FIN": ("FI", "Finnair"),
    "LOT": ("PL", "LOT Polish Airlines"),
    "LOY": ("PL", "LOT Polish Airlines"),  # Alternate code used in callsigns
    "CSA": ("CZ", "Czech Airlines"),
    "ROT": ("RO", "TAROM"),
    "SWR": ("CH", "Swiss International Air Lines"),
    "AUA": ("AT", "Austrian Airlines"),
    "TAP": ("PT", "TAP Air Portugal"),
    "BEL": ("BE", "Brussels Airlines"),
    "NAX": ("NO", "Norwegian Air Shuttle"),
    "TAR": ("TN", "Tunisair"),
    "RAM": ("MA", "Royal Air Maroc"),
    "DAH": ("DZ", "Air Algerie"),
    "LAJ": ("LY", "Libyan Airlines"),
    "ETH": ("ET", "Ethiopian Airlines"),
    "KQA": ("KE", "Kenya Airways"),
    "CCA": ("CN", "Air China"),
    "CES": ("CN", "China Eastern Airlines"),
    "CSN": ("CN", "China Southern Airlines"),
    "AIC": ("IN", "Air India"),
    "JAL": ("JP", "Japan Airlines"),
    "ANA": ("JP", "All Nippon Airways"),
    "KAL": ("KR", "Korean Air"),
    "SIA": ("SG", "Singapore Airlines"),
    "THA": ("TH", "Thai Airways"),
    "MAS": ("MY", "Malaysia Airlines"),
    "QFA": ("AU", "Qantas"),
    "ANZ": ("NZ", "Air New Zealand"),
    "ACA": ("CA", "Air Canada"),
    "ARG": ("AR", "Aerolineas Argentinas"),
    "GLO": ("BR", "GOL Airlines"),
    "AMX": ("MX", "Aeromexico"),
    
    # === Cargo / Charter ===
    "CLX": ("LU", "Cargolux"),
    "ABD": ("AE", "Air Atlanta Icelandic for UAE"),
    "MPH": ("NL", "Martinair"),
    "ADB": ("RU", "Antonov Design Bureau"),
}


def airline_prefix_to_country(callsign: str) -> Optional[Tuple[str, str, str]]:
    """
    Extract the 3-letter ICAO airline prefix from a callsign and look up the operator country.
    
    Args:
        callsign: Flight callsign (e.g., "ELY001", "MEA402")
        
    Returns:
        Tuple of (country_iso2, country_name_or_airline, prefix) or None if not found
    """
    if not callsign or len(callsign) < 3:
        return None
    
    prefix = callsign[:3].upper()
    
    # Must be alphabetic prefix
    if not prefix.isalpha():
        return None
    
    info = AIRLINE_COUNTRY_MAP.get(prefix)
    if info:
        return (info[0], info[1], prefix)
    
    return None


def check_identity_origin_conflict(
    hex_code: str,
    callsign: str,
) -> Optional[Dict]:
    """
    Check for Identity-Origin Conflict (IOC).
    
    Compares the country of aircraft registration (from hex code) with the 
    country of the airline operator (from callsign prefix).
    
    Args:
        hex_code: ICAO 24-bit hex address
        callsign: Flight callsign
        
    Returns:
        Dict with conflict details, or None if no conflict or data insufficient
    """
    # Look up hex country
    hex_result = hex_to_country(hex_code)
    if hex_result is None:
        return None
    hex_iso, hex_country = hex_result
    
    # Skip offshore registration hubs
    if hex_iso in OFFSHORE_REGISTRATION_COUNTRIES:
        return None
    
    # Look up airline country
    airline_result = airline_prefix_to_country(callsign)
    if airline_result is None:
        return None
    airline_iso, airline_name, prefix = airline_result
    
    # Compare countries
    if hex_iso != airline_iso:
        return {
            "conflict": True,
            "hex_code": hex_code,
            "hex_country_iso": hex_iso,
            "hex_country_name": hex_country,
            "callsign": callsign,
            "airline_prefix": prefix,
            "airline_name": airline_name,
            "airline_country_iso": airline_iso,
            "message": (
                f"Aircraft hex {hex_code} is registered in {hex_country} ({hex_iso}), "
                f"but callsign {callsign} belongs to {airline_name} ({airline_iso})"
            )
        }
    
    return None  # No conflict


def is_offshore_registration(hex_code: str) -> bool:
    """Check if hex code belongs to a known offshore registration hub."""
    result = hex_to_country(hex_code)
    if result:
        return result[0] in OFFSHORE_REGISTRATION_COUNTRIES
    return False
