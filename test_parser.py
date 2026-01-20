from app.parser import parse_signal

text = """#XAUUSD SELL 4872_75

TP 4868
TP 4864
TP 4860
TP 4856
TP 4852

SL 4885"""

sig = parse_signal(text)
if sig:
    print(f"Parsed: {sig.symbol} {sig.side} entry={sig.entry} tps={sig.tps} sl={sig.sl}")
else:
    print("Failed to parse")
