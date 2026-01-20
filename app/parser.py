import re
import logging
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger("app.parser")

@dataclass
class Signal:
    symbol: str
    side: str  # BUY / SELL
    entry: float
    tps: list[float]
    sl: Optional[float]

def parse_numbers(s: str) -> list[float]:
    """Extract all numbers from a string, supporting dots and underscores as decimal/suffix."""
    # Find things like 2025.5, 4872_75, 4872
    matches = re.findall(r"\b\d+(?:[._]\d+)?\b", s)
    results = []
    for m in matches:
        if "_" in m:
            parts = m.split("_")
            if len(parts) == 2:
                base, suffix = parts[0], parts[1]
                if len(suffix) < len(base):
                    # logic: 4872_75 -> 4875
                    results.append(float(base[:-len(suffix)] + suffix))
                else:
                    results.append(float(suffix))
        else:
            results.append(float(m.replace("_", ".")))
    return results

def parse_signal(text: str) -> Optional[Signal]:
    lines = [x.strip() for x in text.splitlines() if x.strip()]
    if not lines:
        return None
    
    # Extract Symbol and Side (searching entire message if needed, but prioritize first line)
    symbol, side = None, None
    for line in lines:
        if not symbol:
            sym_m = re.search(r"#?([A-Z0-9]{3,10})", line, re.I)
            if sym_m: symbol = sym_m.group(1).upper()
        if not side:
            # Support BUY, SELL, LONG, SHORT
            side_m = re.search(r"\b(BUY|SELL|LONG|SHORT|LIMIT BUY|LIMIT SELL)\b", line, re.I)
            if side_m:
                raw = side_m.group(1).upper()
                if raw in ["BUY", "LONG"] or "BUY" in raw:
                    side = "BUY"
                else:
                    side = "SELL"
    
    if not symbol or not side:
        return None

    entries: list[float] = []
    tps: list[float] = []
    sl: Optional[float] = None

    for i, line in enumerate(lines):
        # 1. Entry detection
        # Look for "ENTRY", "ENTRIES", "ENT", "PRICE", "AT", etc.
        # Or look for numbers on the first line if it contains the side
        is_entry_line = re.search(r"\b(ENTRY|ENTRIES|ENT|PRICE|BUY AT|SELL AT|LIMIT)\b", line, re.I)
        if is_entry_line:
            entries.extend(parse_numbers(line))
        elif i == 0:
            # Check first line numbers if no side was explicitly matched here, 
            # or just harvest all remaining numbers as potential entries
            line_clean = line.replace(symbol, "")
            entries.extend(parse_numbers(line_clean))
            
        # 2. TP detection
        m_tp = re.search(r"TP\s*(?:\d\b)?\s*[:\s-]*\s*([0-9]+(?:\.[0-9]+)?)", line, re.I)
        if m_tp:
            tps.append(float(m_tp.group(1)))
            
        # 3. SL detection
        m_sl = re.search(r"SL\s*[:\s-]*\s*([0-9]+(?:\.[0-9]+)?)", line, re.I)
        if m_sl:
            sl = float(m_sl.group(1))

    if not entries:
        # Fallback: if no explicit entry found, check second line numbers
        if len(lines) > 1:
            entries.extend(parse_numbers(lines[1]))
            
    if not entries:
        return None

    # Handle "Safe" entry:
    # SELL (Short): highest price is safest (farther from SL)
    # BUY (Long): lowest price is safest
    if side == "SELL":
        entry = max(entries)
    else:
        entry = min(entries)

    return Signal(symbol=symbol, side=side, entry=entry, tps=tps, sl=sl)
